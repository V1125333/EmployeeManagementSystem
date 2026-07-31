"""Typed, owner-scoped, read-only tools for leave request history and status."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.leave_balance_tool import AIToolException
from app.core.authentication import (
    AuthenticatedPrincipal,
    LEAVE_REQUEST_SELF_PERMISSION,
)
from app.models.employee import Employee
from app.schemas.ai import (
    AIToolError,
    ExplainMyLeaveDecisionInput,
    ExplainMyLeaveDecisionOutput,
    GetMyLeaveRequestDetailsInput,
    GetMyLeaveRequestStatusInput,
    GetMyRecentLeaveRequestsInput,
    LeaveRequestToolItem,
    MyLeaveRequestDetailsOutput,
    MyLeaveRequestListOutput,
    MyLeaveRequestStatusOutput,
)
from app.schemas.leave import MyLeaveRequestQuery
from app.services.leave_service import (
    LeaveServiceError,
    get_my_leave_request_by_id,
    list_my_leave_requests,
)


def _employee(db: Session, principal: AuthenticatedPrincipal) -> Employee:
    if not principal.has_permission(LEAVE_REQUEST_SELF_PERMISSION):
        raise AIToolException(
            AIToolError(
                code="PERMISSION_DENIED",
                message="You do not have permission to view leave requests.",
            )
        )
    employee = db.query(Employee).filter(Employee.id == principal.employee_id).first()
    if not employee:
        raise AIToolException(
            AIToolError(
                code="TOOL_UNAVAILABLE",
                message="Your leave requests are temporarily unavailable.",
            )
        )
    return employee


def _item(request, as_of: datetime) -> LeaveRequestToolItem:
    pending_duration = None
    if request.status in {"submitted", "pending"}:
        pending_duration = max((as_of.date() - request.created_at.date()).days, 0)
    return LeaveRequestToolItem(
        request_id=request.id,
        leave_type=request.leave_type,
        start_date=request.start_date,
        end_date=request.end_date,
        total_days=request.total_days,
        status=request.status,
        reason=request.reason,
        submitted_at=request.created_at,
        approver=request.pending_with,
        pending_duration_days=pending_duration,
        decided_by=request.reviewed_by,
        decided_at=request.reviewed_at,
        decision_reason=request.reviewer_notes,
    )


def _service_error(exc: LeaveServiceError) -> AIToolException:
    code = (
        "UNSUPPORTED_LEAVE_TYPE"
        if exc.code == "LEAVE_TYPE_NOT_FOUND"
        else "LEAVE_REQUEST_NOT_FOUND"
    )
    return AIToolException(AIToolError(code=code, message=exc.message))


def get_my_recent_leave_requests(
    db: Session,
    principal: AuthenticatedPrincipal,
    tool_input: GetMyRecentLeaveRequestsInput,
) -> MyLeaveRequestListOutput:
    employee = _employee(db, principal)
    try:
        snapshot = list_my_leave_requests(
            db,
            employee,
            MyLeaveRequestQuery(
                statuses=tool_input.statuses,
                leave_type=tool_input.leave_type,
                on_date=tool_input.on_date,
                limit=tool_input.limit,
            ),
        )
    except LeaveServiceError as exc:
        raise _service_error(exc) from exc
    return MyLeaveRequestListOutput(
        as_of=snapshot.as_of,
        requests=[_item(item, snapshot.as_of) for item in snapshot.requests],
        total_matches=snapshot.total_matches,
    )


def _resolve_one(
    db: Session,
    principal: AuthenticatedPrincipal,
    tool_input: GetMyLeaveRequestStatusInput,
) -> tuple[LeaveRequestToolItem, datetime]:
    employee = _employee(db, principal)
    if tool_input.request_id:
        try:
            snapshot = get_my_leave_request_by_id(
                db, employee, tool_input.request_id
            )
        except LeaveServiceError as exc:
            raise _service_error(exc) from exc
        return _item(snapshot.request, snapshot.as_of), snapshot.as_of

    try:
        matches = list_my_leave_requests(
            db,
            employee,
            MyLeaveRequestQuery(
                statuses=[tool_input.status] if tool_input.status else [],
                leave_type=tool_input.leave_type,
                on_date=tool_input.on_date,
                limit=25,
            ),
        )
    except LeaveServiceError as exc:
        raise _service_error(exc) from exc
    if not matches.requests:
        raise AIToolException(
            AIToolError(
                code="LEAVE_REQUEST_NOT_FOUND",
                message="I could not find a matching leave request in your records.",
            )
        )
    if len(matches.requests) > 1 and not tool_input.latest:
        raise AIToolException(
            AIToolError(
                code="AMBIGUOUS_LEAVE_REQUEST",
                message="More than one of your leave requests matches.",
                details={
                    "candidates": [
                        _item(item, matches.as_of).model_dump(mode="json")
                        for item in matches.requests[:5]
                    ]
                },
            )
        )
    return _item(matches.requests[0], matches.as_of), matches.as_of


def get_my_leave_request_status(
    db: Session,
    principal: AuthenticatedPrincipal,
    tool_input: GetMyLeaveRequestStatusInput,
) -> MyLeaveRequestStatusOutput:
    item, as_of = _resolve_one(db, principal, tool_input)
    return MyLeaveRequestStatusOutput(as_of=as_of, request=item)


def get_my_leave_request_details(
    db: Session,
    principal: AuthenticatedPrincipal,
    tool_input: GetMyLeaveRequestDetailsInput,
) -> MyLeaveRequestDetailsOutput:
    item, as_of = _resolve_one(
        db, principal, GetMyLeaveRequestStatusInput(**tool_input.model_dump())
    )
    return MyLeaveRequestDetailsOutput(as_of=as_of, request=item)


def explain_my_leave_decision(
    db: Session,
    principal: AuthenticatedPrincipal,
    tool_input: ExplainMyLeaveDecisionInput,
) -> ExplainMyLeaveDecisionOutput:
    item, as_of = _resolve_one(
        db, principal, GetMyLeaveRequestStatusInput(**tool_input.model_dump())
    )
    if item.status == "rejected":
        explanation = (
            item.decision_reason
            if item.decision_reason
            else "No rejection reason was recorded."
        )
    elif item.status == "approved":
        explanation = (
            item.decision_reason
            if item.decision_reason
            else "The request was approved, but no decision note was recorded."
        )
    else:
        explanation = (
            f"This request is officially {item.status}; no final approval or "
            "rejection reason is available."
        )
    return ExplainMyLeaveDecisionOutput(
        as_of=as_of,
        request=item,
        explanation=explanation,
        reason_recorded=bool(item.decision_reason),
    )
