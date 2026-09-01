"""Strict internal response and safe error contracts for Platform 1D."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationInfo, field_validator, model_validator

from app.ai_platform.contracts import PlatformContract, require_timezone_aware
from app.ai_platform.errors import EmployeeErrorClass, GroundingFailureError
from app.ai_platform.grounding import GroundedClaim
from app.ai_platform.response_composer import (
    ComposedPlatformContent, EmployeeManagerResultCard,
    CurrentProjectAssignmentsResultCard,
)
from app.ai_platform.capabilities.manager import EMPLOYEE_MANAGER_CAPABILITY_ID
from app.ai_platform.capabilities.projects import PROJECT_ASSIGNMENTS_CAPABILITY_ID
from app.ai_platform.trace import AIRequestTrace, TraceOutcome
from app.schemas.ai import LeaveBalanceResultCard


class PlatformResponseStatus(str, Enum):
    COMPLETED = "completed"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"
    DENIED = "denied"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class PlatformSafeError(PlatformContract):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    classification: EmployeeErrorClass
    message: str = Field(min_length=1, max_length=240)
    retryable: bool = False

    @field_validator("message")
    @classmethod
    def sanitized_message(cls, value: str) -> str:
        lowered = value.lower()
        if any(marker in lowered for marker in (
            "bearer ", "authorization", "api_key", "api key", "password", "traceback",
        )):
            raise ValueError("safe errors cannot contain credentials or internal diagnostics")
        return " ".join(value.split())


_RESPONSE_CONTEXT = object()


class PlatformResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True)

    request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    correlation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    conversation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    status: PlatformResponseStatus
    message: str = Field(min_length=1, max_length=1_000)
    result_cards: tuple[
        LeaveBalanceResultCard | EmployeeManagerResultCard | CurrentProjectAssignmentsResultCard,
        ...,
    ] = Field(default=(), max_length=1)
    result_reference_ids: tuple[str, ...] = Field(default=(), max_length=3)
    grounded_claims: tuple[GroundedClaim, ...] = Field(default=(), max_length=192)
    safe_warnings: tuple[str, ...] = Field(default=(), max_length=8)
    clarification: str | None = Field(default=None, min_length=1, max_length=240)
    safe_error: PlatformSafeError | None = None
    trace: AIRequestTrace
    completed_at: datetime
    _composition_trusted: bool = PrivateAttr(default=False)

    @field_validator("completed_at")
    @classmethod
    def aware_completion(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)

    @model_validator(mode="after")
    def status_shape(self, info: ValidationInfo) -> "PlatformResponse":
        if self.status is PlatformResponseStatus.COMPLETED:
            trusted = bool(info.context and info.context.get("composition") is _RESPONSE_CONTEXT)
            if not trusted and not self._composition_trusted:
                raise ValueError("completed responses require deterministic composer attestation")
            if not self.grounded_claims or not self.result_reference_ids:
                raise ValueError("completed factual responses require grounded claims and result references")
            if self.safe_error or self.clarification:
                raise ValueError("completed responses cannot include errors or clarification")
            if self.trace.final_outcome is not TraceOutcome.SUCCEEDED:
                raise ValueError("completed response trace must succeed")
        else:
            if self.result_cards or self.grounded_claims or self.result_reference_ids:
                raise ValueError("non-completed responses cannot include factual results")
        if self.status is PlatformResponseStatus.CLARIFICATION_REQUIRED:
            if not self.clarification or self.clarification.count("?") != 1 or not self.clarification.endswith("?"):
                raise ValueError("clarification requires one bounded question")
        elif self.clarification is not None:
            raise ValueError("clarification is valid only for clarification responses")
        if self.status in {PlatformResponseStatus.DENIED, PlatformResponseStatus.FAILED, PlatformResponseStatus.TIMED_OUT} and self.safe_error is None:
            raise ValueError("failed responses require a safe error")
        return self

    @property
    def is_composition_trusted(self) -> bool:
        return self._composition_trusted


def build_completed_response(
    *, request_id: str, correlation_id: str, conversation_id: str,
    content: ComposedPlatformContent, trace: AIRequestTrace, completed_at: datetime,
) -> PlatformResponse:
    if not content.is_composer_trusted:
        raise GroundingFailureError("Completed responses require deterministic composed content.")
    response = PlatformResponse.model_validate({
        "request_id": request_id, "correlation_id": correlation_id,
        "conversation_id": conversation_id, "status": PlatformResponseStatus.COMPLETED,
        "message": content.message, "result_cards": content.result_cards,
        "result_reference_ids": content.result_reference_ids,
        "grounded_claims": content.grounded_claims, "safe_warnings": content.safe_warnings,
        "trace": trace, "completed_at": completed_at,
    }, context={"composition": _RESPONSE_CONTEXT})
    object.__setattr__(response, "_composition_trusted", True)
    verify_platform_response(response)
    return response


def verify_platform_response(response: PlatformResponse) -> None:
    """Detect any post-composition factual card substitution or mutation."""

    if response.status is not PlatformResponseStatus.COMPLETED:
        return
    if not response.is_composition_trusted:
        raise GroundingFailureError("The completed response is not composer-attested.")
    paths = {claim.source_field_paths[0]: claim.rendered_value for claim in response.grounded_claims}
    claim_references = tuple(dict.fromkeys(
        claim.source_result_reference_id for claim in response.grounded_claims
    ))
    if claim_references != response.result_reference_ids:
        raise GroundingFailureError("Response references do not match grounded claims.")
    capability_ids = {claim.capability_id for claim in response.grounded_claims}
    if capability_ids == {EMPLOYEE_MANAGER_CAPABILITY_ID}:
        if len(response.result_cards) != 1 or not isinstance(response.result_cards[0], EmployeeManagerResultCard):
            raise GroundingFailureError("Manager grounding requires one manager result card.")
        card = response.result_cards[0]
        status = paths.get("status")
        expected = {
            "status": status,
            "display_name": paths.get("manager.display_name"),
            "job_title": paths.get("manager.job_title"),
            "department": paths.get("manager.department"),
            "work_email": paths.get("manager.work_email"),
        }
        if any(getattr(card, field) != value for field, value in expected.items()):
            raise GroundingFailureError("Manager result card does not match grounded claims.")
        if card.as_of.isoformat() != datetime.fromisoformat(paths["as_of"]).isoformat():
            raise GroundingFailureError("Manager result card timestamp does not match grounded claims.")
        if status == "available":
            job = f", {card.job_title}" if card.job_title else ""
            expected_message = f"Your manager is {card.display_name}{job}. You can reach them at {card.work_email}."
        else:
            expected_message = (
                "A reporting manager is not currently assigned to your employee profile."
                if status == "not_assigned"
                else "Your manager information is currently unavailable. Please contact HR or your administrator."
            )
        if response.message != expected_message:
            raise GroundingFailureError("Manager response text is not grounded.")
        return
    if capability_ids == {PROJECT_ASSIGNMENTS_CAPABILITY_ID}:
        if (
            len(response.result_cards) != 1
            or not isinstance(response.result_cards[0], CurrentProjectAssignmentsResultCard)
        ):
            raise GroundingFailureError("Project grounding requires one project result card.")
        card = response.result_cards[0]
        try:
            expected_count = int(paths["assignment_count"])
            expected_truncated = paths["truncated"] == "True"
        except (KeyError, ValueError) as exc:
            raise GroundingFailureError("Project card metadata is not grounded.") from exc
        if (
            card.status != paths.get("status")
            or card.as_of.isoformat() != paths.get("as_of")
            or card.assignment_count != expected_count
            or card.truncated != expected_truncated
            or len(card.assignments) != expected_count
        ):
            raise GroundingFailureError("Project result card metadata does not match grounded claims.")
        for index, item in enumerate(card.assignments):
            prefix = f"assignments.{index}."
            expected = {
                "project_name": item.project_name,
                "project_code": item.project_code,
                "project_status": item.project_status,
                "allocation_role": item.allocation_role,
                "allocation_percentage": str(item.allocation_percentage),
                "allocation_start_date": item.allocation_start_date.isoformat(),
                "allocation_end_date": item.allocation_end_date.isoformat() if item.allocation_end_date else None,
                "project_manager_name": item.project_manager_name,
            }
            if any(paths.get(prefix + field) != value for field, value in expected.items()):
                raise GroundingFailureError("Project result card facts do not match grounded claims.")
        if card.status == "available" and expected_count == 1:
            item = card.assignments[0]
            expected_message = (
                f"You are currently assigned to {item.project_name} as {item.allocation_role} "
                f"at {item.allocation_percentage}% allocation."
            )
        elif card.status == "available":
            names = ", ".join(item.project_name for item in card.assignments[:-1])
            names = f"{names} and {card.assignments[-1].project_name}" if names else card.assignments[-1].project_name
            expected_message = f"You are currently assigned to {expected_count} projects: {names}."
        elif card.status == "no_current_assignments":
            expected_message = "You do not currently have any active project assignments."
        else:
            expected_message = "Your project assignment information is currently unavailable. Please try again later."
        if response.message != expected_message:
            raise GroundingFailureError("Project response text is not grounded.")
        return
    if paths.get("status") == "unavailable":
        if response.result_cards:
            raise GroundingFailureError("Unavailable grounding cannot include a factual card.")
        warning_paths = sorted(
            (path for path in paths if path.startswith("warnings.")),
            key=lambda path: int(path.split(".")[1]),
        )
        expected_message = paths[warning_paths[0]] if warning_paths else "Your leave balances are currently unavailable."
        if response.message != expected_message:
            raise GroundingFailureError("Employee message is not derived from grounded claims.")
        return
    if len(response.result_cards) != 1:
        raise GroundingFailureError("Available grounding requires one compatible result card.")
    card = response.result_cards[0]
    if paths.get("as_of") is None or card.as_of.isoformat() != datetime.fromisoformat(paths["as_of"]).replace(tzinfo=None).isoformat():
        raise GroundingFailureError("Result card timestamp does not match grounded claims.")
    expected_indices = {
        int(path.split(".")[1]) for path in paths
        if path.startswith("balances.") and path.split(".")[1].isdigit()
    }
    if expected_indices != set(range(len(card.balances))):
        raise GroundingFailureError("Result card balance rows do not match grounded claims.")
    for index, item in enumerate(card.balances):
        prefix = f"balances.{index}."
        expected = {
            "leave_type": item.leave_type, "code": item.code, "total": f"{item.total:g}",
            "available": item.available if isinstance(item.available, str) else f"{item.available:g}",
            "used": f"{item.used:g}", "pending": f"{item.pending:g}", "source": item.source,
        }
        if any(paths.get(prefix + field) != str(value) for field, value in expected.items()):
            raise GroundingFailureError("Result card facts do not match grounded claims.")
    if len(card.balances) == 1:
        item = card.balances[0]
        available = item.available if isinstance(item.available, str) else f"{item.available:g} days"
        expected_message = (
            f"You have {available} of {item.leave_type} available. "
            f"Used: {item.used:g} days; pending: {item.pending:g} days."
        )
    else:
        expected_message = (
            f"I found {len(card.balances)} leave balances for {paths['year']}. "
            "The verified values are shown below."
        )
    if response.message != expected_message:
        raise GroundingFailureError("Employee message is not derived from grounded claims.")
