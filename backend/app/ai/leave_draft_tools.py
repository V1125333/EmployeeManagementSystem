"""Typed, principal-scoped tools for AI leave draft preparation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.leave_balance_tool import AIToolException
from app.core.authentication import (
    AuthenticatedPrincipal,
    LEAVE_PREPARE_SELF_PERMISSION,
)
from app.models.employee import Employee
from app.schemas.ai import (
    AIToolError,
    DiscardMyLeaveRequestDraftInput,
    GetMyLeaveRequestDraftInput,
    LeaveRequestDraftOutput,
    PrepareMyLeaveRequestInput,
    UpdateMyLeaveRequestDraftInput,
)
from app.services.leave_draft_service import (
    LeaveDraftError,
    discard_my_leave_request_draft as discard_draft,
    get_my_leave_request_draft as get_draft,
    prepare_my_leave_request as prepare_draft,
)


@dataclass(frozen=True)
class TrustedDraftReference:
    draft_id: str
    version: int


def _authorized_employee(
    db: Session, principal: AuthenticatedPrincipal
) -> Employee:
    if not principal.has_permission(LEAVE_PREPARE_SELF_PERMISSION):
        raise AIToolException(
            AIToolError(
                code="PERMISSION_DENIED",
                message="You do not have permission to prepare leave requests.",
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
    return employee


def _translate(exc: LeaveDraftError) -> AIToolException:
    known = {
        "UNSUPPORTED_LEAVE_TYPE",
        "INVALID_DATE_RANGE",
        "INVALID_REASON",
        "DRAFT_NOT_FOUND",
        "DRAFT_EXPIRED",
        "DRAFT_VERSION_CONFLICT",
        "PERMISSION_DENIED",
    }
    code = exc.code if exc.code in known else "INVALID_TOOL_INPUT"
    return AIToolException(
        AIToolError(code=code, message=exc.message, details=exc.details or {})
    )


def prepare_my_leave_request(
    db: Session,
    principal: AuthenticatedPrincipal,
    payload: PrepareMyLeaveRequestInput,
    *,
    correlation_id: str,
    conversation_id: str | None,
) -> LeaveRequestDraftOutput:
    employee = _authorized_employee(db, principal)
    try:
        return prepare_draft(
            db,
            employee,
            payload.leave_type,
            payload.start_date,
            payload.end_date,
            payload.reason,
            correlation_id=correlation_id,
            conversation_id=conversation_id,
        )
    except LeaveDraftError as exc:
        raise _translate(exc) from exc


def get_my_leave_request_draft(
    db: Session,
    principal: AuthenticatedPrincipal,
    _payload: GetMyLeaveRequestDraftInput,
    *,
    conversation_id: str | None,
    trusted_reference: TrustedDraftReference | None = None,
) -> LeaveRequestDraftOutput:
    employee = _authorized_employee(db, principal)
    try:
        return get_draft(
            db,
            employee,
            conversation_id=conversation_id,
            draft_id=trusted_reference.draft_id if trusted_reference else None,
        )
    except LeaveDraftError as exc:
        raise _translate(exc) from exc


def update_my_leave_request_draft(
    db: Session,
    principal: AuthenticatedPrincipal,
    payload: UpdateMyLeaveRequestDraftInput,
    *,
    correlation_id: str,
    conversation_id: str | None,
    trusted_reference: TrustedDraftReference | None,
) -> LeaveRequestDraftOutput:
    employee = _authorized_employee(db, principal)
    try:
        current = (
            get_draft(
                db,
                employee,
                conversation_id=conversation_id,
                draft_id=trusted_reference.draft_id if trusted_reference else None,
            )
        )
        reason = (
            None
            if payload.remove_reason
            else payload.reason
            if payload.reason is not None
            else current.reason
        )
        return prepare_draft(
            db,
            employee,
            payload.leave_type or current.leave_type,
            payload.start_date or current.start_date,
            payload.end_date or current.end_date,
            reason,
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            draft_id=current.draft_id,
            expected_version=payload.expected_version,
            continue_to_confirmation=payload.continue_to_confirmation,
        )
    except LeaveDraftError as exc:
        raise _translate(exc) from exc


def discard_my_leave_request_draft(
    db: Session,
    principal: AuthenticatedPrincipal,
    payload: DiscardMyLeaveRequestDraftInput,
    *,
    conversation_id: str | None,
    trusted_reference: TrustedDraftReference | None,
) -> LeaveRequestDraftOutput:
    employee = _authorized_employee(db, principal)
    try:
        current = (
            get_draft(
                db,
                employee,
                conversation_id=conversation_id,
                draft_id=trusted_reference.draft_id if trusted_reference else None,
            )
        )
        return discard_draft(
            db,
            employee,
            draft_id=current.draft_id,
            expected_version=payload.expected_version,
        )
    except LeaveDraftError as exc:
        raise _translate(exc) from exc
