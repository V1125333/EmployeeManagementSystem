"""
Employee leave request and approval endpoints.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday
from app.services.audit_service import log_audit, log_authorization_failure
from app.services.settings_service import get_current_employee
from app.services.work_calendar_service import payable_leave_day_count, region_from_location

router = APIRouter(prefix="/leaves", tags=["Leaves"])


DEFAULT_LEAVE_DATE_POLICIES = {
    "SL": {
        "allow_future_dates": True,
        "past_date_limit_days": None,
        "future_date_warning": None,
    },
    "BL": {
        "allow_future_dates": True,
        "past_date_limit_days": 30,
        "future_date_warning": "Future bereavement leave is unusual. Please confirm the dates before submitting.",
    },
}


def leave_date_policy(leave_type: LeaveType) -> dict:
    code = (leave_type.code or "").upper()
    defaults = DEFAULT_LEAVE_DATE_POLICIES.get(code, {
        "allow_future_dates": True,
        "past_date_limit_days": None,
        "future_date_warning": None,
    })
    allow_future = leave_type.allow_future_dates
    return {
        "allow_future_dates": defaults["allow_future_dates"] if allow_future is None else bool(allow_future),
        "past_date_limit_days": leave_type.past_date_limit_days
        if leave_type.past_date_limit_days is not None
        else defaults["past_date_limit_days"],
        "future_date_warning": leave_type.future_date_warning
        if leave_type.future_date_warning is not None
        else defaults["future_date_warning"],
    }


def validate_leave_date_policy(leave_type: LeaveType, start_date: date, end_date: date):
    policy = leave_date_policy(leave_type)
    today = date.today()
    if not policy["allow_future_dates"] and (start_date > today or end_date > today):
        raise HTTPException(
            status_code=400,
            detail=f"{leave_type.name} cannot be applied for future dates.",
        )
    past_limit = policy["past_date_limit_days"]
    if past_limit is not None:
        earliest_allowed = today - timedelta(days=int(past_limit))
        if start_date < earliest_allowed:
            raise HTTPException(
                status_code=400,
                detail=f"{leave_type.name} can only be applied up to {past_limit} days in the past.",
            )


def employee_joining_date(employee: Employee) -> date | None:
    return employee.date_of_joining or employee.joining_date


def min_request_date(employee: Employee) -> date:
    today = date.today()
    joining_date = employee_joining_date(employee)
    return max(today, joining_date) if joining_date else today


def validate_forward_leave_dates(employee: Employee, start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")
    minimum = min_request_date(employee)
    joining_date = employee_joining_date(employee)
    if joining_date and (start_date < joining_date or end_date < joining_date):
        raise HTTPException(
            status_code=400,
            detail=f"Leave cannot be applied before your joining date ({joining_date.strftime('%b %d, %Y')}).",
        )
    today = date.today()
    if start_date < today or end_date < today:
        raise HTTPException(status_code=400, detail="Cannot apply leave for a past date.")
    if start_date < minimum:
        raise HTTPException(status_code=400, detail="Selected leave dates are not available for your profile.")
    max_advance_date = today + timedelta(days=90)
    if start_date > max_advance_date:
        raise HTTPException(status_code=400, detail="Leave cannot be applied more than 90 days in advance.")


def ensure_no_leave_overlap(
    db: Session,
    employee_id: str,
    start_date: date,
    end_date: date,
    exclude_request_id: str | None = None,
) -> None:
    query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= end_date,
        LeaveRequest.end_date >= start_date,
    )
    if exclude_request_id:
        query = query.filter(LeaveRequest.id != exclude_request_id)
    if query.first():
        raise HTTPException(status_code=409, detail="You already have a leave request for this period.")


def effective_available_days(db: Session, balance: LeaveBalance, employee_id: str, leave_type_id: str, year: int) -> tuple[float, float, float, float]:
    total = decimal_to_float(balance.total_days) + decimal_to_float(balance.carry_forward_days)
    used = decimal_to_float(balance.used_days)
    pending = pending_days(db, employee_id, leave_type_id, year)
    effective = round(max(total - used - pending, 0), 1)
    return total, used, pending, effective


def ensure_effective_balance(
    db: Session,
    employee_id: str,
    leave_type: LeaveType,
    requested_days: float,
    year: int,
) -> None:
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type_id == leave_type.id,
        LeaveBalance.year == year,
    ).with_for_update().first()
    if not balance:
        balance = LeaveBalance(
            employee_id=employee_id,
            leave_type_id=leave_type.id,
            year=year,
            total_days=leave_type.default_days_per_year,
            used_days=0,
            carry_forward_days=0,
        )
        db.add(balance)
        db.flush()
    total, used, pending, effective = effective_available_days(db, balance, employee_id, leave_type.id, year)
    if requested_days > effective:
        if effective <= 0 and pending > 0:
            raise HTTPException(status_code=400, detail=f"No balance available - {pending:g} days are pending approval.")
        raise HTTPException(
            status_code=400,
            detail=f"You only have {effective:g} effective days available ({pending:g} days are pending approval).",
        )


class LeaveRequestPayload(BaseModel):
    leave_type_id: str
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=1, max_length=200)
    action: str = Field(default="submit", pattern="^(draft|submit)$")
    holiday_id: str | None = None


class LeaveDecisionPayload(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reviewer_notes: str | None = Field(default=None, max_length=300)


def decimal_to_float(value) -> float:
    return float(value) if isinstance(value, Decimal) else float(value or 0)


def is_admin(role: str | None) -> bool:
    normalized = (role or "").lower().replace(" ", "_")
    return normalized in {"super_admin", "admin", "hr_admin", "global_access"}


def leave_days(db: Session, employee: Employee, leave_type: LeaveType, start_date: date, end_date: date) -> float:
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="To Date must be on or after From Date.")
    total = payable_leave_day_count(db, employee, leave_type, start_date, end_date)
    if total <= 0:
        raise HTTPException(status_code=400, detail="Leave requests must include at least one working day.")
    return float(total)


def holiday_visible_to_employee(holiday: CompanyHoliday, employee: Employee) -> bool:
    region = region_from_location(employee.work_location)
    regions = {item.strip().upper() for item in (holiday.regions or "all").split(",") if item.strip()}
    return "ALL" in regions or region.upper() in regions


def validate_holiday_leave(
    db: Session,
    employee: Employee,
    leave_type: LeaveType,
    payload: LeaveRequestPayload,
    exclude_request_id: str | None = None,
) -> CompanyHoliday | None:
    code = (leave_type.code or "").upper()
    if code not in {"FL", "OH"}:
        return None
    if not payload.holiday_id:
        raise HTTPException(status_code=400, detail=f"{leave_type.name} requires selecting a holiday.")
    holiday = db.query(CompanyHoliday).filter(
        CompanyHoliday.id == payload.holiday_id,
        CompanyHoliday.is_active == True,
        CompanyHoliday.holiday_type.in_(["floating", "optional"]),
    ).first()
    if not holiday or not holiday_visible_to_employee(holiday, employee):
        raise HTTPException(status_code=400, detail="Selected holiday is not available for your region.")
    if payload.start_date != holiday.holiday_date or payload.end_date != holiday.holiday_date:
        raise HTTPException(status_code=400, detail="Floating or optional holiday dates must match the selected holiday.")
    existing_query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.holiday_id == holiday.id,
        LeaveRequest.status.in_(["pending", "approved"]),
    )
    if exclude_request_id:
        existing_query = existing_query.filter(LeaveRequest.id != exclude_request_id)
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail="This holiday has already been requested or used.")
    return holiday


def get_employee(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    return get_current_employee(db, user_id, user_email)


def ensure_balance(db: Session, employee_id: str, leave_type: LeaveType, year: int) -> LeaveBalance:
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type_id == leave_type.id,
        LeaveBalance.year == year,
    ).first()
    if balance:
        return balance
    balance = LeaveBalance(
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        year=year,
        total_days=leave_type.default_days_per_year,
        used_days=0,
        carry_forward_days=0,
    )
    db.add(balance)
    db.flush()
    return balance


def pending_days(db: Session, employee_id: str, leave_type_id: str, year: int) -> float:
    requests = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.leave_type_id == leave_type_id,
        LeaveRequest.status == "pending",
        LeaveRequest.start_date >= date(year, 1, 1),
        LeaveRequest.start_date <= date(year, 12, 31),
    ).all()
    return round(sum(decimal_to_float(item.total_days) for item in requests), 1)


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown"
    return f"{employee.first_name} {employee.last_name}".strip()


def leave_type_applies_to_employee(leave_type: LeaveType, employee: Employee) -> bool:
    code = (leave_type.code or "").upper()
    gender = (employee.gender or "").lower()
    if code == "ML":
        return gender == "female"
    if code == "PL":
        return gender == "male"
    return True


def serialize_request(db: Session, request: LeaveRequest, leave_type: LeaveType | None = None, employee: Employee | None = None) -> dict:
    leave_type = leave_type or db.query(LeaveType).filter(LeaveType.id == request.leave_type_id).first()
    employee = employee or db.query(Employee).filter(Employee.id == request.employee_id).first()
    reviewer = db.query(Employee).filter(Employee.id == request.reviewed_by).first() if request.reviewed_by else None
    manager_name = employee.reporting_manager if employee else None
    pending_with = manager_name or "Super Admin"
    return {
        "id": request.id,
        "employee_id": request.employee_id,
        "employee_name": employee_name(employee),
        "leave_type_id": request.leave_type_id,
        "leave_type": leave_type.name if leave_type else "Leave",
        "start_date": request.start_date,
        "end_date": request.end_date,
        "total_days": decimal_to_float(request.total_days),
        "holiday_id": request.holiday_id,
        "reason": request.reason,
        "status": request.status,
        "reporting_manager": manager_name,
        "pending_with": pending_with if request.status == "pending" else None,
        "reviewed_by": employee_name(reviewer) if reviewer else None,
        "reviewed_at": request.reviewed_at,
        "reviewer_notes": request.reviewer_notes,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


def summary_for_employee(db: Session, employee: Employee) -> dict:
    year = date.today().year
    leave_types = db.query(LeaveType).filter(LeaveType.is_active == True).order_by(LeaveType.sort_order.asc(), LeaveType.name.asc()).all()
    leave_types = [leave_type for leave_type in leave_types if leave_type_applies_to_employee(leave_type, employee)]
    balances = []
    for leave_type in leave_types:
        balance = ensure_balance(db, employee.id, leave_type, year)
        total = decimal_to_float(balance.total_days) + decimal_to_float(balance.carry_forward_days)
        used = decimal_to_float(balance.used_days)
        pending = pending_days(db, employee.id, leave_type.id, year)
        effective = round(max(total - used - pending, 0), 1)
        balances.append({
            "leave_type_id": leave_type.id,
            "type": leave_type.name,
            "code": leave_type.code,
            "date_policy": leave_date_policy(leave_type),
            "total": total,
            "available": "On request" if total <= 0 and not leave_type.is_paid else effective,
            "effective_available": "On request" if total <= 0 and not leave_type.is_paid else effective,
            "used": round(used, 1),
            "pending": pending,
            "is_paid": leave_type.is_paid,
            "is_carry_forward": leave_type.is_carry_forward,
            "max_carry_forward_days": decimal_to_float(leave_type.max_carry_forward_days),
            "expiry_label": (
                "No balance expiry"
                if total <= 0 and not leave_type.is_paid
                else f"Carry forward up to {decimal_to_float(leave_type.max_carry_forward_days):g} days"
                if leave_type.is_carry_forward
                else f"Expires Dec 31, {year}"
            ),
        })

    requests = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee.id,
    ).order_by(LeaveRequest.created_at.desc()).limit(12).all()

    db.commit()
    return {
        "reporting_manager": employee.reporting_manager,
        "joining_date": employee_joining_date(employee),
        "min_request_date": min_request_date(employee),
        "balances": balances,
        "requests": [serialize_request(db, request, employee=employee) for request in requests],
    }


@router.get("/me/summary")
async def my_leave_summary(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    return summary_for_employee(db, employee)


@router.post("/me/requests")
async def create_my_leave_request(
    payload: LeaveRequestPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    leave_type = db.query(LeaveType).filter(LeaveType.id == payload.leave_type_id, LeaveType.is_active == True).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found.")
    if not leave_type_applies_to_employee(leave_type, employee):
        raise HTTPException(status_code=400, detail="This leave type is not applicable to your profile.")

    selected_holiday = validate_holiday_leave(db, employee, leave_type, payload)
    validate_forward_leave_dates(employee, payload.start_date, payload.end_date)
    total_days = leave_days(db, employee, leave_type, payload.start_date, payload.end_date)
    validate_leave_date_policy(leave_type, payload.start_date, payload.end_date)
    ensure_no_leave_overlap(db, employee.id, payload.start_date, payload.end_date)
    if payload.action == "submit":
        if leave_type.is_paid:
            ensure_effective_balance(db, employee.id, leave_type, total_days, payload.start_date.year)

    now = datetime.utcnow()
    request = LeaveRequest(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_days=total_days,
        holiday_id=selected_holiday.id if selected_holiday else None,
        reason=payload.reason.strip(),
        status="draft" if payload.action == "draft" else "pending",
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    db.flush()
    log_audit(
        db,
        employee,
        action="leave.draft_saved" if payload.action == "draft" else "leave.submitted",
        entity_type="leave_request",
        entity_id=request.id,
        new_values={
            "employee_id": employee.id,
            "leave_type": leave_type.name,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "total_days": total_days,
            "holiday_id": selected_holiday.id if selected_holiday else None,
            "status": request.status,
        },
        reason=payload.reason.strip(),
    )
    db.commit()
    db.refresh(request)
    return summary_for_employee(db, employee)


@router.put("/me/requests/{request_id}")
async def update_my_leave_request(
    request_id: str,
    payload: LeaveRequestPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.employee_id == employee.id,
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    if request.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft leave requests can be edited.")

    leave_type = db.query(LeaveType).filter(LeaveType.id == payload.leave_type_id, LeaveType.is_active == True).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found.")
    if not leave_type_applies_to_employee(leave_type, employee):
        raise HTTPException(status_code=400, detail="This leave type is not applicable to your profile.")

    selected_holiday = validate_holiday_leave(db, employee, leave_type, payload, exclude_request_id=request.id)
    validate_forward_leave_dates(employee, payload.start_date, payload.end_date)
    total_days = leave_days(db, employee, leave_type, payload.start_date, payload.end_date)
    validate_leave_date_policy(leave_type, payload.start_date, payload.end_date)
    ensure_no_leave_overlap(db, employee.id, payload.start_date, payload.end_date, exclude_request_id=request.id)
    if payload.action == "submit":
        if leave_type.is_paid:
            ensure_effective_balance(db, employee.id, leave_type, total_days, payload.start_date.year)

    old_values = {
        "leave_type_id": request.leave_type_id,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "total_days": request.total_days,
        "holiday_id": request.holiday_id,
        "reason": request.reason,
        "status": request.status,
    }
    request.leave_type_id = leave_type.id
    request.start_date = payload.start_date
    request.end_date = payload.end_date
    request.total_days = total_days
    request.holiday_id = selected_holiday.id if selected_holiday else None
    request.reason = payload.reason.strip()
    request.status = "draft" if payload.action == "draft" else "pending"
    request.updated_at = datetime.utcnow()
    log_audit(
        db,
        employee,
        action="leave.updated" if payload.action == "draft" else "leave.submitted",
        entity_type="leave_request",
        entity_id=request.id,
        old_values=old_values,
        new_values={
            "leave_type_id": request.leave_type_id,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "total_days": request.total_days,
            "holiday_id": request.holiday_id,
            "reason": request.reason,
            "status": request.status,
        },
        reason=payload.reason.strip(),
    )
    db.commit()
    return summary_for_employee(db, employee)


@router.delete("/me/requests/{request_id}")
async def delete_my_leave_request(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.employee_id == employee.id,
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    if request.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft leave requests can be deleted.")
    old_values = serialize_request(db, request, employee=employee)
    log_audit(
        db,
        employee,
        action="leave.cancelled",
        entity_type="leave_request",
        entity_id=request.id,
        old_values=old_values,
        reason="Employee deleted draft leave request.",
    )
    db.delete(request)
    db.commit()
    return summary_for_employee(db, employee)


@router.post("/me/requests/{request_id}/withdraw")
async def withdraw_my_leave_request(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.employee_id == employee.id,
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be withdrawn.")

    old_values = serialize_request(db, request, employee=employee)
    request.status = "cancelled"
    request.updated_at = datetime.utcnow()
    log_audit(
        db,
        employee,
        action="leave.withdrawn",
        entity_type="leave_request",
        entity_id=request.id,
        old_values=old_values,
        new_values={
            "status": request.status,
            "updated_at": request.updated_at,
        },
        reason="Employee withdrew pending leave request.",
    )
    db.commit()
    return summary_for_employee(db, employee)


@router.get("/approvals")
async def leave_approvals(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    reviewer = get_employee(db, x_user_id, x_user_email)
    query = db.query(LeaveRequest, LeaveType, Employee).join(
        LeaveType,
        LeaveType.id == LeaveRequest.leave_type_id,
    ).join(
        Employee,
        Employee.id == LeaveRequest.employee_id,
    ).filter(LeaveRequest.status == "pending")

    if not is_admin(reviewer.role):
        query = query.filter(Employee.reporting_manager == employee_name(reviewer))

    rows = query.order_by(LeaveRequest.created_at.asc()).all()
    return {
        "approvals": [
            serialize_request(db, request, leave_type=leave_type, employee=employee)
            for request, leave_type, employee in rows
        ]
    }


@router.post("/approvals/{request_id}/decision")
async def decide_leave_request(
    request_id: str,
    payload: LeaveDecisionPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    reviewer = get_employee(db, x_user_id, x_user_email)
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
            db,
            reviewer,
            action="leave.approval",
            entity_type="leave_request",
            entity_id=request.id,
            reason="Reviewer attempted to approve their own leave request.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="You cannot review your own leave request.")
    if not is_admin(reviewer.role) and employee.reporting_manager != employee_name(reviewer):
        log_authorization_failure(
            db,
            reviewer,
            action="leave.approval",
            entity_type="leave_request",
            entity_id=request.id,
            reason="Reviewer is not the employee manager or admin.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Not authorized to review this leave request.")

    now = datetime.utcnow()
    old_values = {"status": request.status, "reviewed_by": request.reviewed_by, "reviewed_at": request.reviewed_at}
    request.status = "approved" if payload.decision == "approve" else "rejected"
    request.reviewed_by = reviewer.id
    request.reviewed_at = now
    request.reviewer_notes = payload.reviewer_notes
    request.updated_at = now

    if payload.decision == "approve":
        leave_type = db.query(LeaveType).filter(LeaveType.id == request.leave_type_id).first()
        if leave_type:
            balance = ensure_balance(db, request.employee_id, leave_type, request.start_date.year)
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
