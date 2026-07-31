"""Self-scoped, read-only leave balance tool."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.authentication import (
    AuthenticatedPrincipal,
    LEAVE_BALANCE_SELF_PERMISSION,
)
from app.core.config import settings
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveType
from app.schemas.ai import (
    AIToolError,
    GetMyLeaveBalanceInput,
    GetMyLeaveBalanceOutput,
    LeaveBalanceToolItem,
)
from app.services.leave_service import (
    get_my_leave_balances,
    leave_type_applies_to_employee,
)


@dataclass
class AIToolException(Exception):
    error: AIToolError

    def __str__(self) -> str:
        return self.error.message


def _normalized(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _matches(leave_type: LeaveType, requested: str) -> bool:
    candidate = _normalized(requested)
    name = _normalized(leave_type.name)
    code = _normalized(leave_type.code)
    aliases = {
        "casual": "casual leave",
        "sick": "sick leave",
        "earned": "earned leave",
        "comp off": "compensatory off",
        "compensatory": "compensatory off",
        "lop": "loss of pay",
        "optional": "optional holiday",
        "floating": "floating holiday",
    }
    candidate = aliases.get(candidate, candidate)
    return candidate in {name, code} or candidate == name.removesuffix(" leave")


def get_my_leave_balance(
    db: Session,
    principal: AuthenticatedPrincipal,
    tool_input: GetMyLeaveBalanceInput,
) -> GetMyLeaveBalanceOutput:
    if not principal.has_permission(LEAVE_BALANCE_SELF_PERMISSION):
        raise AIToolException(
            AIToolError(code="PERMISSION_DENIED", message="You do not have permission to view this balance.")
        )

    employee = db.query(Employee).filter(Employee.id == principal.employee_id).first()
    if not employee:
        raise AIToolException(
            AIToolError(code="TOOL_UNAVAILABLE", message="Your leave balance is temporarily unavailable.")
        )

    requested_type: LeaveType | None = None
    if tool_input.leave_type:
        all_types = db.query(LeaveType).filter(LeaveType.is_active == True).all()
        requested_type = next(
            (item for item in all_types if _matches(item, tool_input.leave_type or "")),
            None,
        )
        if not requested_type:
            raise AIToolException(
                AIToolError(
                    code="UNSUPPORTED_LEAVE_TYPE",
                    message=f"'{tool_input.leave_type}' is not a supported leave type.",
                )
            )
        if not leave_type_applies_to_employee(requested_type, employee):
            raise AIToolException(
                AIToolError(
                    code="LEAVE_TYPE_NOT_APPLICABLE",
                    message=f"{requested_type.name} does not apply to your profile.",
                )
            )
        has_stored_balance = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.leave_type_id == requested_type.id,
        ).first()
        missing_policy = (
            requested_type.default_days_per_year is None
            or (
                float(requested_type.default_days_per_year or 0) <= 0
                and bool(requested_type.is_paid)
                and (requested_type.code or "").upper() not in {"CO"}
            )
        )
        if missing_policy and not has_stored_balance:
            raise AIToolException(
                AIToolError(
                    code="MISSING_POLICY_CONFIGURATION",
                    message=f"{requested_type.name} is not configured for the current policy year.",
                )
            )

    snapshot = get_my_leave_balances(db, employee)
    balances = snapshot.balances
    if requested_type:
        balances = [item for item in balances if item.leave_type_id == requested_type.id]
        if not balances:
            raise AIToolException(
                AIToolError(
                    code="MISSING_BALANCE_RECORD",
                    message=f"No effective {requested_type.name} balance is available.",
                )
            )

    if len(balances) > settings.AI_CHAT_MAX_BALANCES:
        balances = balances[: settings.AI_CHAT_MAX_BALANCES]
    return GetMyLeaveBalanceOutput(
        as_of=snapshot.as_of,
        year=snapshot.year,
        balances=[
            LeaveBalanceToolItem(
                leave_type=item.type,
                code=item.code,
                total=item.total,
                available=item.available,
                used=item.used,
                pending=item.pending,
                source=item.source,
            )
            for item in balances
        ],
    )
