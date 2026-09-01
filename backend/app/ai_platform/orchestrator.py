"""Isolated application-controlled Platform 1D read orchestration."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.ai_platform.capabilities.leave import LeaveBalanceCapabilityError
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.errors import (
    AuthorizationDeniedError, CapabilityExecutionError, CapabilityInputInvalidError,
    CapabilityResultInvalidError, CapabilityTimeoutError, ClarificationRequiredError,
    DisabledCapabilityError, EmployeeErrorClass, GroundingFailureError, InvalidPlanError,
    PlatformError, UnknownCapabilityError, UnsupportedRequestError,
    WriteCapabilityProhibitedError,
)
from app.ai_platform.execution import CapabilityExecutionContext
from app.ai_platform.grounding import extract_registered_claims, validate_grounding
from app.ai_platform.interpreter import InterpretationStatus, InterpreterRequest, interpret_employee_request
from app.ai_platform.plan_executor import execute_validated_plan
from app.ai_platform.plan_validator import validate_candidate_plan
from app.ai_platform.platform_registry import PLATFORM_REGISTRY
from app.ai_platform.platform_request import PlatformRequest
from app.ai_platform.platform_response import (
    PlatformResponse, PlatformResponseStatus, PlatformSafeError, build_completed_response,
)
from app.ai_platform.response_composer import compose_registered_response
from app.ai_platform.trace import AIRequestTrace, TraceEvent, TraceOutcome, TraceStage


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event(stage: TraceStage, started: datetime, outcome: TraceOutcome, *, error: str | None = None,
           capability_id: str | None = None, capability_version: int | None = None,
           result_reference_id: str | None = None) -> TraceEvent:
    completed = _now()
    return TraceEvent(
        stage=stage, started_at=started, completed_at=completed,
        latency_ms=max(0, int((completed - started).total_seconds() * 1000)),
        outcome=outcome, safe_error_category=error,
        capability_id=capability_id, capability_version=capability_version,
        result_reference_id=result_reference_id,
    )


def _actor_reference(request: PlatformRequest) -> str:
    raw = f"{request.principal.organization_scope}:{request.principal.employee_id}:{request.request_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _trace(request: PlatformRequest, events: list[TraceEvent], outcome: TraceOutcome, plan_id: str | None) -> AIRequestTrace:
    return AIRequestTrace(
        request_id=request.request_id, conversation_id=request.conversation_id,
        actor_reference=_actor_reference(request), plan_id=plan_id,
        events=tuple(events), final_outcome=outcome,
    )


_SAFE_MESSAGES = {
    "UNSUPPORTED_REQUEST": "I can currently help with your leave balance, reporting manager, or current project assignments.",
    "CLARIFICATION_REQUIRED": "I need one more detail to continue safely.",
    "AUTHORIZATION_DENIED": "You do not have permission to view this information.",
    "WRITE_CAPABILITY_PROHIBITED": "That operation is not available in this read-only experience.",
    "CAPABILITY_TIMEOUT": "This information is taking too long to load. Please try again.",
    "CAPABILITY_EXECUTION_FAILURE": "This information is temporarily unavailable. Please try again.",
    "CAPABILITY_RESULT_INVALID": "This information could not be verified safely.",
    "GROUNDING_FAILURE": "This information could not be grounded safely.",
    "UNSUPPORTED_LEAVE_TYPE": "That leave type is not supported.",
    "LEAVE_TYPE_NOT_APPLICABLE": "That leave type does not apply to your profile.",
    "MISSING_POLICY_CONFIGURATION": "That leave type is not configured for the current policy year.",
    "MISSING_BALANCE_RECORD": "No effective balance is currently available for that leave type.",
}


def _classification(error: PlatformError) -> EmployeeErrorClass:
    if isinstance(error, LeaveBalanceCapabilityError) and error.legacy_code in {
        "UNSUPPORTED_LEAVE_TYPE", "LEAVE_TYPE_NOT_APPLICABLE",
        "MISSING_POLICY_CONFIGURATION", "MISSING_BALANCE_RECORD",
    }:
        return EmployeeErrorClass.UNSUPPORTED
    if isinstance(error, AuthorizationDeniedError | WriteCapabilityProhibitedError):
        return EmployeeErrorClass.DENIED
    if isinstance(error, CapabilityInputInvalidError | ClarificationRequiredError):
        return EmployeeErrorClass.CLARIFICATION
    return error.employee_classification


def _status(error: PlatformError) -> PlatformResponseStatus:
    if isinstance(error, UnsupportedRequestError):
        return PlatformResponseStatus.UNSUPPORTED
    if isinstance(error, CapabilityInputInvalidError | ClarificationRequiredError):
        return PlatformResponseStatus.CLARIFICATION_REQUIRED
    if isinstance(error, AuthorizationDeniedError | WriteCapabilityProhibitedError):
        return PlatformResponseStatus.DENIED
    if isinstance(error, CapabilityTimeoutError):
        return PlatformResponseStatus.TIMED_OUT
    return PlatformResponseStatus.FAILED


def _safe_code(error: PlatformError) -> str:
    if isinstance(error, LeaveBalanceCapabilityError):
        return error.legacy_code if error.legacy_code in _SAFE_MESSAGES else "CAPABILITY_EXECUTION_FAILURE"
    return error.code


def _error_response(request: PlatformRequest, events: list[TraceEvent], error: PlatformError,
                    stage: TraceStage, plan_id: str | None) -> PlatformResponse:
    code = _safe_code(error)
    status = _status(error)
    outcome = TraceOutcome.TIMED_OUT if status is PlatformResponseStatus.TIMED_OUT else (
        TraceOutcome.DENIED if status is PlatformResponseStatus.DENIED else TraceOutcome.FAILED
    )
    events.append(_event(stage, _now(), outcome, error=code))
    events.append(_event(TraceStage.REQUEST_COMPLETION, _now(), outcome, error=code))
    message = _SAFE_MESSAGES.get(code, "Orbit could not complete this request safely. Please try again.")
    clarification = "Which leave type would you like to check?" if status is PlatformResponseStatus.CLARIFICATION_REQUIRED else None
    return PlatformResponse(
        request_id=request.request_id, correlation_id=request.correlation_id,
        conversation_id=request.conversation_id, status=status, message=message,
        clarification=clarification,
        safe_error=PlatformSafeError(
            code=code, classification=_classification(error), message=message,
            retryable=error.retryable,
        ),
        trace=_trace(request, events, outcome, plan_id), completed_at=_now(),
    )


def run_platform_request(
    request: PlatformRequest,
    db: object,
    registry: CapabilityRegistry = PLATFORM_REGISTRY,
) -> PlatformResponse:
    """Run exactly one deterministic interpretation, plan, and read execution."""

    events = [_event(TraceStage.REQUEST, request.received_at, TraceOutcome.SUCCEEDED)]
    plan_id: str | None = None
    if _now() >= request.deadline_at:
        return _error_response(request, events, CapabilityTimeoutError("deadline"), TraceStage.INTERPRETATION, None)
    started = _now()
    try:
        interpretation = interpret_employee_request(
            InterpreterRequest(message=request.message), request.principal, registry
        )
    except ClarificationRequiredError as error:
        return _error_response(request, events, error, TraceStage.INTERPRETATION, None)
    except PlatformError as error:
        return _error_response(request, events, error, TraceStage.INTERPRETATION, None)
    events.append(_event(TraceStage.INTERPRETATION, started, TraceOutcome.SUCCEEDED))
    if interpretation.status is not InterpretationStatus.PLANNED or interpretation.candidate_plan is None:
        error = UnsupportedRequestError("unsupported")
        code = error.code
        events.append(_event(TraceStage.CANDIDATE_PLAN, _now(), TraceOutcome.SKIPPED))
        events.append(_event(TraceStage.REQUEST_COMPLETION, _now(), TraceOutcome.SKIPPED))
        message = _SAFE_MESSAGES[code]
        return PlatformResponse(
            request_id=request.request_id, correlation_id=request.correlation_id,
            conversation_id=request.conversation_id, status=PlatformResponseStatus.UNSUPPORTED,
            message=message,
            safe_error=PlatformSafeError(code=code, classification=EmployeeErrorClass.UNSUPPORTED,
                                         message=message, retryable=False),
            trace=_trace(request, events, TraceOutcome.SKIPPED, None), completed_at=_now(),
        )
    candidate = interpretation.candidate_plan
    plan_id = candidate.plan_id
    events.append(_event(TraceStage.CANDIDATE_PLAN, _now(), TraceOutcome.SUCCEEDED))
    started = _now()
    try:
        plan = validate_candidate_plan(candidate, registry, request.principal, db)
    except AuthorizationDeniedError as error:
        return _error_response(request, events, error, TraceStage.PRELIMINARY_AUTHORIZATION, plan_id)
    except PlatformError as error:
        return _error_response(request, events, error, TraceStage.PLAN_VALIDATION, plan_id)
    events.append(_event(TraceStage.PLAN_VALIDATION, started, TraceOutcome.SUCCEEDED))
    events.append(_event(TraceStage.PRELIMINARY_AUTHORIZATION, _now(), TraceOutcome.SUCCEEDED,
                         capability_id=plan.steps[0].capability_id,
                         capability_version=plan.steps[0].capability_version))
    if _now() >= request.deadline_at:
        return _error_response(request, events, CapabilityTimeoutError("deadline"), TraceStage.CAPABILITY_EXECUTION, plan_id)
    context = CapabilityExecutionContext(
        principal=request.principal, request_id=request.request_id,
        correlation_id=request.correlation_id, conversation_id=request.conversation_id,
        plan_id=plan.plan_id, step_id=plan.steps[0].step_id, deadline_at=request.deadline_at,
    )
    try:
        execution = execute_validated_plan(plan, registry, context, db)
    except AuthorizationDeniedError as error:
        return _error_response(request, events, error, TraceStage.FINAL_AUTHORIZATION, plan_id)
    except CapabilityTimeoutError as error:
        return _error_response(request, events, error, TraceStage.CAPABILITY_EXECUTION, plan_id)
    except CapabilityResultInvalidError as error:
        return _error_response(request, events, error, TraceStage.RESULT_VALIDATION, plan_id)
    except PlatformError as error:
        return _error_response(request, events, error, TraceStage.CAPABILITY_EXECUTION, plan_id)
    first = execution.steps[0]
    events.append(_event(TraceStage.FINAL_AUTHORIZATION, _now(), TraceOutcome.SUCCEEDED,
                         capability_id=plan.steps[0].capability_id,
                         capability_version=plan.steps[0].capability_version))
    events.append(_event(TraceStage.CAPABILITY_EXECUTION, _now(), TraceOutcome.SUCCEEDED,
                         capability_id=plan.steps[0].capability_id,
                         capability_version=plan.steps[0].capability_version))
    events.append(_event(TraceStage.RESULT_VALIDATION, _now(), TraceOutcome.SUCCEEDED,
                         capability_id=plan.steps[0].capability_id,
                         capability_version=plan.steps[0].capability_version,
                         result_reference_id=first.result.reference.result_reference_id))
    results = tuple(step.result for step in execution.steps)
    started = _now()
    try:
        claims = tuple(claim for result in results for claim in extract_registered_claims(result))
    except GroundingFailureError as error:
        return _error_response(request, events, error, TraceStage.CLAIM_EXTRACTION, plan_id)
    events.append(_event(TraceStage.CLAIM_EXTRACTION, started, TraceOutcome.SUCCEEDED))
    started = _now()
    try:
        grounding = validate_grounding(plan, results, claims)
    except GroundingFailureError as error:
        return _error_response(request, events, error, TraceStage.GROUNDING_VALIDATION, plan_id)
    events.append(_event(TraceStage.GROUNDING_VALIDATION, started, TraceOutcome.SUCCEEDED))
    started = _now()
    try:
        content = compose_registered_response(
            grounding, locale=request.locale, timezone=request.timezone
        )
    except GroundingFailureError as error:
        return _error_response(request, events, error, TraceStage.COMPOSITION, plan_id)
    events.append(_event(TraceStage.COMPOSITION, started, TraceOutcome.SUCCEEDED))
    events.append(_event(TraceStage.REQUEST_COMPLETION, _now(), TraceOutcome.SUCCEEDED))
    trace = _trace(request, events, TraceOutcome.SUCCEEDED, plan_id)
    return build_completed_response(
        request_id=request.request_id, correlation_id=request.correlation_id,
        conversation_id=request.conversation_id, content=content, trace=trace,
        completed_at=_now(),
    )
