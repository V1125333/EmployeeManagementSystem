"""Deterministic leave-balance composition from validated claims only."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, PrivateAttr

from app.ai_platform.errors import GroundingFailureError
from app.ai_platform.grounding import ClaimType, GroundedClaim, ValidatedGrounding
from app.ai_platform.contracts import PlatformContract
from app.ai_platform.capabilities.leave import LEAVE_BALANCE_CAPABILITY_ID
from app.ai_platform.capabilities.manager import EMPLOYEE_MANAGER_CAPABILITY_ID, ManagerStatus
from app.ai_platform.capabilities.projects import PROJECT_ASSIGNMENTS_CAPABILITY_ID, ProjectAssignmentsStatus
from app.schemas.ai import LeaveBalanceResultCard, LeaveBalanceToolItem


class EmployeeManagerResultCard(PlatformContract):
    type: Literal["employee_manager"] = "employee_manager"
    title: Literal["My manager"] = "My manager"
    status: ManagerStatus
    display_name: str | None = None
    job_title: str | None = None
    department: str | None = None
    work_email: EmailStr | None = None
    as_of: datetime


class CurrentProjectAssignmentCardEntry(PlatformContract):
    project_name: str
    project_code: str
    project_status: str
    allocation_role: str
    allocation_percentage: int
    allocation_start_date: date
    allocation_end_date: date | None = None
    project_manager_name: str | None = None


class CurrentProjectAssignmentsResultCard(PlatformContract):
    type: Literal["current_project_assignments"] = "current_project_assignments"
    title: Literal["My current projects"] = "My current projects"
    status: ProjectAssignmentsStatus
    as_of: date
    assignment_count: int
    assignments: tuple[CurrentProjectAssignmentCardEntry, ...] = ()
    truncated: bool = False


class ComposedPlatformContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True)

    message: str
    result_cards: tuple[
        LeaveBalanceResultCard | EmployeeManagerResultCard | CurrentProjectAssignmentsResultCard,
        ...,
    ]
    result_reference_ids: tuple[str, ...]
    safe_warnings: tuple[str, ...]
    grounded_claims: tuple[GroundedClaim, ...]
    _composer_trusted: bool = PrivateAttr(default=False)

    @property
    def is_composer_trusted(self) -> bool:
        return self._composer_trusted


def _claim_map(grounding: ValidatedGrounding) -> dict[str, GroundedClaim]:
    return {claim.source_field_paths[0]: claim for claim in grounding.claims}


def _number(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise GroundingFailureError("A numeric grounded claim is invalid.") from exc


def compose_leave_balance_response(
    grounding: ValidatedGrounding,
    *,
    locale: str,
    timezone: str,
) -> ComposedPlatformContent:
    """Compose fixed employee text and the legacy card without raw result access."""

    if not grounding.is_grounding_trusted:
        raise GroundingFailureError("Response composition requires validated grounding.")
    if locale != "en-US":
        raise GroundingFailureError("Platform 1D supports deterministic en-US composition only.")
    if not timezone:
        raise GroundingFailureError("A bounded response timezone is required.")
    claims = _claim_map(grounding)
    status = claims.get("status")
    if status is None or status.claim_type is not ClaimType.STATUS:
        raise GroundingFailureError("Grounded status is required for composition.")
    if status.rendered_value == "unavailable":
        warning_claims = sorted(
            (item for path, item in claims.items() if path.startswith("warnings.")),
            key=lambda item: int(item.source_field_paths[0].split(".")[1]),
        )
        message = (
            warning_claims[0].rendered_value
            if warning_claims
            else "Your leave balances are currently unavailable."
        )
        composed = ComposedPlatformContent(
            message=message,
            result_cards=(),
            result_reference_ids=grounding.result_reference_ids,
            safe_warnings=tuple(item.rendered_value for item in warning_claims),
            grounded_claims=grounding.claims,
        )
        object.__setattr__(composed, "_composer_trusted", True)
        return composed
    try:
        as_of = datetime.fromisoformat(claims["as_of"].rendered_value)
        year = int(claims["year"].rendered_value)
    except (KeyError, TypeError, ValueError) as exc:
        raise GroundingFailureError("Grounded balance metadata is incomplete.") from exc

    indices = sorted({
        int(path.split(".")[1])
        for path in claims if re_balance_path(path)
    })
    balances: list[LeaveBalanceToolItem] = []
    for index in indices:
        prefix = f"balances.{index}."
        try:
            available_value = claims[prefix + "available"].rendered_value
            available = "On request" if available_value == "On request" else _number(available_value)
            balances.append(LeaveBalanceToolItem(
                leave_type=claims[prefix + "leave_type"].rendered_value,
                code=claims[prefix + "code"].rendered_value,
                total=_number(claims[prefix + "total"].rendered_value),
                available=available,
                used=_number(claims[prefix + "used"].rendered_value),
                pending=_number(claims[prefix + "pending"].rendered_value),
                source=claims[prefix + "source"].rendered_value,
            ))
        except (KeyError, ValueError) as exc:
            raise GroundingFailureError("Grounded balance claims are incomplete.") from exc
    if not balances:
        raise GroundingFailureError("Available grounding requires at least one balance.")
    if len(balances) == 1:
        item = balances[0]
        available = item.available if isinstance(item.available, str) else f"{item.available:g} days"
        message = (
            f"You have {available} of {item.leave_type} available. "
            f"Used: {item.used:g} days; pending: {item.pending:g} days."
        )
    else:
        message = (
            f"I found {len(balances)} leave balances for {year}. "
            "The verified values are shown below."
        )
    warning_claims = sorted(
        (item for path, item in claims.items() if path.startswith("warnings.")),
        key=lambda item: int(item.source_field_paths[0].split(".")[1]),
    )
    composed = ComposedPlatformContent(
        message=message,
        result_cards=(LeaveBalanceResultCard(
            title="My leave balance", as_of=as_of.replace(tzinfo=None), balances=balances,
        ),),
        result_reference_ids=grounding.result_reference_ids,
        safe_warnings=tuple(item.rendered_value for item in warning_claims),
        grounded_claims=grounding.claims,
    )
    object.__setattr__(composed, "_composer_trusted", True)
    return composed


def compose_employee_manager_response(
    grounding: ValidatedGrounding, *, locale: str, timezone: str,
) -> ComposedPlatformContent:
    if not grounding.is_grounding_trusted or locale != "en-US" or not timezone:
        raise GroundingFailureError("Manager composition requires validated en-US grounding.")
    claims = _claim_map(grounding)
    try:
        status = claims["status"].rendered_value
        as_of = datetime.fromisoformat(claims["as_of"].rendered_value)
    except (KeyError, ValueError) as exc:
        raise GroundingFailureError("Grounded manager metadata is incomplete.") from exc
    if status == "available":
        try:
            name = claims["manager.display_name"].rendered_value
            email = claims["manager.work_email"].rendered_value
        except KeyError as exc:
            raise GroundingFailureError("Available manager grounding is incomplete.") from exc
        job = claims.get("manager.job_title")
        department = claims.get("manager.department")
        message = f"Your manager is {name}{', ' + job.rendered_value if job else ''}. You can reach them at {email}."
        card = EmployeeManagerResultCard(
            status=status, display_name=name,
            job_title=job.rendered_value if job else None,
            department=department.rendered_value if department else None,
            work_email=email, as_of=as_of,
        )
    else:
        message = (
            "A reporting manager is not currently assigned to your employee profile."
            if status == "not_assigned"
            else "Your manager information is currently unavailable. Please contact HR or your administrator."
        )
        card = EmployeeManagerResultCard(status=status, as_of=as_of)
    composed = ComposedPlatformContent(
        message=message, result_cards=(card,),
        result_reference_ids=grounding.result_reference_ids,
        safe_warnings=grounding.safe_warnings,
        grounded_claims=grounding.claims,
    )
    object.__setattr__(composed, "_composer_trusted", True)
    return composed


def compose_project_assignments_response(
    grounding: ValidatedGrounding, *, locale: str, timezone: str,
) -> ComposedPlatformContent:
    if not grounding.is_grounding_trusted or locale != "en-US" or not timezone:
        raise GroundingFailureError("Project composition requires validated en-US grounding.")
    claims = _claim_map(grounding)
    try:
        status = claims["status"].rendered_value
        as_of = date.fromisoformat(claims["as_of"].rendered_value)
        count = int(claims["assignment_count"].rendered_value)
        truncated = claims["truncated"].rendered_value == "True"
    except (KeyError, ValueError) as exc:
        raise GroundingFailureError("Grounded project metadata is incomplete.") from exc
    indices = sorted({
        int(path.split(".")[1]) for path in claims
        if path.startswith("assignments.") and path.split(".")[1].isdigit()
    })
    assignments: list[CurrentProjectAssignmentCardEntry] = []
    for index in indices:
        prefix = f"assignments.{index}."
        try:
            assignments.append(CurrentProjectAssignmentCardEntry(
                project_name=claims[prefix + "project_name"].rendered_value,
                project_code=claims[prefix + "project_code"].rendered_value,
                project_status=claims[prefix + "project_status"].rendered_value,
                allocation_role=claims[prefix + "allocation_role"].rendered_value,
                allocation_percentage=int(claims[prefix + "allocation_percentage"].rendered_value),
                allocation_start_date=date.fromisoformat(
                    claims[prefix + "allocation_start_date"].rendered_value
                ),
                allocation_end_date=(
                    date.fromisoformat(claims[prefix + "allocation_end_date"].rendered_value)
                    if prefix + "allocation_end_date" in claims else None
                ),
                project_manager_name=(
                    claims[prefix + "project_manager_name"].rendered_value
                    if prefix + "project_manager_name" in claims else None
                ),
            ))
        except (KeyError, ValueError) as exc:
            raise GroundingFailureError("Grounded project assignment claims are incomplete.") from exc
    if count != len(assignments):
        raise GroundingFailureError("Grounded project assignment count is contradictory.")
    if status == "available":
        if not assignments:
            raise GroundingFailureError("Available project grounding requires assignments.")
        if count == 1:
            item = assignments[0]
            message = (
                f"You are currently assigned to {item.project_name} as {item.allocation_role} "
                f"at {item.allocation_percentage}% allocation."
            )
        else:
            names = ", ".join(item.project_name for item in assignments[:-1])
            names = f"{names} and {assignments[-1].project_name}" if names else assignments[-1].project_name
            message = f"You are currently assigned to {count} projects: {names}."
    elif status == "no_current_assignments":
        if assignments:
            raise GroundingFailureError("Empty project grounding cannot contain assignments.")
        message = "You do not currently have any active project assignments."
    else:
        if assignments:
            raise GroundingFailureError("Unavailable project grounding cannot contain assignments.")
        message = "Your project assignment information is currently unavailable. Please try again later."
    card = CurrentProjectAssignmentsResultCard(
        status=status, as_of=as_of, assignment_count=count,
        assignments=tuple(assignments), truncated=truncated,
    )
    composed = ComposedPlatformContent(
        message=message, result_cards=(card,),
        result_reference_ids=grounding.result_reference_ids,
        safe_warnings=grounding.safe_warnings,
        grounded_claims=grounding.claims,
    )
    object.__setattr__(composed, "_composer_trusted", True)
    return composed


def compose_registered_response(
    grounding: ValidatedGrounding, *, locale: str, timezone: str,
) -> ComposedPlatformContent:
    capability_ids = {claim.capability_id for claim in grounding.claims}
    if capability_ids == {LEAVE_BALANCE_CAPABILITY_ID}:
        return compose_leave_balance_response(grounding, locale=locale, timezone=timezone)
    if capability_ids == {EMPLOYEE_MANAGER_CAPABILITY_ID}:
        return compose_employee_manager_response(grounding, locale=locale, timezone=timezone)
    if capability_ids == {PROJECT_ASSIGNMENTS_CAPABILITY_ID}:
        return compose_project_assignments_response(grounding, locale=locale, timezone=timezone)
    raise GroundingFailureError("No deterministic composer is registered for these claims.")


def re_balance_path(path: str) -> bool:
    parts = path.split(".")
    return len(parts) == 3 and parts[0] == "balances" and parts[1].isdigit()
