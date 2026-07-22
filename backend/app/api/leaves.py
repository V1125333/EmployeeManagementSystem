"""Employee leave request, assessment, and approval endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.schemas.leave import (
    LeaveAssessmentInput,
    LeaveContextResponse,
    LeaveDecisionInput,
    LeaveEligibilityResponse,
    LeaveRequestInput,
    LeaveSubmissionInput,
    OwnerScopedLeaveRequestStatus,
    StructuredErrorResponse,
    SubmittedLeaveResult,
)
from app.services.audit_service import log_audit, log_authorization_failure
from app.services.leave_service import (
    LeaveServiceError,
    create_my_leave_request as create_leave,
    decimal_to_float,
    delete_my_leave_draft,
    employee_name,
    get_my_leave_context,
    get_my_leave_request_by_id,
    provision_leave_balance,
    assess_my_leave_request,
    serialize_leave_request,
    submit_my_leave_request,
    update_my_leave_request as update_leave,
    withdraw_my_leave_request as withdraw_leave,
)
from app.services.settings_service import get_current_employee


router = APIRouter(prefix="/leaves", tags=["Leaves"])
ERROR_RESPONSES = {
    400: {"model": StructuredErrorResponse},
    403: {"model": StructuredErrorResponse},
    404: {"model": StructuredErrorResponse},
    409: {"model": StructuredErrorResponse},
}


def _employee(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    return get_current_employee(db, user_id, user_email)


def _raise_http(error: LeaveServiceError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={
            "code": error.code,
            "message": error.message,
            "field": error.field,
            "details": error.details,
        },
    )


def _legacy_summary(context: LeaveContextResponse) -> dict:
    """Keep the established frontend response while canonical contracts evolve."""
    data = context.model_dump(mode="json")
    data.pop("as_of", None)
    for balance in data["balances"]:
        balance.pop("initialized", None)
        policy = balance.get("date_policy") or {}
        balance["date_policy"] = {
            "allow_future_dates": policy.get("allow_future_dates"),
            "past_date_limit_days": policy.get("past_date_limit_days"),
            "future_date_warning": policy.get("future_date_warning"),
        }
    return data


def _is_admin(role: str | None) -> bool:
    normalized = (role or "").lower().replace(" ", "_")
    return normalized in {"super_admin", "admin", "hr_admin", "global_access"}


@router.get("/me/context", response_model=LeaveContextResponse)
async def my_leave_context(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    return get_my_leave_context(db, _employee(db, x_user_id, x_user_email))


@router.post("/me/assess", response_model=LeaveEligibilityResponse, responses=ERROR_RESPONSES)
async def assess_leave_request(
    payload: LeaveAssessmentInput,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    try:
        return assess_my_leave_request(db, _employee(db, x_user_id, x_user_email), payload)
    except LeaveServiceError as error:
        _raise_http(error)


@router.post(
    "/me/submissions",
    response_model=SubmittedLeaveResult,
    status_code=201,
    responses=ERROR_RESPONSES,
)
async def submit_leave_request(
    payload: LeaveSubmissionInput,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None),
):
    try:
        return submit_my_leave_request(
            db,
            _employee(db, x_user_id, x_user_email),
            LeaveRequestInput(**payload.model_dump(), action="submit"),
            correlation_id=x_correlation_id,
        )
    except LeaveServiceError as error:
        _raise_http(error)


@router.get(
    "/me/requests/{request_id}/status",
    response_model=OwnerScopedLeaveRequestStatus,
    responses=ERROR_RESPONSES,
)
async def my_leave_request_status(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    try:
        return get_my_leave_request_by_id(
            db, _employee(db, x_user_id, x_user_email), request_id
        )
    except LeaveServiceError as error:
        _raise_http(error)


@router.get("/me/summary")
async def my_leave_summary(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    context = get_my_leave_context(db, _employee(db, x_user_id, x_user_email))
    return _legacy_summary(context)


@router.post("/me/requests")
async def create_my_leave_request(
    payload: LeaveRequestInput,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = _employee(db, x_user_id, x_user_email)
    try:
        create_leave(db, employee, payload)
        return _legacy_summary(get_my_leave_context(db, employee))
    except LeaveServiceError as error:
        _raise_http(error)


@router.put("/me/requests/{request_id}")
async def update_my_leave_request(
    request_id: str,
    payload: LeaveRequestInput,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = _employee(db, x_user_id, x_user_email)
    try:
        update_leave(db, employee, request_id, payload)
        return _legacy_summary(get_my_leave_context(db, employee))
    except LeaveServiceError as error:
        _raise_http(error)


@router.delete("/me/requests/{request_id}")
async def delete_my_leave_request(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = _employee(db, x_user_id, x_user_email)
    try:
        delete_my_leave_draft(db, employee, request_id)
        return _legacy_summary(get_my_leave_context(db, employee))
    except LeaveServiceError as error:
        _raise_http(error)


@router.post("/me/requests/{request_id}/withdraw")
async def withdraw_my_leave_request(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = _employee(db, x_user_id, x_user_email)
    try:
        withdraw_leave(db, employee, request_id)
        return _legacy_summary(get_my_leave_context(db, employee))
    except LeaveServiceError as error:
        _raise_http(error)


@router.get("/approvals")
async def leave_approvals(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    reviewer = _employee(db, x_user_id, x_user_email)
    query = db.query(LeaveRequest, LeaveType, Employee).join(
        LeaveType, LeaveType.id == LeaveRequest.leave_type_id
    ).join(Employee, Employee.id == LeaveRequest.employee_id).filter(
        LeaveRequest.status == "pending"
    )
    if not _is_admin(reviewer.role):
        query = query.filter(Employee.reporting_manager == employee_name(reviewer))
    rows = query.order_by(LeaveRequest.created_at.asc()).all()
    return {
        "approvals": [
            serialize_leave_request(
                db, request, leave_type=leave_type, employee=employee
            ).model_dump(mode="json")
            for request, leave_type, employee in rows
        ]
    }


@router.post("/approvals/{request_id}/decision")
async def decide_leave_request(
    request_id: str,
    payload: LeaveDecisionInput,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    reviewer = _employee(db, x_user_id, x_user_email)
    request = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be reviewed.")
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if employee.id == reviewer.id:
        log_authorization_failure(
            db, reviewer, "leave.approval", "leave_request", request.id,
            "Reviewer attempted to approve their own leave request.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="You cannot review your own leave request.")
    if not _is_admin(reviewer.role) and employee.reporting_manager != employee_name(reviewer):
        log_authorization_failure(
            db, reviewer, "leave.approval", "leave_request", request.id,
            "Reviewer is not the employee manager or admin.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Not authorized to review this leave request.")

    now = datetime.utcnow()
    old_values = {
        "status": request.status,
        "reviewed_by": request.reviewed_by,
        "reviewed_at": request.reviewed_at,
    }
    request.status = "approved" if payload.decision == "approve" else "rejected"
    request.reviewed_by = reviewer.id
    request.reviewed_at = now
    request.reviewer_notes = payload.reviewer_notes
    request.updated_at = now
    if payload.decision == "approve":
        leave_type = db.query(LeaveType).filter(LeaveType.id == request.leave_type_id).first()
        if leave_type:
            balance = provision_leave_balance(
                db, request.employee_id, leave_type, request.start_date.year
            )
            balance.used_days = decimal_to_float(balance.used_days) + decimal_to_float(request.total_days)
            balance.updated_at = now
    log_audit(
        db,
        reviewer,
        action="leave.approved" if payload.decision == "approve" else "leave.rejected",
        entity_type="leave_request",
        entity_id=request.id,
        old_values=old_values,
        new_values={
            "status": request.status,
            "reviewed_by": request.reviewed_by,
            "reviewed_at": request.reviewed_at,
            "reviewer_notes": request.reviewer_notes,
        },
        reason=payload.reviewer_notes,
        metadata={"employee_id": employee.id, "employee_name": employee_name(employee)},
    )
    db.commit()
    return await leave_approvals(db, x_user_id, x_user_email)
