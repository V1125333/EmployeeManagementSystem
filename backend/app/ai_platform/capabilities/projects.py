"""Self-scoped current project-assignment capability."""

from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.ai_platform.authorization import AuthorizationDecision, minimize_target_reference
from app.ai_platform.contracts import ActorScope, DataClassification, PlatformContract
from app.ai_platform.errors import CapabilityExecutionError, CapabilityResultInvalidError
from app.ai_platform.execution import CapabilityExecutionContext, ExecutionPrincipal
from app.ai_platform.result import (
    CapabilityResultReference, Freshness, ResultAvailability,
    ResultValidationStatus, ValidatedCapabilityResult,
)
from app.core.authentication import PROJECT_ASSIGNMENTS_SELF_PERMISSION
from app.models.employee import Employee
from app.services.leave_eligibility_service import local_now
from app.services.project_assignment_service import list_current_project_assignments

PROJECT_ASSIGNMENTS_CAPABILITY_ID = "project.assignments.list_self"
PROJECT_ASSIGNMENTS_CAPABILITY_VERSION = 1


class CurrentProjectAssignmentsCapabilityInput(PlatformContract):
    pass


class ProjectAssignmentProjection(PlatformContract):
    project_name: str = Field(min_length=1, max_length=200)
    project_code: str = Field(min_length=1, max_length=20)
    project_status: Literal["active"]
    allocation_role: str = Field(min_length=1, max_length=100)
    allocation_percentage: int = Field(ge=1, le=100)
    allocation_start_date: date
    allocation_end_date: date | None = None
    project_manager_name: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_dates(self) -> "ProjectAssignmentProjection":
        if self.allocation_end_date and self.allocation_end_date < self.allocation_start_date:
            raise ValueError("allocation end date cannot precede its start date")
        return self


ProjectAssignmentsStatus = Literal["available", "no_current_assignments", "unavailable"]


class CurrentProjectAssignmentsCapabilityOutput(PlatformContract):
    status: ProjectAssignmentsStatus
    as_of: date
    assignment_count: int = Field(ge=0, le=20)
    assignments: tuple[ProjectAssignmentProjection, ...] = Field(default=(), max_length=20)
    truncated: bool = False
    safe_warnings: tuple[str, ...] = Field(default=(), max_length=6)

    @field_validator("safe_warnings")
    @classmethod
    def bounded_warnings(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        allowed = {
            "inactive_or_missing_project_excluded",
            "duplicate_active_allocations_combined",
            "allocation_percentage_capped",
            "assignment_results_truncated",
        }
        if any(value not in allowed for value in values) or len(set(values)) != len(values):
            raise ValueError("project warnings must be unique bounded codes")
        return values

    @model_validator(mode="after")
    def valid_state(self) -> "CurrentProjectAssignmentsCapabilityOutput":
        if self.assignment_count != len(self.assignments):
            raise ValueError("assignment count must match returned assignments")
        if self.status == "available" and not self.assignments:
            raise ValueError("available results require assignments")
        if self.status != "available" and self.assignments:
            raise ValueError("nonavailable results cannot contain assignments")
        if self.status == "no_current_assignments" and self.assignment_count != 0:
            raise ValueError("empty status requires an empty result")
        if self.status == "unavailable" and (self.assignment_count or self.truncated):
            raise ValueError("unavailable results cannot contain project facts")
        identities = [(item.project_name.casefold(), item.project_code.casefold()) for item in self.assignments]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate project assignments are prohibited")
        if identities != sorted(identities):
            raise ValueError("project assignments must use canonical ordering")
        if self.truncated != ("assignment_results_truncated" in self.safe_warnings):
            raise ValueError("truncation state must match its safe warning")
        return self


def authorize_project_assignments_list_self(
    db: Session,
    principal: ExecutionPrincipal,
    _input: CurrentProjectAssignmentsCapabilityInput,
) -> AuthorizationDecision:
    employee = db.query(Employee).filter(Employee.id == principal.employee_id).first()
    target_hash = minimize_target_reference(principal.employee_id, salt="project-assignments-v1")
    if (
        principal.status.strip().lower() != "active" or employee is None
        or not employee.is_active or employee.employment_status != "active"
        or employee.account_locked
    ):
        return AuthorizationDecision.deny(
            reason_code="ACTOR_NOT_ACTIVE", evaluated_scope=ActorScope.SELF,
            policy_version="project-assignments-v1", target_reference_hash=target_hash,
            evaluated_at=datetime.now(timezone.utc),
        )
    if not principal.has_permission(PROJECT_ASSIGNMENTS_SELF_PERMISSION):
        return AuthorizationDecision.deny(
            reason_code="SELF_PERMISSION_MISSING", evaluated_scope=ActorScope.SELF,
            policy_version="project-assignments-v1", target_reference_hash=target_hash,
            evaluated_at=datetime.now(timezone.utc),
        )
    return AuthorizationDecision.allow(
        reason_code="SELF_PERMISSION_ALLOWED", evaluated_scope=ActorScope.SELF,
        policy_version="project-assignments-v1", target_reference_hash=target_hash,
        evaluated_at=datetime.now(timezone.utc),
    )


def execute_project_assignments_adapter(
    db: Session,
    context: CapabilityExecutionContext,
    _input: CurrentProjectAssignmentsCapabilityInput,
) -> CurrentProjectAssignmentsCapabilityOutput:
    employee = db.query(Employee).filter(Employee.id == context.principal.employee_id).first()
    if employee is None:
        raise CapabilityExecutionError("Project assignment information is temporarily unavailable.")
    try:
        observed_at, _ = local_now(db, employee)
        view = list_current_project_assignments(db, employee, observed_at.date())
    except Exception as exc:
        raise CapabilityExecutionError("Project assignment information is temporarily unavailable.") from exc
    return CurrentProjectAssignmentsCapabilityOutput(
        status=view.status.value,
        as_of=view.as_of,
        assignment_count=view.assignment_count,
        assignments=tuple(ProjectAssignmentProjection(**item.__dict__) for item in view.assignments),
        truncated=view.truncated,
        safe_warnings=view.safe_warnings,
    )


def validate_project_assignments_postconditions(
    output: CurrentProjectAssignmentsCapabilityOutput,
) -> CurrentProjectAssignmentsCapabilityOutput:
    try:
        return CurrentProjectAssignmentsCapabilityOutput.model_validate(output.model_dump(), strict=True)
    except Exception as exc:
        raise CapabilityResultInvalidError("The project assignment result failed validation.") from exc


def validate_project_assignments_result(
    output: CurrentProjectAssignmentsCapabilityOutput,
) -> ValidatedCapabilityResult[CurrentProjectAssignmentsCapabilityOutput]:
    validated = validate_project_assignments_postconditions(output)
    reference = CapabilityResultReference(
        result_reference_id="res_" + secrets.token_urlsafe(18),
        capability_id=PROJECT_ASSIGNMENTS_CAPABILITY_ID,
        capability_version=PROJECT_ASSIGNMENTS_CAPABILITY_VERSION,
        retrieved_at=datetime.combine(validated.as_of, datetime.min.time(), tzinfo=timezone.utc),
        freshness=Freshness.FRESH,
        source_service="app.services.project_assignment_service.list_current_project_assignments",
        data_classification=DataClassification.INTERNAL,
        validation_status=ResultValidationStatus.VALID,
    )
    return ValidatedCapabilityResult[CurrentProjectAssignmentsCapabilityOutput](
        reference=reference,
        availability=ResultAvailability.AVAILABLE,
        output=validated,
        permitted_field_paths=(
            "status", "as_of", "assignment_count", "truncated",
            "assignments.*.project_name", "assignments.*.project_code",
            "assignments.*.project_status", "assignments.*.allocation_role",
            "assignments.*.allocation_percentage", "assignments.*.allocation_start_date",
            "assignments.*.allocation_end_date", "assignments.*.project_manager_name",
            "safe_warnings.*",
        ),
        safe_warnings=validated.safe_warnings,
    )
