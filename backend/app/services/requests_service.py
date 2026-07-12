from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest
from app.models.operations import ActionInboxItem, Notification
from app.models.requests import EmployeeRequest, RequestAttachment, RequestComment, RequestStatusHistory, RequestTicketCounter
from app.schemas.requests import CommentSchema, ReassignSchema, RequestCreateSchema, RequestUpdateSchema
from app.services.audit_service import log_audit, log_authorization_failure
from app.services.settings_service import is_admin_role, normalize_role

REQUEST_TYPES = {
    "wfh": "Work From Home",
    "short_permission": "Short Permission",
    "overtime": "Overtime",
    "expense": "Expense Reimbursement",
}


@dataclass(frozen=True)
class RequestPolicy:
    request_type: str
    label: str
    allow_past_dates: bool
    allow_future_dates: bool
    allow_today: bool = True
    maximum_past_days: int | None = None
    maximum_future_days: int | None = None
    allow_dates_before_joining: bool = False
    maximum_pre_joining_days: int | None = None
    requires_manager_approval: bool = True
    requires_hr_approval: bool = False
    requires_finance_approval: bool = False
    requires_attachment: bool = False
    requires_comments: bool = True
    maximum_attachment_size: int = 10 * 1024 * 1024
    accepted_file_types: tuple[str, ...] = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".doc", ".docx")
    invalid_past_message: str = "This request type cannot be created for past dates."
    invalid_future_message: str = "This request type cannot be created for future dates."
    past_window_message: str = "Selected date is outside the allowed request period."
    future_window_message: str = "Selected date is outside the allowed future request period."
    pre_joining_message: str = "Selected date is outside the allowed pre-joining request period."


REQUEST_POLICIES: dict[str, RequestPolicy] = {
    "wfh": RequestPolicy(
        request_type="wfh",
        label="Work From Home",
        allow_past_dates=False,
        allow_future_dates=True,
        maximum_future_days=None,
        invalid_past_message="Work From Home requests cannot be created for past dates.",
    ),
    "short_permission": RequestPolicy(
        request_type="short_permission",
        label="Short Permission",
        allow_past_dates=False,
        allow_future_dates=True,
        maximum_future_days=None,
        invalid_past_message="Short permission cannot be requested for a past date.",
    ),
    "overtime": RequestPolicy(
        request_type="overtime",
        label="Overtime",
        allow_past_dates=True,
        allow_future_dates=False,
        allow_today=False,
        maximum_past_days=30,
        invalid_future_message="Overtime claims can only be submitted after the work is completed.",
        past_window_message="Overtime must be submitted within 30 days of the work date.",
    ),
    "expense": RequestPolicy(
        request_type="expense",
        label="Expense Reimbursement",
        allow_past_dates=True,
        allow_future_dates=False,
        maximum_past_days=90,
        allow_dates_before_joining=True,
        maximum_pre_joining_days=14,
        requires_hr_approval=True,
        requires_attachment=settings.REQUESTS_EXPENSE_RECEIPT_REQUIRED,
        invalid_future_message="Expense reimbursement cannot be created for a future expense date.",
        past_window_message="Expense reimbursement must be submitted within 90 days of the expense date.",
        pre_joining_message="Selected date is outside the allowed reimbursement period.",
    ),
}

_TICKET_PREFIX = {
    "wfh": "WFH",
    "short_permission": "SP",
    "overtime": "OT",
    "expense": "EXP",
}

STATUSES = {"draft", "pending", "approved", "rejected", "cancelled", "paid"}
REVIEWER_ROLES = {"manager", "super_admin", "admin", "hr_admin", "global_access"}
HR_ADMIN_ROLES = {"super_admin", "admin", "hr_admin", "global_access"}


def utc_now() -> datetime:
    return datetime.utcnow()


def _decimal(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _time_diff_minutes(start_time, end_time) -> int:
    start = start_time.hour * 60 + start_time.minute
    end = end_time.hour * 60 + end_time.minute
    minutes = end - start
    if minutes <= 0:
        raise HTTPException(status_code=400, detail="End time must be after start time.")
    return minutes


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown"
    parts = [employee.first_name, getattr(employee, "middle_name", None), employee.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip()) or employee.work_email


def _name_key(value: str | None) -> str:
    return " ".join((value or "").lower().replace(",", " ").split())


def find_employee(db: Session, employee_id: str | None) -> Employee | None:
    if not employee_id:
        return None
    return db.query(Employee).filter(Employee.id == employee_id).first()


def _is_admin(actor: Employee) -> bool:
    return is_admin_role(actor.role) or normalize_role(actor.role) in HR_ADMIN_ROLES


def _can_pay_expenses(actor: Employee) -> bool:
    return normalize_role(actor.role) in {"hr_admin", "super_admin"}


def _is_reviewer(actor: Employee) -> bool:
    return normalize_role(actor.role) in REVIEWER_ROLES


def _is_direct_report(actor: Employee, employee: Employee | None) -> bool:
    if not employee or employee.id == actor.id:
        return False
    if employee.manager_id == actor.id:
        return True
    manager_ref = _name_key(employee.reporting_manager)
    return bool(manager_ref and manager_ref in {_name_key(employee_name(actor)), _name_key(actor.work_email)})


def _manager_for_employee(db: Session, employee: Employee) -> Employee | None:
    manager = find_employee(db, employee.manager_id)
    if manager and manager.id != employee.id:
        return manager
    manager_ref = _name_key(employee.reporting_manager)
    if manager_ref:
        managers = db.query(Employee).filter(Employee.id != employee.id).all()
        for candidate in managers:
            if manager_ref in {_name_key(employee_name(candidate)), _name_key(candidate.work_email)}:
                return candidate
    return None


def _ensure_employee_can_submit_hr_request(db: Session, employee: Employee) -> Employee:
    if not employee.is_active or employee.employment_status != "active":
        raise HTTPException(status_code=400, detail="Only active employees can submit requests.")
    manager = _manager_for_employee(db, employee)
    if not manager:
        raise HTTPException(status_code=400, detail="No Reporting Manager has been assigned. Please contact HR.")
    return manager


def _hr_admins(db: Session) -> list[Employee]:
    rows = db.query(Employee).all()
    return [row for row in rows if normalize_role(row.role) in HR_ADMIN_ROLES]


def _generate_ticket_number(db: Session, request_type: str) -> str:
    prefix = _TICKET_PREFIX.get(request_type, "REQ")
    year = utc_now().year
    counter = (
        db.query(RequestTicketCounter)
        .filter(RequestTicketCounter.prefix == prefix, RequestTicketCounter.year == year)
        .with_for_update()
        .first()
    )
    if not counter:
        counter = RequestTicketCounter(prefix=prefix, year=year, last_value=0)
        db.add(counter)
        db.flush()
    counter.last_value += 1
    db.flush()
    return f"{prefix}-{year}-{counter.last_value:06d}"


def _request_owner(db: Session, request: EmployeeRequest) -> Employee | None:
    return find_employee(db, request.employee_id)


def _can_read(db: Session, actor: Employee, request: EmployeeRequest) -> bool:
    owner = _request_owner(db, request)
    return (
        request.employee_id == actor.id
        or request.current_owner_id == actor.id
        or request.reviewed_by_id == actor.id
        or _is_admin(actor)
        or _is_direct_report(actor, owner)
    )


def ensure_read_access(db: Session, actor: Employee, request: EmployeeRequest) -> None:
    if _can_read(db, actor, request):
        return
    log_authorization_failure(db, actor, "request.read", "employee_request", request.id)
    db.commit()
    raise HTTPException(status_code=403, detail="Not authorized to view this request.")


def _can_review(db: Session, actor: Employee, request: EmployeeRequest) -> bool:
    owner = _request_owner(db, request)
    if request.employee_id == actor.id:
        return False
    return _is_admin(actor) or request.current_owner_id == actor.id or (_is_reviewer(actor) and _is_direct_report(actor, owner))


def _ensure_review_access(db: Session, actor: Employee, request: EmployeeRequest) -> None:
    if _can_review(db, actor, request):
        return
    log_authorization_failure(db, actor, "request.review", "employee_request", request.id)
    db.commit()
    raise HTTPException(status_code=403, detail="Not authorized to review this request.")


def _snapshot(row: EmployeeRequest) -> dict[str, Any]:
    return {
        "status": row.status,
        "ticket_number": row.ticket_number,
        "current_owner_id": row.current_owner_id,
        "submitted_to_id": row.submitted_to_id,
        "request_type": row.request_type,
        "title": row.title,
        "wfh_from_date": row.wfh_from_date,
        "wfh_to_date": row.wfh_to_date,
        "wfh_reason": row.wfh_reason,
        "sp_date": row.sp_date,
        "sp_start_time": row.sp_start_time.isoformat() if row.sp_start_time else None,
        "sp_end_time": row.sp_end_time.isoformat() if row.sp_end_time else None,
        "ot_date": row.ot_date,
        "ot_start_time": row.ot_start_time.isoformat() if row.ot_start_time else None,
        "ot_end_time": row.ot_end_time.isoformat() if row.ot_end_time else None,
        "ot_project_id": row.ot_project_id,
        "exp_date": row.exp_date,
        "exp_category": row.exp_category,
        "exp_amount": _decimal(row.exp_amount),
        "exp_currency": row.exp_currency,
    }


def _transition(
    db: Session,
    row: EmployeeRequest,
    actor: Employee,
    to_status: str,
    action: str,
    reason: str | None = None,
    notes: str | None = None,
) -> None:
    if to_status not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid request status.")
    old_status = row.status
    row.status = to_status
    row.updated_by = actor.id
    row.updated_at = utc_now()
    if to_status == "pending":
        row.submitted_at = row.submitted_at or utc_now()
    if to_status in {"approved", "rejected"}:
        row.reviewed_by_id = actor.id
        row.reviewed_at = utc_now()
        row.reviewer_notes = notes or reason
    db.add(RequestStatusHistory(
        request_id=row.id,
        from_status=old_status,
        to_status=to_status,
        changed_by_id=actor.id,
        reason=reason or notes,
    ))
    log_audit(
        db,
        actor,
        action,
        "employee_request",
        row.id,
        old_values={"status": old_status},
        new_values={"status": to_status},
        reason=reason,
        metadata={**({"reviewer_notes": notes} if notes else {}), "ticket_number": row.ticket_number},
    )


def _notify(db: Session, user_id: str | None, title: str, message: str, request_id: str) -> None:
    if not user_id:
        return
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        type="request",
        notification_type="employee_request",
        related_entity_type="employee_request",
        related_entity_id=request_id,
        link_url=f"/requests/{request_id}",
    ))


def _inbox(db: Session, user_id: str | None, title: str, description: str, request_id: str) -> None:
    if not user_id:
        return
    db.add(ActionInboxItem(
        assigned_to_user_id=user_id,
        item_type="employee_request",
        title=title,
        description=description,
        related_entity_type="employee_request",
        related_entity_id=request_id,
        priority="normal",
    ))


def _clear_inbox(db: Session, request_id: str) -> None:
    db.query(ActionInboxItem).filter(
        ActionInboxItem.related_entity_type == "employee_request",
        ActionInboxItem.related_entity_id == request_id,
        ActionInboxItem.status == "pending",
    ).update({"status": "completed", "updated_at": utc_now()}, synchronize_session=False)


def _notify_approvers(db: Session, row: EmployeeRequest, employee: Employee) -> None:
    recipients: dict[str, Employee] = {}
    current_owner = find_employee(db, row.current_owner_id)
    if current_owner:
        recipients[current_owner.id] = current_owner
    elif row.status == "pending":
        for admin in _hr_admins(db):
            if admin.id != employee.id:
                recipients[admin.id] = admin
    for recipient in recipients.values():
        _notify(
            db,
            recipient.id,
            "Request awaiting approval",
            f"{employee_name(employee)} submitted {REQUEST_TYPES[row.request_type]} ({row.ticket_number or row.id}).",
            row.id,
        )
        _inbox(
            db,
            recipient.id,
            f"{REQUEST_TYPES[row.request_type]} approval",
            f"{employee_name(employee)} submitted {row.ticket_number or 'a request'} for review.",
            row.id,
        )


def _notify_employee(db: Session, row: EmployeeRequest, reviewer: Employee, status: str) -> None:
    _notify(
        db,
        row.employee_id,
        f"Request {status}",
        f"Your {REQUEST_TYPES[row.request_type]} request {row.ticket_number or ''} was {status} by {employee_name(reviewer)}.".strip(),
        row.id,
    )


def _notify_expense_paid(db: Session, row: EmployeeRequest) -> None:
    _notify(
        db,
        row.employee_id,
        "Expense reimbursement processed",
        f"Your expense reimbursement request {row.ticket_number or ''} has been processed.".strip(),
        row.id,
    )


def _serialize_policy(policy: RequestPolicy, employee: Employee | None = None) -> dict[str, Any]:
    data = asdict(policy)
    data["accepted_file_types"] = list(policy.accepted_file_types)
    min_date, max_date = _policy_bounds(policy, employee)
    data["min_date"] = min_date
    data["max_date"] = max_date
    return data


def _reason(row: EmployeeRequest) -> str | None:
    if row.request_type == "wfh":
        return row.wfh_reason
    if row.request_type == "short_permission":
        return row.sp_reason
    if row.request_type == "overtime":
        return row.ot_reason
    if row.request_type == "expense":
        return row.exp_description
    return None


def _request_date(row: EmployeeRequest) -> date | None:
    if row.request_type == "wfh":
        return row.wfh_from_date
    if row.request_type == "short_permission":
        return row.sp_date
    if row.request_type == "overtime":
        return row.ot_date
    if row.request_type == "expense":
        return row.exp_date
    return None


def _employee_joining_date(employee: Employee | None) -> date | None:
    if not employee:
        return None
    return getattr(employee, "date_of_joining", None) or getattr(employee, "joining_date", None)


def _policy_for(request_type: str) -> RequestPolicy:
    policy = REQUEST_POLICIES.get(request_type)
    if not policy:
        raise HTTPException(status_code=400, detail="Unsupported request type.")
    return policy


def _policy_bounds(policy: RequestPolicy, employee: Employee | None, today: date | None = None) -> tuple[date | None, date | None]:
    today = today or date.today()
    joining_date = _employee_joining_date(employee)
    min_date = today - timedelta(days=policy.maximum_past_days) if policy.allow_past_dates and policy.maximum_past_days is not None else None
    if not policy.allow_past_dates:
        min_date = today
    if joining_date:
        joining_floor = joining_date
        if policy.allow_dates_before_joining:
            pre_joining_days = policy.maximum_pre_joining_days or 0
            joining_floor = joining_date - timedelta(days=pre_joining_days)
        min_date = max(filter(None, [min_date, joining_floor]), default=joining_floor)
    max_date = today + timedelta(days=policy.maximum_future_days) if policy.allow_future_dates and policy.maximum_future_days is not None else None
    if not policy.allow_future_dates:
        max_date = today if policy.allow_today else today - timedelta(days=1)
    if not policy.allow_past_dates and not policy.allow_today:
        min_date = today + timedelta(days=1)
    return min_date, max_date


def _validate_date_against_policy(policy: RequestPolicy, employee: Employee | None, value: date, label: str) -> None:
    today = date.today()
    if value < today and not policy.allow_past_dates:
        raise HTTPException(status_code=400, detail=policy.invalid_past_message)
    if value > today and not policy.allow_future_dates:
        raise HTTPException(status_code=400, detail=policy.invalid_future_message)
    if value == today and not policy.allow_today:
        raise HTTPException(status_code=400, detail=policy.invalid_future_message)

    joining_date = _employee_joining_date(employee)
    if joining_date and value < joining_date:
        if not policy.allow_dates_before_joining:
            raise HTTPException(
                status_code=400,
                detail=f"{label} cannot be requested before your joining date ({joining_date.strftime('%b %d, %Y')}).",
            )
        earliest_pre_joining = joining_date - timedelta(days=policy.maximum_pre_joining_days or 0)
        if value < earliest_pre_joining:
            raise HTTPException(status_code=400, detail=policy.pre_joining_message)

    min_date, max_date = _policy_bounds(policy, employee, today)
    if min_date and value < min_date:
        raise HTTPException(status_code=400, detail=policy.past_window_message)
    if max_date and value > max_date:
        raise HTTPException(status_code=400, detail=policy.future_window_message)


def _validate_request_dates_by_policy(row: EmployeeRequest, employee: Employee | None) -> None:
    policy = _policy_for(row.request_type)
    start_date, end_date = _start_end_dates(row)
    if not start_date:
        return
    _validate_date_against_policy(policy, employee, start_date, policy.label)
    if end_date and end_date != start_date:
        _validate_date_against_policy(policy, employee, end_date, policy.label)


def _min_forward_request_date(employee: Employee | None) -> date:
    today = date.today()
    joining_date = _employee_joining_date(employee)
    return max(today, joining_date) if joining_date else today


def _validate_not_before_joining(employee: Employee | None, request_date: date | None, label: str) -> None:
    joining_date = _employee_joining_date(employee)
    if joining_date and request_date and request_date < joining_date:
        raise HTTPException(
            status_code=400,
            detail=f"{label} cannot be requested before your joining date ({joining_date.strftime('%b %d, %Y')}).",
        )


def _start_end_dates(row: EmployeeRequest) -> tuple[date | None, date | None]:
    if row.request_type == "wfh":
        return row.wfh_from_date, row.wfh_to_date
    request_date = _request_date(row)
    return request_date, request_date


def _start_end_times(row: EmployeeRequest):
    if row.request_type == "short_permission":
        return row.sp_start_time, row.sp_end_time
    if row.request_type == "overtime":
        return row.ot_start_time, row.ot_end_time
    return None, None


def _duration(row: EmployeeRequest) -> int | None:
    if row.request_type == "short_permission":
        return row.sp_duration_minutes
    if row.request_type == "overtime":
        return row.ot_duration_minutes
    return None


def _hours(row: EmployeeRequest) -> float:
    minutes = _duration(row)
    return round(minutes / 60, 2) if minutes else 0


def _build_title(row: EmployeeRequest) -> str:
    label = REQUEST_TYPES[row.request_type]
    if row.request_type == "wfh":
        return f"{label}: {row.wfh_from_date} to {row.wfh_to_date}"
    if row.request_type == "short_permission":
        return f"{label}: {row.sp_date}"
    if row.request_type == "overtime":
        return f"{label}: {_hours(row):g}h on {row.ot_date}"
    if row.request_type == "expense":
        return f"{label}: {row.exp_currency or 'USD'} {_decimal(row.exp_amount):g}"
    return label


def _apply_payload(row: EmployeeRequest, payload: RequestCreateSchema | RequestUpdateSchema, request_type: str) -> None:
    if request_type == "wfh" and payload.wfh:
        if payload.wfh.to_date < payload.wfh.from_date:
            raise HTTPException(status_code=400, detail="To Date must be on or after From Date.")
        row.wfh_from_date = payload.wfh.from_date
        row.wfh_to_date = payload.wfh.to_date
        row.wfh_reason = payload.wfh.reason
        row.wfh_note = payload.wfh.note
    elif request_type == "short_permission" and payload.short_permission:
        row.sp_date = payload.short_permission.date
        row.sp_start_time = payload.short_permission.start_time
        row.sp_end_time = payload.short_permission.end_time
        row.sp_reason = payload.short_permission.reason
        row.sp_duration_minutes = _time_diff_minutes(payload.short_permission.start_time, payload.short_permission.end_time)
    elif request_type == "overtime" and payload.overtime:
        row.ot_date = payload.overtime.date
        row.ot_start_time = payload.overtime.start_time
        row.ot_end_time = payload.overtime.end_time
        row.ot_project_id = payload.overtime.project_id
        row.ot_reason = payload.overtime.reason
        row.ot_duration_minutes = _time_diff_minutes(payload.overtime.start_time, payload.overtime.end_time)
    elif request_type == "expense" and payload.expense:
        row.exp_date = payload.expense.date
        row.exp_category = payload.expense.category
        row.exp_amount = payload.expense.amount
        row.exp_currency = payload.expense.currency.upper()
        row.exp_description = payload.expense.description
    else:
        raise HTTPException(status_code=400, detail=f"{REQUEST_TYPES[request_type]} data is required.")
    row.title = _build_title(row)


def _check_wfh_overlap(db: Session, employee_id: str, from_date: date, to_date: date, exclude_request_id: str | None = None) -> EmployeeRequest | None:
    query = db.query(EmployeeRequest).filter(
        EmployeeRequest.employee_id == employee_id,
        EmployeeRequest.request_type == "wfh",
        EmployeeRequest.status.in_(["pending", "approved"]),
        EmployeeRequest.wfh_to_date >= from_date,
        EmployeeRequest.wfh_from_date <= to_date,
    )
    if exclude_request_id:
        query = query.filter(EmployeeRequest.id != exclude_request_id)
    return query.first()


def _check_sp_overlap(db: Session, employee_id: str, sp_date: date, exclude_request_id: str | None = None) -> EmployeeRequest | None:
    query = db.query(EmployeeRequest).filter(
        EmployeeRequest.employee_id == employee_id,
        EmployeeRequest.request_type == "short_permission",
        EmployeeRequest.status.in_(["pending", "approved"]),
        EmployeeRequest.sp_date == sp_date,
    )
    if exclude_request_id:
        query = query.filter(EmployeeRequest.id != exclude_request_id)
    return query.first()


def _leave_overlap_warning(db: Session, row: EmployeeRequest) -> str | None:
    start_date, end_date = _start_end_dates(row)
    if not start_date or not end_date:
        return None
    overlap = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == row.employee_id,
        LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= end_date,
        LeaveRequest.end_date >= start_date,
    ).first()
    if not overlap:
        return None
    return "You have an approved or pending leave overlapping this period. Please confirm."


def _validate_request_fields(db: Session, row: EmployeeRequest, block_conflicts: bool = True) -> str | None:
    employee = find_employee(db, row.employee_id)
    if row.request_type == "wfh":
        if not row.wfh_from_date or not row.wfh_to_date:
            raise HTTPException(status_code=400, detail="WFH requests require From Date and To Date.")
        if row.wfh_to_date < row.wfh_from_date:
            raise HTTPException(status_code=400, detail="To Date must be on or after From Date.")
        _validate_request_dates_by_policy(row, employee)
        if (row.wfh_to_date - row.wfh_from_date).days + 1 > settings.REQUESTS_WFH_MAX_DAYS:
            raise HTTPException(status_code=400, detail=f"WFH requests cannot exceed {settings.REQUESTS_WFH_MAX_DAYS} days.")
        if block_conflicts and _check_wfh_overlap(db, row.employee_id, row.wfh_from_date, row.wfh_to_date, row.id):
            raise HTTPException(status_code=409, detail="You already have an active WFH request overlapping this date range.")
    elif row.request_type == "short_permission":
        if not row.sp_date or not row.sp_duration_minutes:
            raise HTTPException(status_code=400, detail="Short permission requires date, start time, and end time.")
        _validate_request_dates_by_policy(row, employee)
        if row.sp_duration_minutes > settings.REQUESTS_SP_MAX_DURATION_MINUTES:
            raise HTTPException(status_code=400, detail=f"Short permission cannot exceed {settings.REQUESTS_SP_MAX_DURATION_MINUTES} minutes.")
        if block_conflicts and _check_sp_overlap(db, row.employee_id, row.sp_date, row.id):
            raise HTTPException(status_code=409, detail="You already have a short permission request for this date.")
    elif row.request_type == "overtime":
        if not row.ot_date or not row.ot_duration_minutes:
            raise HTTPException(status_code=400, detail="Overtime requests require date, start time, and end time.")
        _validate_request_dates_by_policy(row, employee)
        if row.ot_duration_minutes > settings.REQUESTS_OVERTIME_MAX_DURATION_MINUTES:
            raise HTTPException(status_code=400, detail=f"Overtime cannot exceed {settings.REQUESTS_OVERTIME_MAX_DURATION_MINUTES} minutes.")
    elif row.request_type == "expense":
        if not row.exp_date or not row.exp_amount:
            raise HTTPException(status_code=400, detail="Expense requests require date and amount.")
        _validate_request_dates_by_policy(row, employee)
    return _leave_overlap_warning(db, row)


def _serialize_attachment(row: RequestAttachment) -> dict[str, Any]:
    uploader = getattr(row, "_uploaded_by_name", None)
    return {
        "id": row.id,
        "request_id": row.request_id,
        "original_file_name": row.original_file_name,
        "file_extension": row.file_extension,
        "file_size_bytes": row.file_size_bytes,
        "mime_type": row.mime_type,
        "document_type": row.document_type,
        "storage_provider": row.storage_provider,
        "uploaded_by_name": uploader,
        "created_at": row.created_at,
    }


def serialize_comment(db: Session, row: RequestComment) -> dict[str, Any]:
    author = find_employee(db, row.author_id)
    return {
        "id": row.id,
        "body": row.body,
        "comment": row.body,
        "is_internal": row.is_internal,
        "author_id": row.author_id,
        "created_by_name": employee_name(author),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _serialize_history(db: Session, row: RequestStatusHistory) -> dict[str, Any]:
    actor = find_employee(db, row.changed_by_id)
    return {
        "id": row.id,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "old_status": row.from_status,
        "new_status": row.to_status,
        "action": f"{row.from_status or 'new'}_to_{row.to_status}",
        "reason": row.reason,
        "performed_by_name": employee_name(actor),
        "performed_at": row.created_at,
        "created_at": row.created_at,
    }


def serialize_request(db: Session, row: EmployeeRequest, actor: Employee | None = None, include_detail: bool = False) -> dict[str, Any]:
    employee = find_employee(db, row.employee_id)
    reviewer = find_employee(db, row.reviewed_by_id)
    current_owner = find_employee(db, row.current_owner_id)
    submitted_to = find_employee(db, row.submitted_to_id)
    start_date, end_date = _start_end_dates(row)
    start_time, end_time = _start_end_times(row)
    amount = _decimal(row.exp_amount)
    manager = _manager_for_employee(db, employee) if employee else None
    pending_with = employee_name(manager) if manager else "HR Admin"
    days_pending = None
    if row.pending_since:
        days_pending = max(0, (utc_now() - row.pending_since).days)
    data = {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": employee_name(employee),
        "ticket_number": row.ticket_number,
        "request_type": row.request_type,
        "request_type_label": REQUEST_TYPES.get(row.request_type, row.request_type),
        "title": row.title,
        "status": row.status,
        "current_owner_id": row.current_owner_id,
        "current_owner_name": employee_name(current_owner) if current_owner else None,
        "submitted_to_id": row.submitted_to_id,
        "submitted_to_name": employee_name(submitted_to) if submitted_to else None,
        "pending_since": row.pending_since,
        "days_pending": days_pending,
        "start_date": start_date,
        "end_date": end_date,
        "request_date": _request_date(row),
        "start_time": start_time.isoformat(timespec="minutes") if start_time else None,
        "end_time": end_time.isoformat(timespec="minutes") if end_time else None,
        "duration_minutes": _duration(row),
        "hours": _hours(row),
        "amount": amount,
        "currency": row.exp_currency,
        "category": row.exp_category,
        "reason": _reason(row),
        "approver_name": employee_name(current_owner) if current_owner else pending_with,
        "reviewed_by_id": row.reviewed_by_id,
        "reviewed_by_name": employee_name(reviewer) if reviewer else None,
        "reviewed_at": row.reviewed_at,
        "reviewer_notes": row.reviewer_notes,
        "approved_by_name": employee_name(reviewer) if row.status == "approved" and reviewer else None,
        "approved_at": row.reviewed_at if row.status == "approved" else None,
        "rejected_by_name": employee_name(reviewer) if row.status == "rejected" and reviewer else None,
        "rejected_at": row.reviewed_at if row.status == "rejected" else None,
        "rejection_reason": row.reviewer_notes if row.status == "rejected" else None,
        "submitted_at": row.submitted_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "can_edit": bool(actor and actor.id == row.employee_id and row.status == "draft"),
        "can_submit": bool(actor and actor.id == row.employee_id and row.status == "draft"),
        "can_cancel": bool(actor and actor.id == row.employee_id and row.status in {"draft", "pending"}),
        "can_decide": bool(actor and row.status == "pending" and _can_review(db, actor, row)),
        "can_reassign": bool(actor and row.status == "pending" and _is_admin(actor)),
        "wfh": {"from_date": row.wfh_from_date, "to_date": row.wfh_to_date, "reason": row.wfh_reason, "note": row.wfh_note},
        "short_permission": {"date": row.sp_date, "start_time": row.sp_start_time, "end_time": row.sp_end_time, "reason": row.sp_reason, "duration_minutes": row.sp_duration_minutes},
        "overtime": {"date": row.ot_date, "start_time": row.ot_start_time, "end_time": row.ot_end_time, "project_id": row.ot_project_id, "reason": row.ot_reason, "duration_minutes": row.ot_duration_minutes},
        "expense": {"date": row.exp_date, "category": row.exp_category, "amount": amount, "currency": row.exp_currency, "description": row.exp_description, "paid_at": row.exp_paid_at, "paid_by_id": row.exp_paid_by_id},
    }
    if include_detail:
        attachments = db.query(RequestAttachment).filter(
            RequestAttachment.request_id == row.id,
            RequestAttachment.is_deleted.is_(False),
        ).order_by(RequestAttachment.created_at.asc()).all()
        comments_query = db.query(RequestComment).filter(RequestComment.request_id == row.id)
        if actor and actor.id == row.employee_id and not _is_admin(actor):
            comments_query = comments_query.filter(RequestComment.is_internal.is_(False))
        comments = comments_query.order_by(RequestComment.created_at.asc()).all()
        history = db.query(RequestStatusHistory).filter(RequestStatusHistory.request_id == row.id).order_by(RequestStatusHistory.created_at.asc()).all()
        serialized_attachments = []
        for item in attachments:
            uploader = find_employee(db, item.uploaded_by_id)
            setattr(item, "_uploaded_by_name", employee_name(uploader))
            serialized_attachments.append(_serialize_attachment(item))
        data.update({
            "attachments": serialized_attachments,
            "comments": [serialize_comment(db, item) for item in comments],
            "history": [_serialize_history(db, item) for item in history],
        })
    warning = getattr(row, "_warning", None)
    if warning:
        data["warning"] = warning
    return data


def get_types() -> list[dict[str, str]]:
    return [{"value": key, "label": value} for key, value in REQUEST_TYPES.items()]


def get_request_policies(actor: Employee) -> dict[str, Any]:
    return {
        "policies": {
            key: _serialize_policy(policy, actor)
            for key, policy in REQUEST_POLICIES.items()
        }
    }


def get_request(db: Session, request_id: str) -> EmployeeRequest:
    row = db.query(EmployeeRequest).filter(EmployeeRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found.")
    return row


def _date_filter(query, date_from: date | None, date_to: date | None):
    if not date_from and not date_to:
        return query
    clauses = []
    for column in (EmployeeRequest.wfh_from_date, EmployeeRequest.sp_date, EmployeeRequest.ot_date, EmployeeRequest.exp_date):
        bounds = []
        if date_from is not None:
            bounds.append(column >= date_from)
        if date_to is not None:
            bounds.append(column <= date_to)
        clauses.append(and_(*bounds))
    return query.filter(or_(*clauses))


def get_my_requests(
    db: Session,
    actor: Employee,
    status: str | None = None,
    request_type: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    query = db.query(EmployeeRequest).filter(EmployeeRequest.employee_id == actor.id)
    if status and status != "all":
        query = query.filter(EmployeeRequest.status == status)
    if request_type and request_type != "all":
        query = query.filter(EmployeeRequest.request_type == request_type)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(or_(
            EmployeeRequest.ticket_number.ilike(like),
            EmployeeRequest.title.ilike(like),
            EmployeeRequest.wfh_reason.ilike(like),
            EmployeeRequest.sp_reason.ilike(like),
            EmployeeRequest.ot_reason.ilike(like),
            EmployeeRequest.exp_description.ilike(like),
        ))
    query = _date_filter(query, date_from, date_to)
    total = query.count()
    rows = query.order_by(EmployeeRequest.updated_at.desc(), EmployeeRequest.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [serialize_request(db, row, actor) for row in rows], "total": total, "page": page, "per_page": per_page}


def get_approval_queue(
    db: Session,
    actor: Employee,
    status: str | None = "pending",
    request_type: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    if not _is_reviewer(actor):
        raise HTTPException(status_code=403, detail="Only managers and HR admins can view approval queues.")
    query = db.query(EmployeeRequest).join(Employee, Employee.id == EmployeeRequest.employee_id)
    if _is_admin(actor):
        query = query.filter(EmployeeRequest.employee_id != actor.id)
    else:
        query = query.filter(
            EmployeeRequest.employee_id != actor.id,
            or_(
                EmployeeRequest.current_owner_id == actor.id,
                Employee.manager_id == actor.id,
                Employee.reporting_manager == employee_name(actor),
                Employee.reporting_manager == actor.work_email,
            ),
        )
    if status and status != "all":
        query = query.filter(EmployeeRequest.status == status)
    if request_type and request_type != "all":
        query = query.filter(EmployeeRequest.request_type == request_type)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(or_(
            Employee.first_name.ilike(like),
            Employee.last_name.ilike(like),
            Employee.work_email.ilike(like),
            EmployeeRequest.ticket_number.ilike(like),
            EmployeeRequest.title.ilike(like),
            EmployeeRequest.wfh_reason.ilike(like),
            EmployeeRequest.sp_reason.ilike(like),
            EmployeeRequest.ot_reason.ilike(like),
            EmployeeRequest.exp_description.ilike(like),
        ))
    query = _date_filter(query, date_from, date_to)
    total = query.count()
    rows = query.order_by(EmployeeRequest.updated_at.desc(), EmployeeRequest.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [serialize_request(db, row, actor) for row in rows], "total": total, "page": page, "per_page": per_page}


def create_request(db: Session, actor: Employee, payload: RequestCreateSchema) -> EmployeeRequest:
    status = "pending" if payload.submit_immediately else "draft"
    row = EmployeeRequest(
        employee_id=actor.id,
        ticket_number=_generate_ticket_number(db, payload.request_type),
        request_type=payload.request_type,
        title=REQUEST_TYPES[payload.request_type],
        status="draft",
        current_owner_id=actor.id,
        created_by=actor.id,
        updated_by=actor.id,
    )
    _apply_payload(row, payload, payload.request_type)
    db.add(row)
    db.flush()
    warning = _validate_request_fields(db, row, block_conflicts=status == "pending")
    if warning:
        setattr(row, "_warning", warning)
    log_audit(
        db,
        actor,
        "request_created",
        "employee_request",
        row.id,
        new_values=_snapshot(row),
        metadata={"ticket_number": row.ticket_number},
    )
    if status == "pending":
        manager = _ensure_employee_can_submit_hr_request(db, actor)
        row.submitted_to_id = manager.id
        row.current_owner_id = manager.id
        row.pending_since = utc_now()
    _transition(db, row, actor, status, "request_submitted" if status == "pending" else "request_created")
    if status == "pending":
        _notify_approvers(db, row, actor)
    db.commit()
    db.refresh(row)
    return row


def update_request(db: Session, actor: Employee, request_id: str, payload: RequestUpdateSchema) -> EmployeeRequest:
    row = get_request(db, request_id)
    if row.employee_id != actor.id:
        raise HTTPException(status_code=403, detail="You can update only your own requests.")
    if row.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft requests can be updated.")
    old = _snapshot(row)
    _apply_payload(row, payload, row.request_type)
    warning = _validate_request_fields(db, row, block_conflicts=False)
    if warning:
        setattr(row, "_warning", warning)
    row.updated_by = actor.id
    row.updated_at = utc_now()
    log_audit(db, actor, "request_updated", "employee_request", row.id, old_values=old, new_values=_snapshot(row), metadata={"ticket_number": row.ticket_number})
    db.commit()
    db.refresh(row)
    return row


def submit_request(db: Session, actor: Employee, request_id: str) -> EmployeeRequest:
    row = get_request(db, request_id)
    if row.employee_id != actor.id:
        raise HTTPException(status_code=403, detail="You can submit only your own requests.")
    if row.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft requests can be submitted.")
    warning = _validate_request_fields(db, row, block_conflicts=True)
    if warning:
        setattr(row, "_warning", warning)
    employee = find_employee(db, row.employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    manager = _ensure_employee_can_submit_hr_request(db, employee)
    row.submitted_to_id = manager.id
    row.current_owner_id = manager.id
    row.pending_since = utc_now()
    _transition(db, row, actor, "pending", "request_submitted")
    _notify_approvers(db, row, employee or actor)
    db.commit()
    db.refresh(row)
    return row


def cancel_request(db: Session, actor: Employee, request_id: str, reason: str | None = None) -> EmployeeRequest:
    row = get_request(db, request_id)
    if row.employee_id != actor.id:
        raise HTTPException(status_code=403, detail="You can cancel only your own requests.")
    if row.status not in {"draft", "pending"}:
        raise HTTPException(status_code=400, detail="Only draft or pending requests can be cancelled.")
    row.current_owner_id = None
    row.pending_since = None
    _transition(db, row, actor, "cancelled", "request_cancelled", reason=reason)
    _clear_inbox(db, row.id)
    db.commit()
    db.refresh(row)
    return row


def approve_request(db: Session, actor: Employee, request_id: str, notes: str | None = None) -> EmployeeRequest:
    row = get_request(db, request_id)
    _ensure_review_access(db, actor, row)
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be approved.")
    policy = _policy_for(row.request_type)
    actor_role = normalize_role(actor.role)
    if actor_role == "manager" and policy.requires_hr_approval:
        hr_admins = _hr_admins(db)
        next_owner = next((item for item in hr_admins if item.id != actor.id and item.id != row.employee_id), None)
        if next_owner:
            old_owner_id = row.current_owner_id
            row.current_owner_id = next_owner.id
            row.pending_since = utc_now()
            row.updated_by = actor.id
            row.updated_at = utc_now()
            db.add(RequestStatusHistory(
                request_id=row.id,
                from_status=row.status,
                to_status=row.status,
                changed_by_id=actor.id,
                reason=notes or "Manager approved; routed to HR.",
            ))
            log_audit(
                db,
                actor,
                "request_manager_approved",
                "employee_request",
                row.id,
                old_values={"current_owner_id": old_owner_id},
                new_values={"current_owner_id": next_owner.id, "status": row.status},
                reason=notes,
                metadata={"ticket_number": row.ticket_number},
            )
            _clear_inbox(db, row.id)
            _notify(
                db,
                next_owner.id,
                "Request awaiting HR review",
                f"{row.ticket_number or 'A request'} was approved by {employee_name(actor)} and is ready for HR review.",
                row.id,
            )
            _inbox(
                db,
                next_owner.id,
                f"{REQUEST_TYPES[row.request_type]} HR review",
                f"{row.ticket_number or 'A request'} was approved by {employee_name(actor)} and needs HR review.",
                row.id,
            )
            db.commit()
            db.refresh(row)
            return row
    _transition(db, row, actor, "approved", "request_approved", notes=notes)
    if actor_role == "manager":
        row.current_owner_id = None
        row.pending_since = None
    else:
        row.current_owner_id = None
        row.pending_since = None
    _clear_inbox(db, row.id)
    _notify_employee(db, row, actor, "approved")
    db.commit()
    db.refresh(row)
    return row


def reject_request(db: Session, actor: Employee, request_id: str, reason: str) -> EmployeeRequest:
    row = get_request(db, request_id)
    _ensure_review_access(db, actor, row)
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be rejected.")
    row.current_owner_id = None
    row.pending_since = None
    _transition(db, row, actor, "rejected", "request_rejected", reason=reason)
    _clear_inbox(db, row.id)
    _notify_employee(db, row, actor, "rejected")
    db.commit()
    db.refresh(row)
    return row


def add_comment(db: Session, actor: Employee, request_id: str, payload: CommentSchema) -> RequestComment:
    row = get_request(db, request_id)
    ensure_read_access(db, actor, row)
    if payload.is_internal and not _can_review(db, actor, row):
        raise HTTPException(status_code=403, detail="Only reviewers can add internal comments.")
    comment = RequestComment(
        request_id=row.id,
        author_id=actor.id,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    db.add(comment)
    log_audit(db, actor, "request_comment_added", "employee_request", row.id, metadata={"internal": payload.is_internal, "ticket_number": row.ticket_number})
    db.commit()
    db.refresh(comment)
    return comment


def reassign_request(db: Session, actor: Employee, request_id: str, payload: ReassignSchema) -> EmployeeRequest:
    if not _is_admin(actor):
        raise HTTPException(status_code=403, detail="Only HR Admin and Super Admin can reassign requests.")
    row = get_request(db, request_id)
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be reassigned.")
    new_owner = find_employee(db, payload.new_owner_id)
    if not new_owner:
        raise HTTPException(status_code=404, detail="New owner not found.")
    old_owner = find_employee(db, row.current_owner_id)
    old_owner_id = row.current_owner_id
    row.current_owner_id = new_owner.id
    row.pending_since = utc_now()
    row.updated_by = actor.id
    row.updated_at = utc_now()
    reason = f"Reassigned from {employee_name(old_owner) if old_owner else 'Unassigned'} to {employee_name(new_owner)}. Reason: {payload.reason}"
    db.add(RequestStatusHistory(
        request_id=row.id,
        from_status=row.status,
        to_status=row.status,
        changed_by_id=actor.id,
        reason=reason,
    ))
    log_audit(
        db,
        actor,
        "request_reassigned",
        "employee_request",
        row.id,
        old_values={"current_owner_id": old_owner_id},
        new_values={"current_owner_id": new_owner.id},
        reason=payload.reason,
        metadata={"ticket_number": row.ticket_number, "from_owner_id": old_owner_id, "to_owner_id": new_owner.id},
    )
    _clear_inbox(db, row.id)
    _notify(db, new_owner.id, "Request reassigned to you", f"{row.ticket_number or 'A request'} needs your review.", row.id)
    _inbox(db, new_owner.id, f"{REQUEST_TYPES[row.request_type]} review", f"{row.ticket_number or 'A request'} was reassigned to you.", row.id)
    db.commit()
    db.refresh(row)
    return row


def upload_attachment(
    db: Session,
    actor: Employee,
    request_id: str,
    file_name: str,
    content_type: str | None,
    file_bytes: bytes,
    document_type: str = "OTHER",
) -> RequestAttachment:
    from app.services.attachment_service import upload_attachment as upload_request_attachment

    return upload_request_attachment(db, actor, request_id, file_name, content_type, file_bytes, document_type)


def get_attachment(db: Session, actor: Employee, attachment_id: str) -> RequestAttachment:
    attachment = db.query(RequestAttachment).filter(
        RequestAttachment.id == attachment_id,
        RequestAttachment.is_deleted.is_(False),
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    row = get_request(db, attachment.request_id)
    ensure_read_access(db, actor, row)
    return attachment


def delete_attachment(db: Session, actor: Employee, attachment_id: str) -> None:
    attachment = get_attachment(db, actor, attachment_id)
    from app.services.attachment_service import delete_attachment as delete_request_attachment

    delete_request_attachment(db, actor, attachment.request_id, attachment_id)


def serialize_attachment(db: Session, row: RequestAttachment) -> dict[str, Any]:
    from app.services.attachment_service import serialize_attachment as serialize_request_attachment

    return serialize_request_attachment(db, row)


def mark_expense_paid(db: Session, actor: Employee, request_id: str) -> EmployeeRequest:
    if not _can_pay_expenses(actor):
        raise HTTPException(status_code=403, detail="Only HR Admin and Super Admin can mark expenses as paid.")
    row = get_request(db, request_id)
    if row.request_type != "expense":
        raise HTTPException(status_code=400, detail="Only expense requests can be marked as paid.")
    if row.status != "approved":
        raise HTTPException(status_code=400, detail="Request must be approved before it can be marked as paid.")
    if settings.REQUESTS_EXPENSE_RECEIPT_REQUIRED:
        receipt_count = db.query(RequestAttachment).filter(
            RequestAttachment.request_id == row.id,
            RequestAttachment.document_type == "EXPENSE_RECEIPT",
            RequestAttachment.is_deleted.is_(False),
        ).count()
        if receipt_count == 0:
            raise HTTPException(status_code=400, detail="A receipt is required before this expense can be marked as paid.")
    row.exp_paid_at = utc_now()
    row.exp_paid_by_id = actor.id
    row.current_owner_id = None
    row.pending_since = None
    _transition(db, row, actor, "paid", "request_paid")
    _notify_expense_paid(db, row)
    log_audit(
        db,
        actor,
        "request_paid",
        "employee_request",
        row.id,
        metadata={"ticket_number": row.ticket_number},
    )
    db.commit()
    db.refresh(row)
    return row
