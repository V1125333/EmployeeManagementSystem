"""Minimal constrained executor for explicitly registered read capabilities."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai_platform.authorization import AuthorizationDecision
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.errors import (
    AuthorizationDeniedError,
    CapabilityExecutionError,
    CapabilityInputInvalidError,
    CapabilityResultInvalidError,
    CapabilityTimeoutError,
    PlatformError,
)
from app.ai_platform.execution import CapabilityExecutionContext
from app.ai_platform.result import ValidatedCapabilityResult
from app.ai_platform.trace import AIRequestTrace, TraceEvent, TraceOutcome, TraceStage


class CapabilityExecutionOutcome(BaseModel):
    model_config = {"extra": "forbid", "frozen": True, "arbitrary_types_allowed": True}

    result: ValidatedCapabilityResult
    trace: AIRequestTrace


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event(
    stage: TraceStage,
    started_at: datetime,
    *,
    outcome: TraceOutcome,
    capability_id: str | None = None,
    capability_version: int | None = None,
    error_code: str | None = None,
    result_reference_id: str | None = None,
) -> TraceEvent:
    completed_at = _now()
    return TraceEvent(
        stage=stage,
        started_at=started_at,
        completed_at=completed_at,
        latency_ms=max(0, int((completed_at - started_at).total_seconds() * 1000)),
        outcome=outcome,
        safe_error_category=error_code,
        capability_id=capability_id,
        capability_version=capability_version,
        result_reference_id=result_reference_id,
    )


def _actor_reference(context: CapabilityExecutionContext) -> str:
    value = (
        f"{context.principal.organization_scope}:"
        f"{context.principal.employee_id}:{context.request_id}"
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _trace(
    context: CapabilityExecutionContext,
    events: list[TraceEvent],
    outcome: TraceOutcome,
) -> AIRequestTrace:
    return AIRequestTrace(
        request_id=context.request_id,
        conversation_id=context.conversation_id,
        actor_reference=_actor_reference(context),
        plan_id=context.plan_id,
        events=tuple(events),
        final_outcome=outcome,
    )


def _raise_with_trace(
    error: PlatformError,
    context: CapabilityExecutionContext,
    events: list[TraceEvent],
    outcome: TraceOutcome,
) -> None:
    error.execution_trace = _trace(context, events, outcome)
    raise error


def execute_capability(
    registry: CapabilityRegistry,
    capability_id: str,
    capability_version: int,
    raw_input: BaseModel | dict[str, Any],
    context: CapabilityExecutionContext,
    db: object,
) -> CapabilityExecutionOutcome:
    """Execute one fixed registry entry with no dynamic invocation or chaining."""

    request_time = _now()
    events = [
        _event(
            TraceStage.REQUEST,
            request_time,
            outcome=TraceOutcome.SUCCEEDED,
        )
    ]
    stage_started = _now()
    try:
        definition = registry.resolve(capability_id, capability_version, production=True)
    except PlatformError as exc:
        events.append(_event(
            TraceStage.CAPABILITY_RESOLUTION,
            stage_started,
            outcome=TraceOutcome.FAILED,
            error_code=exc.code,
        ))
        _raise_with_trace(exc, context, events, TraceOutcome.FAILED)
    events.append(_event(
        TraceStage.CAPABILITY_RESOLUTION,
        stage_started,
        outcome=TraceOutcome.SUCCEEDED,
        capability_id=capability_id,
        capability_version=capability_version,
    ))

    payload = raw_input.model_dump() if isinstance(raw_input, BaseModel) else raw_input
    try:
        validated_input = definition.input_model.model_validate(payload, strict=True)
    except ValidationError as exc:
        error = CapabilityInputInvalidError(
            "Capability input did not match the registered contract."
        )
        events.append(_event(
            TraceStage.PLAN_VALIDATION,
            _now(),
            outcome=TraceOutcome.FAILED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.FAILED)

    authorization_started = _now()
    try:
        preliminary = definition.authorization_policy(db, context.principal, validated_input)
    except Exception as exc:
        error = CapabilityExecutionError("Capability authorization failed safely.")
        error.__cause__ = exc
        events.append(_event(
            TraceStage.AUTHORIZATION,
            authorization_started,
            outcome=TraceOutcome.FAILED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.FAILED)
    if not isinstance(preliminary, AuthorizationDecision) or not preliminary.allowed:
        error = AuthorizationDeniedError("The capability is not authorized.")
        events.append(_event(
            TraceStage.AUTHORIZATION,
            authorization_started,
            outcome=TraceOutcome.DENIED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.DENIED)
    events.append(_event(
        TraceStage.AUTHORIZATION,
        authorization_started,
        outcome=TraceOutcome.SUCCEEDED,
        capability_id=capability_id,
        capability_version=capability_version,
    ))

    deadline = min(
        context.deadline_at.timestamp(),
        time.time() + definition.timeout_seconds,
    )
    if time.time() >= deadline:
        error = CapabilityTimeoutError("The capability deadline expired before execution.")
        events.append(_event(
            TraceStage.CAPABILITY_EXECUTION,
            _now(), outcome=TraceOutcome.TIMED_OUT,
            capability_id=capability_id, capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.TIMED_OUT)

    final_auth_started = _now()
    try:
        final_decision = definition.authorization_policy(db, context.principal, validated_input)
    except Exception as exc:
        error = CapabilityExecutionError("Capability authorization failed safely.")
        error.__cause__ = exc
        events.append(_event(
            TraceStage.AUTHORIZATION,
            final_auth_started,
            outcome=TraceOutcome.FAILED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.FAILED)
    if not isinstance(final_decision, AuthorizationDecision) or not final_decision.allowed:
        error = AuthorizationDeniedError("The capability is not authorized.")
        events.append(_event(
            TraceStage.AUTHORIZATION,
            final_auth_started,
            outcome=TraceOutcome.DENIED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.DENIED)
    events.append(_event(
        TraceStage.AUTHORIZATION,
        final_auth_started,
        outcome=TraceOutcome.SUCCEEDED,
        capability_id=capability_id,
        capability_version=capability_version,
    ))

    execution_started = _now()
    try:
        raw_output = definition.executor(db, context, validated_input)
        if time.time() >= deadline:
            raise CapabilityTimeoutError("The capability execution exceeded its deadline.")
        typed_output = definition.output_model.model_validate(
            raw_output.model_dump() if isinstance(raw_output, BaseModel) else raw_output,
            strict=True,
        )
        postcondition_output = definition.postcondition_validator(typed_output)
    except PlatformError as exc:
        outcome = TraceOutcome.TIMED_OUT if isinstance(exc, CapabilityTimeoutError) else TraceOutcome.FAILED
        events.append(_event(
            TraceStage.CAPABILITY_EXECUTION,
            execution_started,
            outcome=outcome,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=exc.code,
        ))
        _raise_with_trace(exc, context, events, outcome)
    except (ValidationError, TypeError, ValueError) as exc:
        error = CapabilityResultInvalidError("The capability returned an invalid result.")
        events.append(_event(
            TraceStage.CAPABILITY_EXECUTION,
            execution_started,
            outcome=TraceOutcome.FAILED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.FAILED)
    except Exception as exc:
        error = CapabilityExecutionError("The capability execution failed safely.")
        error.__cause__ = exc
        events.append(_event(
            TraceStage.CAPABILITY_EXECUTION,
            execution_started,
            outcome=TraceOutcome.FAILED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.FAILED)
    events.append(_event(
        TraceStage.CAPABILITY_EXECUTION,
        execution_started,
        outcome=TraceOutcome.SUCCEEDED,
        capability_id=capability_id,
        capability_version=capability_version,
    ))

    validation_started = _now()
    try:
        result = definition.result_validator(postcondition_output)
        if not isinstance(result, ValidatedCapabilityResult):
            raise TypeError("result validator did not return a validated result")
    except PlatformError as exc:
        events.append(_event(
            TraceStage.RESULT_VALIDATION,
            validation_started,
            outcome=TraceOutcome.FAILED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=exc.code,
        ))
        _raise_with_trace(exc, context, events, TraceOutcome.FAILED)
    except Exception as exc:
        error = CapabilityResultInvalidError("The capability result failed validation.")
        error.__cause__ = exc
        events.append(_event(
            TraceStage.RESULT_VALIDATION,
            validation_started,
            outcome=TraceOutcome.FAILED,
            capability_id=capability_id,
            capability_version=capability_version,
            error_code=error.code,
        ))
        _raise_with_trace(error, context, events, TraceOutcome.FAILED)
    events.append(_event(
        TraceStage.RESULT_VALIDATION,
        validation_started,
        outcome=TraceOutcome.SUCCEEDED,
        capability_id=capability_id,
        capability_version=capability_version,
        result_reference_id=result.reference.result_reference_id,
    ))
    return CapabilityExecutionOutcome(
        result=result,
        trace=_trace(context, events, TraceOutcome.SUCCEEDED),
    )

