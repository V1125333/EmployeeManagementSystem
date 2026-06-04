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
from app.services.settings_service import get_current_employee

router = APIRouter(prefix="/leaves", tags=["Leaves"])


class LeaveRequestPayload(BaseModel):
    leave_type_id: str
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=1, max_length=200)
    action: str = Field(default="submit", pattern="^(draft|submit)$")


class LeaveDecisionPayload(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reviewer_notes: str | None = Field(default=None, max_length=300)


def decimal_to_float(value) -> float:
    return float(value) if isinstance(value, Decimal) else float(value or 0)


def is_admin(role: str | None) -> bool:
    normalized = (role or "").lower().replace(" ", "_")
    return normalized in {"super_admin", "admin", "hr_admin", "global_access"}


def leave_days(start_date: date, end_date: date) -> float:
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="To Date must be on or after From Date.")
    total = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            total += 1
        current += timedelta(days=1)
    if total <= 0:
        raise HTTPException(status_code=400, detail="Leave requests must include at least one weekday.")
    return float(total)


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
        "reason": request.reason,
        "status": request.status,
        "reporting_manager": manager_name,
        "pending_with": pending_with if request.status == "pending" else None,
        "reviewed_by": employee_name(reviewer) if reviewer else None,
        "reviewed_at": request.reviewed_at,
        "reviewer_notes": request.reviewer_notes,
        "created_at": request.created_at,
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
        balances.append({
            "leave_type_id": leave_type.id,
            "type": leave_type.name,
            "code": leave_type.code,
            "total": total,
            "available": "On request" if total <= 0 and not leave_type.is_paid else round(max(total - used, 0), 1),
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

    total_days = leave_days(payload.start_date, payload.end_date)
    if payload.action == "submit":
        balance = ensure_balance(db, employee.id, leave_type, payload.start_date.year)
        available = decimal_to_float(balance.total_days) + decimal_to_float(balance.carry_forward_days) - decimal_to_float(balance.used_days)
        if leave_type.is_paid and total_days > available:
            raise HTTPException(status_code=400, detail="Selected leave days exceed your available balance.")

    now = datetime.utcnow()
    request = LeaveRequest(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_days=total_days,
        reason=payload.reason.strip(),
        status="draft" if payload.action == "draft" else "pending",
        created_at=now,
        updated_at=now,
    )
    db.add(request)
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

    total_days = leave_days(payload.start_date, payload.end_date)
    if payload.action == "submit":
        balance = ensure_balance(db, employee.id, leave_type, payload.start_date.year)
        available = decimal_to_float(balance.total_days) + decimal_to_float(balance.carry_forward_days) - decimal_to_float(balance.used_days)
        if leave_type.is_paid and total_days > available:
            raise HTTPException(status_code=400, detail="Selected leave days exceed your available balance.")

    request.leave_type_id = leave_type.id
    request.start_date = payload.start_date
    request.end_date = payload.end_date
    request.total_days = total_days
    request.reason = payload.reason.strip()
    request.status = "draft" if payload.action == "draft" else "pending"
    request.updated_at = datetime.utcnow()
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
    db.delete(request)
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
    if not is_admin(reviewer.role) and employee.reporting_manager != employee_name(reviewer):
        raise HTTPException(status_code=403, detail="Not authorized to review this leave request.")

    now = datetime.utcnow()
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

    db.commit()
    return await leave_approvals(db, x_user_id, x_user_email)
