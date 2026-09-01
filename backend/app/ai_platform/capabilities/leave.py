"""Self-scoped adapter for the existing authoritative leave-balance tool."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.ai.leave_balance_tool import AIToolException, get_my_leave_balance
from app.ai_platform.authorization import AuthorizationDecision, minimize_target_reference
from app.ai_platform.contracts import ActorScope, DataClassification, PlatformContract, require_timezone_aware
from app.ai_platform.errors import CapabilityExecutionError, CapabilityResultInvalidError, PlatformError
from app.ai_platform.execution import CapabilityExecutionContext, ExecutionPrincipal
from app.ai_platform.result import (
    CapabilityResultReference,
    Freshness,
    ResultAvailability,
    ResultValidationStatus,
    ValidatedCapabilityResult,
)
from app.core.authentication import LEAVE_BALANCE_SELF_PERMISSION
from app.models.employee import Employee
from app.schemas.ai import GetMyLeaveBalanceInput

LEAVE_BALANCE_CAPABILITY_ID = "leave.balance.read_self"
LEAVE_BALANCE_CAPABILITY_VERSION = 1
_AUTHORIZATION_HASH_SALT = "orbit-leave-balance-v1"


class LeaveBalanceCapabilityError(PlatformError):
    """Safe adapter error retaining only the established AI error contract."""

    code = "LEAVE_BALANCE_CAPABILITY_FAILURE"

    def __init__(self, safe_message: str, *, legacy_code: str):
        super().__init__(safe_message)
        self.legacy_code = legacy_code[:64]


class LeaveBalanceCapabilityInput(PlatformContract):
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("leave_type")
    @classmethod
    def normalize_query_whitespace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("leave_type cannot be empty")
        return normalized


class LeaveBalanceCapabilityEntry(PlatformContract):
    leave_type: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    total: float = Field(ge=0, le=100_000)
    available: float | Literal["On request"]
    used: float = Field(ge=0, le=100_000)
    pending: float = Field(ge=0, le=100_000)
    source: Literal["stored_balance", "policy_default", "on_request"]
    unit: Literal["days"] = "days"

    @field_validator("available")
    @classmethod
    def nonnegative_available(cls, value: float | str) -> float | str:
        if isinstance(value, float) and (value < 0 or value > 100_000):
            raise ValueError("available balance is outside the supported range")
        return value

    @model_validator(mode="after")
    def valid_arithmetic(self) -> "LeaveBalanceCapabilityEntry":
        if self.source == "on_request":
            if self.available != "On request":
                raise ValueError("on-request leave must use the on-request balance marker")
            return self
        if not isinstance(self.available, float):
            raise ValueError("numeric leave sources require numeric availability")
        expected = round(max(self.total - self.used - self.pending, 0), 1)
        if abs(self.available - expected) > 0.05:
            raise ValueError("leave balance arithmetic is inconsistent")
        return self


class LeaveBalanceCapabilityOutput(PlatformContract):
    status: Literal["available", "unavailable"]
    as_of: datetime
    year: int = Field(ge=2000, le=2200)
    balances: tuple[LeaveBalanceCapabilityEntry, ...] = Field(default=(), max_length=20)
    warnings: tuple[str, ...] = Field(default=(), max_length=8)

    @field_validator("as_of")
    @classmethod
    def aware_as_of(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)

    @field_validator("warnings")
    @classmethod
    def bounded_warnings(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value or len(value) > 160 for value in values):
            raise ValueError("warnings must be bounded")
        return values

    @model_validator(mode="after")
    def status_matches_data(self) -> "LeaveBalanceCapabilityOutput":
        if self.status == "available" and not self.balances:
            raise ValueError("available output requires at least one balance")
        if self.status == "unavailable" and self.balances:
            raise ValueError("unavailable output cannot contain balances")
        if self.status == "unavailable" and not self.warnings:
            raise ValueError("unavailable output requires a safe warning")
        codes = [item.code.casefold() for item in self.balances]
        names = [item.leave_type.casefold() for item in self.balances]
        if len(codes) != len(set(codes)) or len(names) != len(set(names)):
            raise ValueError("duplicate leave types are not permitted")
        return self


def authorize_leave_balance_self(
    db: Session,
    principal: ExecutionPrincipal,
    _capability_input: LeaveBalanceCapabilityInput,
) -> AuthorizationDecision:
    target_hash = minimize_target_reference(
        principal.employee_id,
        salt=_AUTHORIZATION_HASH_SALT,
    )
    employee = db.query(Employee).filter(Employee.id == principal.employee_id).first()
    if (
        principal.status.strip().lower() != "active"
        or employee is None
        or not employee.is_active
        or employee.employment_status != "active"
        or employee.account_locked
    ):
        return AuthorizationDecision.deny(
            reason_code="ACTOR_NOT_ACTIVE",
            evaluated_scope=ActorScope.SELF,
            policy_version="leave-balance-v1",
            target_reference_hash=target_hash,
            evaluated_at=datetime.now(timezone.utc),
        )
    if not principal.has_permission(LEAVE_BALANCE_SELF_PERMISSION):
        return AuthorizationDecision.deny(
            reason_code="SELF_PERMISSION_MISSING",
            evaluated_scope=ActorScope.SELF,
            policy_version="leave-balance-v1",
            target_reference_hash=target_hash,
            evaluated_at=datetime.now(timezone.utc),
        )
    return AuthorizationDecision.allow(
        reason_code="SELF_PERMISSION_ALLOWED",
        evaluated_scope=ActorScope.SELF,
        policy_version="leave-balance-v1",
        target_reference_hash=target_hash,
        evaluated_at=datetime.now(timezone.utc),
    )


def execute_leave_balance_adapter(
    db: Session,
    context: CapabilityExecutionContext,
    capability_input: LeaveBalanceCapabilityInput,
) -> LeaveBalanceCapabilityOutput:
    """Invoke the existing safe tool; perform no leave calculation here."""

    try:
        legacy = get_my_leave_balance(
            db,
            context.principal,  # trusted snapshot implements the tool's required contract
            GetMyLeaveBalanceInput(leave_type=capability_input.leave_type),
        )
    except AIToolException as exc:
        raise LeaveBalanceCapabilityError(
            exc.error.message,
            legacy_code=exc.error.code,
        ) from exc
    except Exception as exc:
        raise CapabilityExecutionError(
            "The leave-balance service is temporarily unavailable."
        ) from exc

    as_of = legacy.as_of
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    balances = tuple(
        LeaveBalanceCapabilityEntry(
            leave_type=item.leave_type,
            code=item.code,
            total=item.total,
            available=item.available,
            used=item.used,
            pending=item.pending,
            source=item.source,
        )
        for item in legacy.balances
    )
    return LeaveBalanceCapabilityOutput(
        status="available" if balances else "unavailable",
        as_of=as_of,
        year=legacy.year,
        balances=balances,
        warnings=() if balances else ("No leave balances are currently available.",),
    )


def validate_leave_balance_postconditions(
    output: LeaveBalanceCapabilityOutput,
) -> LeaveBalanceCapabilityOutput:
    try:
        return LeaveBalanceCapabilityOutput.model_validate(output.model_dump(), strict=True)
    except Exception as exc:
        raise CapabilityResultInvalidError(
            "The leave-balance result failed validation."
        ) from exc


def validate_leave_balance_result(
    output: LeaveBalanceCapabilityOutput,
) -> ValidatedCapabilityResult[LeaveBalanceCapabilityOutput]:
    validated = validate_leave_balance_postconditions(output)
    reference = CapabilityResultReference(
        result_reference_id="res_" + secrets.token_urlsafe(18),
        capability_id=LEAVE_BALANCE_CAPABILITY_ID,
        capability_version=LEAVE_BALANCE_CAPABILITY_VERSION,
        retrieved_at=validated.as_of,
        freshness=Freshness.FRESH if validated.status == "available" else Freshness.UNAVAILABLE,
        source_service="app.ai.leave_balance_tool.get_my_leave_balance",
        data_classification=DataClassification.CONFIDENTIAL,
        validation_status=ResultValidationStatus.VALID,
    )
    return ValidatedCapabilityResult[LeaveBalanceCapabilityOutput](
        reference=reference,
        availability=(
            ResultAvailability.AVAILABLE
            if validated.status == "available"
            else ResultAvailability.UNAVAILABLE
        ),
        output=validated if validated.status == "available" else None,
        permitted_field_paths=(
            "status", "as_of", "year", "balances.*.leave_type",
            "balances.*.code", "balances.*.total", "balances.*.available",
            "balances.*.used", "balances.*.pending", "balances.*.source",
            "balances.*.unit", "warnings.*",
        ),
        safe_warnings=validated.warnings,
    )
