"""Typed, principal-scoped read-only leave eligibility tool."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.leave_balance_tool import AIToolException
from app.core.authentication import (
    AuthenticatedPrincipal,
    LEAVE_ASSESS_SELF_PERMISSION,
)
from app.models.employee import Employee
from app.schemas.ai import (
    AIToolError,
    CheckMyLeaveEligibilityInput,
    CheckMyLeaveEligibilityOutput,
)
from app.services.leave_eligibility_service import check_my_leave_eligibility as assess
from app.services.leave_service import LeaveServiceError


def check_my_leave_eligibility(
    db: Session,
    principal: AuthenticatedPrincipal,
    payload: CheckMyLeaveEligibilityInput,
) -> CheckMyLeaveEligibilityOutput:
    if not principal.has_permission(LEAVE_ASSESS_SELF_PERMISSION):
        raise AIToolException(
            AIToolError(
                code="PERMISSION_DENIED",
                message="You do not have permission to assess leave eligibility.",
            )
        )
    employee = db.query(Employee).filter(
        Employee.id == principal.employee_id,
        Employee.is_active == True,
        Employee.employment_status == "active",
    ).first()
    if not employee:
        raise AIToolException(
            AIToolError(
                code="PERMISSION_DENIED",
                message="An active employee profile is required.",
            )
        )
    try:
        result = assess(
            db,
            employee,
            payload.leave_type,
            payload.start_date,
            payload.end_date,
        )
    except LeaveServiceError as exc:
        code = (
            "UNSUPPORTED_LEAVE_TYPE"
            if exc.code == "LEAVE_TYPE_NOT_FOUND"
            else "INVALID_TOOL_INPUT"
        )
        raise AIToolException(
            AIToolError(code=code, message=exc.message, details={"field": exc.field})
        ) from exc
    return CheckMyLeaveEligibilityOutput.model_validate(
        {"tool": "check_my_leave_eligibility", **result.model_dump()}
    )
