"""Self-scoped reporting-manager capability backed by the employee directory service."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.ai_platform.authorization import AuthorizationDecision, minimize_target_reference
from app.ai_platform.contracts import ActorScope, DataClassification, PlatformContract, require_timezone_aware
from app.ai_platform.errors import CapabilityExecutionError, CapabilityResultInvalidError
from app.ai_platform.execution import CapabilityExecutionContext, ExecutionPrincipal
from app.ai_platform.result import (
    CapabilityResultReference, Freshness, ResultAvailability, ResultValidationStatus,
    ValidatedCapabilityResult,
)
from app.core.authentication import EMPLOYEE_MANAGER_SELF_PERMISSION
from app.models.employee import Employee
from app.services.employee_directory_service import get_my_reporting_manager

EMPLOYEE_MANAGER_CAPABILITY_ID = "employee.manager.read_self"
EMPLOYEE_MANAGER_CAPABILITY_VERSION = 1


class EmployeeManagerCapabilityInput(PlatformContract):
    pass


class EmployeeManagerProjection(PlatformContract):
    display_name: str = Field(min_length=1, max_length=200)
    job_title: str | None = Field(default=None, min_length=1, max_length=120)
    department: str | None = Field(default=None, min_length=1, max_length=120)
    work_email: EmailStr
    source: Literal["manager_id", "legacy_reporting_manager"]


ManagerStatus = Literal[
    "available", "not_assigned", "invalid_reference", "inactive_manager",
    "ambiguous_legacy_reference", "self_reference", "unavailable",
]


class EmployeeManagerCapabilityOutput(PlatformContract):
    status: ManagerStatus
    manager: EmployeeManagerProjection | None = None
    as_of: datetime
    safe_warnings: tuple[str, ...] = Field(default=(), max_length=4)

    @field_validator("as_of")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)

    @field_validator("safe_warnings")
    @classmethod
    def bounded_warnings(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value or len(value) > 80 or not value.replace("_", "").isalnum() for value in values):
            raise ValueError("manager warnings must be bounded safe codes")
        return values

    @model_validator(mode="after")
    def status_matches_manager(self) -> "EmployeeManagerCapabilityOutput":
        if (self.status == "available") != (self.manager is not None):
            raise ValueError("manager is present only for available results")
        return self


def authorize_employee_manager_read_self(
    db: Session, principal: ExecutionPrincipal, _input: EmployeeManagerCapabilityInput,
) -> AuthorizationDecision:
    employee = db.query(Employee).filter(Employee.id == principal.employee_id).first()
    target_hash = minimize_target_reference(principal.employee_id, salt="employee-manager-v1")
    if (
        principal.status.strip().lower() != "active" or employee is None
        or not employee.is_active or employee.employment_status != "active" or employee.account_locked
    ):
        return AuthorizationDecision.deny(
            reason_code="ACTOR_NOT_ACTIVE", evaluated_scope=ActorScope.SELF,
            policy_version="employee-manager-v1", target_reference_hash=target_hash,
            evaluated_at=datetime.now(timezone.utc),
        )
    if not principal.has_permission(EMPLOYEE_MANAGER_SELF_PERMISSION):
        return AuthorizationDecision.deny(
            reason_code="SELF_PERMISSION_MISSING", evaluated_scope=ActorScope.SELF,
            policy_version="employee-manager-v1", target_reference_hash=target_hash,
            evaluated_at=datetime.now(timezone.utc),
        )
    return AuthorizationDecision.allow(
        reason_code="SELF_PERMISSION_ALLOWED", evaluated_scope=ActorScope.SELF,
        policy_version="employee-manager-v1", target_reference_hash=target_hash,
        evaluated_at=datetime.now(timezone.utc),
    )


def execute_employee_manager_adapter(
    db: Session, context: CapabilityExecutionContext, _input: EmployeeManagerCapabilityInput,
) -> EmployeeManagerCapabilityOutput:
    employee = db.query(Employee).filter(Employee.id == context.principal.employee_id).first()
    if employee is None:
        raise CapabilityExecutionError("Manager information is temporarily unavailable.")
    try:
        view = get_my_reporting_manager(db, employee)
    except Exception as exc:
        raise CapabilityExecutionError("Manager information is temporarily unavailable.") from exc
    return EmployeeManagerCapabilityOutput(
        status=view.status.value,
        manager=(EmployeeManagerProjection(
            display_name=view.display_name, job_title=view.job_title,
            department=view.department, work_email=view.work_email, source=view.source,
        ) if view.status.value == "available" else None),
        as_of=view.as_of,
        safe_warnings=(view.safe_warning,) if view.safe_warning else (),
    )


def validate_employee_manager_postconditions(
    output: EmployeeManagerCapabilityOutput,
) -> EmployeeManagerCapabilityOutput:
    try:
        return EmployeeManagerCapabilityOutput.model_validate(output.model_dump(), strict=True)
    except Exception as exc:
        raise CapabilityResultInvalidError("The manager result failed validation.") from exc


def validate_employee_manager_result(
    output: EmployeeManagerCapabilityOutput,
) -> ValidatedCapabilityResult[EmployeeManagerCapabilityOutput]:
    validated = validate_employee_manager_postconditions(output)
    reference = CapabilityResultReference(
        result_reference_id="res_" + secrets.token_urlsafe(18),
        capability_id=EMPLOYEE_MANAGER_CAPABILITY_ID,
        capability_version=EMPLOYEE_MANAGER_CAPABILITY_VERSION,
        retrieved_at=validated.as_of, freshness=Freshness.FRESH,
        source_service="app.services.employee_directory_service.get_my_reporting_manager",
        data_classification=DataClassification.INTERNAL,
        validation_status=ResultValidationStatus.VALID,
    )
    return ValidatedCapabilityResult[EmployeeManagerCapabilityOutput](
        reference=reference, availability=ResultAvailability.AVAILABLE, output=validated,
        permitted_field_paths=(
            "status", "as_of", "manager.display_name", "manager.job_title",
            "manager.department", "manager.work_email", "manager.source", "safe_warnings.*",
        ),
        safe_warnings=validated.safe_warnings,
    )
