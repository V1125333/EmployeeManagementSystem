"""Safe developer-preview contracts and adapters for the isolated Platform."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
import secrets
import time
from typing import Literal

from pydantic import Field

from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.contracts import PlatformContract
from app.ai_platform.errors import AuthorizationDeniedError, PlatformError
from app.ai_platform.execution import ExecutionPrincipal
from app.ai_platform.interpreter import (
    InterpretationStatus, InterpreterRequest, interpret_employee_request,
)
from app.ai_platform.orchestrator import run_platform_request
from app.ai_platform.plan_validator import validate_candidate_plan
from app.ai_platform.platform_registry import PLATFORM_REGISTRY
from app.ai_platform.platform_request import PlatformRequest
from app.ai_platform.platform_response import PlatformResponseStatus
from app.ai_platform.response_composer import (
    CurrentProjectAssignmentsResultCard, EmployeeManagerResultCard,
)
from app.ai_platform.trace import AIRequestTrace, TraceOutcome, TraceStage
from app.schemas.ai import LeaveBalanceResultCard


class PlatformPreviewRequest(PlatformContract):
    message: str = Field(min_length=1, max_length=2_000)


class PreviewCheckStatus(str, Enum):
    PASSED = "passed"
    DENIED = "denied"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    UNSUPPORTED = "unsupported"
    NOT_REACHED = "not_reached"


class PreviewCandidateSummary(PlatformContract):
    capability_id: str = Field(min_length=5, max_length=120)
    capability_version: int = Field(gt=0, le=999)
    step_count: int = Field(ge=1, le=3)


class PreviewValidatedSummary(PlatformContract):
    capability_id: str = Field(min_length=5, max_length=120)
    capability_version: int = Field(gt=0, le=999)


class PreviewTraceStageSummary(PlatformContract):
    stage: TraceStage
    outcome: TraceOutcome
    started_at: datetime
    completed_at: datetime
    latency_ms: int = Field(ge=0, le=3_600_000)
    capability_id: str | None = Field(default=None, min_length=5, max_length=120)
    capability_version: int | None = Field(default=None, gt=0, le=999)
    safe_error_code: str | None = Field(default=None, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    result_reference_id: str | None = Field(default=None, min_length=20, max_length=80)


PreviewResultCard = (
    LeaveBalanceResultCard | EmployeeManagerResultCard | CurrentProjectAssignmentsResultCard
)


class PreviewEmployeeResponse(PlatformContract):
    status: PlatformResponseStatus
    message: str = Field(min_length=1, max_length=1_000)
    result_card: PreviewResultCard | None = None
    safe_error_code: str | None = Field(default=None, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    correlation_id: str = Field(min_length=8, max_length=64)


class PreviewDeveloperSummary(PlatformContract):
    interpreted_intent: str = Field(min_length=2, max_length=80)
    interpretation_source: Literal["deterministic"] = "deterministic"
    interpretation_status: PreviewCheckStatus
    candidate_plan: PreviewCandidateSummary | None = None
    validated_plan: PreviewValidatedSummary | None = None
    plan_validation_status: PreviewCheckStatus
    authorization_result_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    execution_status: PreviewCheckStatus
    grounding_validation_status: PreviewCheckStatus
    composition_status: PreviewCheckStatus
    trace_stages: tuple[PreviewTraceStageSummary, ...] = Field(default=(), max_length=32)
    total_latency_ms: int = Field(ge=0, le=3_600_000)
    result_reference_ids: tuple[str, ...] = Field(default=(), max_length=3)
    safe_warning_codes: tuple[str, ...] = Field(default=(), max_length=8)


class PlatformPreviewResponse(PlatformContract):
    employee_response: PreviewEmployeeResponse
    developer_summary: PreviewDeveloperSummary


def _preview_status(outcome: TraceOutcome | None) -> PreviewCheckStatus:
    return {
        TraceOutcome.SUCCEEDED: PreviewCheckStatus.PASSED,
        TraceOutcome.DENIED: PreviewCheckStatus.DENIED,
        TraceOutcome.FAILED: PreviewCheckStatus.FAILED,
        TraceOutcome.TIMED_OUT: PreviewCheckStatus.TIMED_OUT,
        TraceOutcome.SKIPPED: PreviewCheckStatus.NOT_REACHED,
        None: PreviewCheckStatus.NOT_REACHED,
    }[outcome]


def _stage_status(events: tuple[PreviewTraceStageSummary, ...], *stages: TraceStage) -> PreviewCheckStatus:
    matching = [item for item in events if item.stage in stages]
    return _preview_status(matching[-1].outcome if matching else None)


_PREVIEW_TRACE_STAGES = frozenset({
    TraceStage.REQUEST,
    TraceStage.INTERPRETATION,
    TraceStage.CANDIDATE_PLAN,
    TraceStage.PLAN_VALIDATION,
    TraceStage.PRELIMINARY_AUTHORIZATION,
    TraceStage.AUTHORIZATION,
    TraceStage.FINAL_AUTHORIZATION,
    TraceStage.CAPABILITY_EXECUTION,
    TraceStage.RESULT_VALIDATION,
    TraceStage.CLAIM_EXTRACTION,
    TraceStage.GROUNDING_VALIDATION,
    TraceStage.COMPOSITION,
    TraceStage.REQUEST_COMPLETION,
})


def summarize_trace(trace: AIRequestTrace) -> tuple[PreviewTraceStageSummary, ...]:
    """Copy only explicitly allowlisted fields from the in-memory trace."""

    return tuple(
        PreviewTraceStageSummary(
            stage=event.stage,
            outcome=event.outcome,
            started_at=event.started_at,
            completed_at=event.completed_at,
            latency_ms=event.latency_ms,
            capability_id=event.capability_id,
            capability_version=event.capability_version,
            safe_error_code=event.safe_error_category,
            result_reference_id=event.result_reference_id,
        )
        for event in trace.events
        if event.stage in _PREVIEW_TRACE_STAGES
    )


def run_platform_preview(
    *,
    message: str,
    principal: ExecutionPrincipal,
    db: object,
    timezone_name: str,
    registry: CapabilityRegistry = PLATFORM_REGISTRY,
) -> PlatformPreviewResponse:
    """Run the isolated Platform and return only employee-safe and preview-safe fields."""

    started = time.perf_counter()
    interpretation = interpret_employee_request(
        InterpreterRequest(message=message), principal, registry
    )
    candidate = interpretation.candidate_plan
    candidate_summary = None
    validated_summary = None
    validation_status = PreviewCheckStatus.NOT_REACHED
    authorization_code = "NOT_REACHED"
    if candidate is not None:
        first = candidate.steps[0]
        candidate_summary = PreviewCandidateSummary(
            capability_id=first.capability_id,
            capability_version=first.capability_version,
            step_count=len(candidate.steps),
        )
        try:
            validated = validate_candidate_plan(candidate, registry, principal, db)
            validated_first = validated.steps[0]
            validated_summary = PreviewValidatedSummary(
                capability_id=validated_first.capability_id,
                capability_version=validated_first.capability_version,
            )
            validation_status = PreviewCheckStatus.PASSED
            authorization_code = validated_first.preliminary_authorization.reason_code
        except AuthorizationDeniedError:
            validation_status = PreviewCheckStatus.DENIED
            authorization_code = "AUTHORIZATION_DENIED"
        except PlatformError as exc:
            validation_status = PreviewCheckStatus.FAILED
            authorization_code = exc.code

    received_at = datetime.now(timezone.utc)
    correlation_id = "preview-corr-" + secrets.token_urlsafe(12)
    platform_request = PlatformRequest(
        request_id="preview-req-" + secrets.token_urlsafe(12),
        correlation_id=correlation_id,
        conversation_id="preview-session-" + secrets.token_urlsafe(12),
        principal=principal,
        message=message,
        locale="en-US",
        timezone=timezone_name,
        received_at=received_at,
        deadline_at=received_at + timedelta(seconds=10),
    )
    response = run_platform_request(platform_request, db, registry)
    stages = summarize_trace(response.trace)
    total_latency_ms = min(
        int((time.perf_counter() - started) * 1000),
        3_600_000,
    )
    if interpretation.status is InterpretationStatus.UNSUPPORTED:
        interpretation_status = PreviewCheckStatus.UNSUPPORTED
    else:
        interpretation_status = PreviewCheckStatus.PASSED
    return PlatformPreviewResponse(
        employee_response=PreviewEmployeeResponse(
            status=response.status,
            message=response.message,
            result_card=response.result_cards[0] if response.result_cards else None,
            safe_error_code=response.safe_error.code if response.safe_error else None,
            correlation_id=response.correlation_id,
        ),
        developer_summary=PreviewDeveloperSummary(
            interpreted_intent=interpretation.intent,
            interpretation_status=interpretation_status,
            candidate_plan=candidate_summary,
            validated_plan=validated_summary,
            plan_validation_status=validation_status,
            authorization_result_code=authorization_code,
            execution_status=_stage_status(stages, TraceStage.CAPABILITY_EXECUTION),
            grounding_validation_status=_stage_status(stages, TraceStage.GROUNDING_VALIDATION),
            composition_status=_stage_status(stages, TraceStage.COMPOSITION),
            trace_stages=stages,
            total_latency_ms=total_latency_ms,
            result_reference_ids=response.result_reference_ids,
            safe_warning_codes=response.safe_warnings,
        ),
    )
