"""
Super Admin / HR Time Off & Attendance operations API.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import Attendance, AttendanceCorrection, LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import ActivityLog, Notification, TimesheetEntry
from app.services.audit_service import log_audit as log_central_audit
from app.services.settings_service import get_current_employee

router = APIRouter(prefix="/admin/time-off", tags=["Admin Time Off & Attendance"])


class DecisionPayload(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reason: str | None = Field(default=None, max_length=500)


class BalanceAdjustmentPayload(BaseModel):
    total_days: float = Field(..., ge=0, le=365)
    used_days: float = Field(..., ge=0, le=365)
    carry_forward_days: float = Field(default=0, ge=0, le=365)
    reason: str = Field(..., min_length=3, max_length=500)


class AttendanceUpdatePayload(BaseModel):
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: str = Field(..., pattern="^(present|absent|late|wfh|checked_out|on_leave|holiday|half_day)$")
    remarks: str | None = Field(default=None, max_length=500)
    reason: str = Field(..., min_length=3, max_length=500)


def decimal_to_float(value) -> float:
    return float(value) if isinstance(value, Decimal) else float(value or 0)


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown"
    return f"{employee.first_name} {employee.last_name}".strip()


def normalize_role(role: str | None) -> str:
    return (role or "").strip().lower().replace(" ", "_")


def is_admin_role(role: str | None) -> bool:
    return normalize_role(role) in {"super_admin", "admin", "hr_admin", "global_access"}


def require_admin(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    user = get_current_employee(db, user_id, user_email)
    if not is_admin_role(user.role):
        raise HTTPException(status_code=403, detail="Only Super Admin and HR roles can access Time Off & Attendance administration.")
    return user


def log_audit(
    db: Session,
    actor: Employee,
    action: str,
    target_type: str,
    target_id: str | None,
    old_value,
    new_value,
    reason: str | None,
) -> None:
    db.add(ActivityLog(
        actor_id=actor.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=f"{action.replace('_', ' ').title()} by {employee_name(actor)}",
        metadata_json=json.dumps({
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "performed_by": employee_name(actor),
            "performed_at": datetime.utcnow().isoformat(),
        }, default=str),
    ))
    action_name = action.replace("_", ".")
    log_central_audit(
        db,
        actor,
        action=f"admin_time_off.{action_name}",
        entity_type=target_type,
        entity_id=target_id,
        old_values=old_value if isinstance(old_value, dict) else {"value": old_value},
        new_values=new_value if isinstance(new_value, dict) else {"value": new_value},
        reason=reason,
        metadata={"legacy_activity_log": True},
        source="admin",
    )


def notify(db: Session, employee_id: str, title: str, message: str, entity_type: str, entity_id: str | None) -> None:
    db.add(Notification(
        user_id=employee_id,
        title=title,
        message=message,
        type=entity_type,
        notification_type=entity_type,
        related_entity_type=entity_type,
        related_entity_id=entity_id,
        link_url="/employee/notifications",
    ))


def serialize_employee(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "name": employee_name(employee),
        "email": employee.work_email,
        "department": employee.department,
        "role": employee.role,
    }


def serialize_leave_request(db: Session, request: LeaveRequest) -> dict:
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    leave_type = db.query(LeaveType).filter(LeaveType.id == request.leave_type_id).first()
    reviewer = db.query(Employee).filter(Employee.id == request.reviewed_by).first() if request.reviewed_by else None
    return {
        "id": request.id,
        "employee_id": request.employee_id,
        "employee_name": employee_name(employee),
        "leave_type": leave_type.name if leave_type else "Leave",
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "total_days": decimal_to_float(request.total_days),
        "reason": request.reason,
        "status": request.status,
        "reviewed_by": employee_name(reviewer) if reviewer else None,
        "reviewer_notes": request.reviewer_notes,
        "created_at": request.created_at.isoformat() if request.created_at else None,
    }


def serialize_balance(db: Session, balance: LeaveBalance) -> dict:
    employee = db.query(Employee).filter(Employee.id == balance.employee_id).first()
    leave_type = db.query(LeaveType).filter(LeaveType.id == balance.leave_type_id).first()
    total = decimal_to_float(balance.total_days)
    used = decimal_to_float(balance.used_days)
    pending = db.query(func.coalesce(func.sum(LeaveRequest.total_days), 0)).filter(
        LeaveRequest.employee_id == balance.employee_id,
        LeaveRequest.leave_type_id == balance.leave_type_id,
        LeaveRequest.status == "pending",
        LeaveRequest.start_date >= date(balance.year, 1, 1),
        LeaveRequest.start_date <= date(balance.year, 12, 31),
    ).scalar()
    return {
        "id": balance.id,
        "employee_id": balance.employee_id,
        "employee_name": employee_name(employee),
        "leave_type": leave_type.name if leave_type else "Leave",
        "year": balance.year,
        "total_days": total,
        "used_days": used,
        "pending_days": decimal_to_float(pending),
        "available_days": max(0, total - used - decimal_to_float(pending)),
        "carry_forward_days": decimal_to_float(balance.carry_forward_days),
        "updated_by": balance.updated_by,
        "updated_at": balance.updated_at.isoformat() if balance.updated_at else None,
    }


def serialize_attendance(db: Session, record: Attendance) -> dict:
    employee = db.query(Employee).filter(Employee.id == record.employee_id).first()
    status = "checked_out" if record.check_out and record.status == "present" else record.status
    return {
        "id": record.id,
        "employee_id": record.employee_id,
        "employee_name": employee_name(employee),
        "date": record.date.isoformat(),
        "check_in": record.check_in.isoformat() if record.check_in else None,
        "check_out": record.check_out.isoformat() if record.check_out else None,
        "total_hours": decimal_to_float(record.total_hours),
        "status": status,
        "source": record.source,
        "remarks": record.remarks,
    }


def serialize_correction(db: Session, correction: AttendanceCorrection) -> dict:
    employee = db.query(Employee).filter(Employee.id == correction.employee_id).first()
    attendance = db.query(Attendance).filter(Attendance.id == correction.attendance_id).first()
    reviewer = db.query(Employee).filter(Employee.id == correction.reviewed_by).first() if correction.reviewed_by else None
    return {
        "id": correction.id,
        "employee_id": correction.employee_id,
        "employee_name": employee_name(employee),
        "attendance_date": attendance.date.isoformat() if attendance else None,
        "original_check_in": correction.original_check_in.isoformat() if correction.original_check_in else None,
        "original_check_out": correction.original_check_out.isoformat() if correction.original_check_out else None,
        "requested_check_in": correction.requested_check_in.isoformat() if correction.requested_check_in else None,
        "requested_check_out": correction.requested_check_out.isoformat() if correction.requested_check_out else None,
        "reason": correction.reason,
        "status": correction.status,
        "reviewed_by": employee_name(reviewer) if reviewer else None,
        "reviewer_notes": correction.reviewer_notes,
    }


def week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def serialize_timesheet(db: Session, employee_id: str, week_start: date) -> dict:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    entries = db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee_id,
        TimesheetEntry.week_start == week_start,
    ).order_by(TimesheetEntry.work_date.asc(), TimesheetEntry.start_time.asc()).all()
    reviewer = db.query(Employee).filter(Employee.id == entries[0].reviewed_by).first() if entries and entries[0].reviewed_by else None
    working = sum(decimal_to_float(entry.hours) for entry in entries if entry.entry_code != "BRK")
    breaks = sum(decimal_to_float(entry.hours) for entry in entries if entry.entry_code == "BRK")
    overtime = sum(decimal_to_float(entry.overtime_hours) for entry in entries)
    return {
        "employee_id": employee_id,
        "employee_name": employee_name(employee),
        "week_start": week_start.isoformat(),
        "week_end": week_end(week_start).isoformat(),
        "status": entries[0].status if entries else "draft",
        "working_hours": working,
        "break_hours": breaks,
        "total_hours": working + breaks,
        "overtime_hours": overtime,
        "reviewed_by": employee_name(reviewer) if reviewer else None,
        "submitted_at": entries[0].submitted_at.isoformat() if entries and entries[0].submitted_at else None,
        "entries": [
            {
                "date": entry.work_date.isoformat(),
                "code": entry.entry_code,
                "project": entry.project_name,
                "start_time": entry.start_time.isoformat() if entry.start_time else None,
                "end_time": entry.end_time.isoformat() if entry.end_time else None,
                "hours": decimal_to_float(entry.hours),
                "notes": entry.notes,
            }
            for entry in entries
        ],
    }


def overview_counts(db: Session) -> dict:
    today = date.today()
    active_ids = [row[0] for row in db.query(Employee.id).filter(Employee.work_email != "superadmin@reknew.ai", Employee.employment_status == "active").all()]
    todays_records = db.query(Attendance).filter(Attendance.date == today).all()
    present_employee_ids = {record.employee_id for record in todays_records if record.status in {"present", "late", "wfh"}}
    return {
        "pending_leave_requests": db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count(),
        "today_present": len(present_employee_ids),
        "absent": max(0, len(active_ids) - len(present_employee_ids)),
        "late_arrivals": db.query(Attendance).filter(Attendance.date == today, Attendance.status == "late").count(),
        "wfh": db.query(Attendance).filter(Attendance.date == today, Attendance.status == "wfh").count(),
        "checked_out": db.query(Attendance).filter(Attendance.date == today, Attendance.check_out.isnot(None)).count(),
        "pending_attendance_corrections": db.query(AttendanceCorrection).filter(AttendanceCorrection.status == "pending").count(),
        "pending_timesheet_approvals": db.query(TimesheetEntry.employee_id, TimesheetEntry.week_start).filter(TimesheetEntry.status == "submitted").group_by(TimesheetEntry.employee_id, TimesheetEntry.week_start).count(),
    }


@router.get("/dashboard")
async def admin_time_off_dashboard(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    require_admin(db, x_user_id, x_user_email)
    current_year = date.today().year
    employees = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai").order_by(Employee.first_name.asc()).all()
    leave_requests = db.query(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(50).all()
    balances = db.query(LeaveBalance).filter(LeaveBalance.year == current_year).order_by(LeaveBalance.updated_at.desc()).limit(200).all()
    attendance_logs = db.query(Attendance).order_by(Attendance.date.desc(), Attendance.updated_at.desc()).limit(100).all()
    corrections = db.query(AttendanceCorrection).order_by(AttendanceCorrection.created_at.desc()).limit(50).all()
    weeks = db.query(TimesheetEntry.employee_id, TimesheetEntry.week_start).filter(
        TimesheetEntry.status.in_(["submitted", "approved", "rejected"])
    ).group_by(TimesheetEntry.employee_id, TimesheetEntry.week_start).order_by(TimesheetEntry.week_start.desc()).limit(50).all()
    leave_types = db.query(LeaveType).order_by(LeaveType.sort_order.asc()).all()
    return {
        "overview": overview_counts(db),
        "employees": [serialize_employee(employee) for employee in employees],
        "leave_requests": [serialize_leave_request(db, request) for request in leave_requests],
        "leave_balances": [serialize_balance(db, balance) for balance in balances],
        "attendance_logs": [serialize_attendance(db, record) for record in attendance_logs],
        "corrections": [serialize_correction(db, correction) for correction in corrections],
        "timesheets": [serialize_timesheet(db, employee_id, target_week_start) for employee_id, target_week_start in weeks],
        "policies": [
            {
                "id": leave_type.id,
                "name": leave_type.name,
                "code": leave_type.code,
                "default_days": decimal_to_float(leave_type.default_days_per_year),
                "paid": leave_type.is_paid,
                "carry_forward": leave_type.is_carry_forward,
                "max_carry_forward": decimal_to_float(leave_type.max_carry_forward_days),
                "active": leave_type.is_active,
            }
            for leave_type in leave_types
        ],
        "attendance_policies": [
            {"name": "Weekends", "value": "Saturday and Sunday are non-working days"},
            {"name": "Standard working day", "value": "8 working hours excluding breaks"},
            {"name": "Late arrival", "value": "Attendance can be marked late by HR/Admin correction"},
            {"name": "WFH", "value": "Admin can mark attendance as WFH when applicable"},
        ],
    }


@router.post("/leave-requests/{request_id}/decision")
async def decide_leave(
    request_id: str,
    payload: DecisionPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    actor = require_admin(db, x_user_id, x_user_email)
    if payload.decision == "reject" and not payload.reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required.")
    request = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be reviewed.")
    if request.employee_id == actor.id:
        raise HTTPException(status_code=403, detail="You cannot review your own leave request.")
    old = {"status": request.status}
    now = datetime.utcnow()
    request.status = "approved" if payload.decision == "approve" else "rejected"
    request.reviewed_by = actor.id
    request.reviewed_at = now
    request.reviewer_notes = payload.reason
    request.updated_at = now
    if payload.decision == "approve":
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == request.employee_id,
            LeaveBalance.leave_type_id == request.leave_type_id,
            LeaveBalance.year == request.start_date.year,
        ).first()
        if balance:
            balance.used_days = decimal_to_float(balance.used_days) + decimal_to_float(request.total_days)
            balance.updated_by = employee_name(actor)
            balance.updated_at = now
    log_audit(db, actor, f"leave_{request.status}", "leave_request", request.id, old, {"status": request.status}, payload.reason)
    notify(db, request.employee_id, f"Leave request {request.status}", f"Your leave request was {request.status} by {employee_name(actor)}.", "leave_request", request.id)
    db.commit()
    return await admin_time_off_dashboard(db, x_user_id, x_user_email)


@router.put("/leave-balances/{balance_id}")
async def adjust_balance(
    balance_id: str,
    payload: BalanceAdjustmentPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    actor = require_admin(db, x_user_id, x_user_email)
    balance = db.query(LeaveBalance).filter(LeaveBalance.id == balance_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Leave balance not found.")
    old = {
        "total_days": decimal_to_float(balance.total_days),
        "used_days": decimal_to_float(balance.used_days),
        "carry_forward_days": decimal_to_float(balance.carry_forward_days),
    }
    balance.total_days = payload.total_days
    balance.used_days = payload.used_days
    balance.carry_forward_days = payload.carry_forward_days
    balance.updated_by = employee_name(actor)
    balance.updated_at = datetime.utcnow()
    new = {
        "total_days": payload.total_days,
        "used_days": payload.used_days,
        "carry_forward_days": payload.carry_forward_days,
    }
    log_audit(db, actor, "leave_balance_adjusted", "leave_balance", balance.id, old, new, payload.reason)
    notify(db, balance.employee_id, "Leave balance updated", f"Your leave balance was updated by {employee_name(actor)}.", "leave_balance", balance.id)
    db.commit()
    return await admin_time_off_dashboard(db, x_user_id, x_user_email)


@router.put("/attendance/{attendance_id}")
async def update_attendance(
    attendance_id: str,
    payload: AttendanceUpdatePayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    actor = require_admin(db, x_user_id, x_user_email)
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
    old = serialize_attendance(db, record)
    record.check_in = payload.check_in
    record.check_out = payload.check_out
    record.status = "present" if payload.status == "checked_out" else payload.status
    record.source = "manual"
    record.remarks = payload.remarks
    if payload.check_in and payload.check_out:
        record.total_hours = round(max(0, (payload.check_out - payload.check_in).total_seconds() / 3600), 2)
    elif payload.status == "absent":
        record.total_hours = 0
    record.updated_at = datetime.utcnow()
    log_audit(db, actor, "attendance_corrected", "attendance", record.id, old, serialize_attendance(db, record), payload.reason)
    notify(db, record.employee_id, "Attendance corrected", f"Your attendance for {record.date} was corrected by {employee_name(actor)}.", "attendance", record.id)
    db.commit()
    return await admin_time_off_dashboard(db, x_user_id, x_user_email)


@router.post("/corrections/{correction_id}/decision")
async def decide_correction(
    correction_id: str,
    payload: DecisionPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    actor = require_admin(db, x_user_id, x_user_email)
    if payload.decision == "reject" and not payload.reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required.")
    correction = db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
    if not correction:
        raise HTTPException(status_code=404, detail="Attendance correction not found.")
    if correction.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending correction requests can be reviewed.")
    if correction.employee_id == actor.id:
        raise HTTPException(status_code=403, detail="You cannot review your own attendance correction.")
    attendance = db.query(Attendance).filter(Attendance.id == correction.attendance_id).first()
    old = serialize_attendance(db, attendance) if attendance else {}
    now = datetime.utcnow()
    correction.status = "approved" if payload.decision == "approve" else "rejected"
    correction.reviewed_by = actor.id
    correction.reviewed_at = now
    correction.reviewer_notes = payload.reason
    if payload.decision == "approve" and attendance:
        attendance.check_in = correction.requested_check_in
        attendance.check_out = correction.requested_check_out
        if attendance.check_in and attendance.check_out:
            attendance.total_hours = round(max(0, (attendance.check_out - attendance.check_in).total_seconds() / 3600), 2)
        attendance.source = "manual"
        attendance.updated_at = now
    log_audit(db, actor, f"attendance_correction_{correction.status}", "attendance_correction", correction.id, old, serialize_attendance(db, attendance) if attendance else {}, payload.reason)
    notify(db, correction.employee_id, f"Attendance correction {correction.status}", f"Your attendance correction was {correction.status} by {employee_name(actor)}.", "attendance_correction", correction.id)
    db.commit()
    return await admin_time_off_dashboard(db, x_user_id, x_user_email)


@router.post("/timesheets/{employee_id}/{week_start}/decision")
async def decide_timesheet(
    employee_id: str,
    week_start: date,
    payload: DecisionPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    actor = require_admin(db, x_user_id, x_user_email)
    if payload.decision == "reject" and not payload.reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required.")
    entries = db.query(TimesheetEntry).filter(TimesheetEntry.employee_id == employee_id, TimesheetEntry.week_start == week_start).all()
    if not entries:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    if not all(entry.status == "submitted" for entry in entries):
        raise HTTPException(status_code=400, detail="Only submitted timesheets can be reviewed.")
    if employee_id == actor.id:
        raise HTTPException(status_code=403, detail="You cannot review your own timesheet.")
    timesheet_audit_id = entries[0].id
    old = {
        "status": "submitted",
        "entries": len(entries),
        "employee_id": employee_id,
        "week_start": week_start.isoformat(),
    }
    next_status = "approved" if payload.decision == "approve" else "rejected"
    now = datetime.utcnow()
    for entry in entries:
        entry.status = next_status
        entry.reviewed_by = actor.id
        entry.reviewed_at = now
        entry.reviewer_notes = payload.reason
        if entry.overtime_hours and float(entry.overtime_hours) > 0:
            entry.overtime_status = "approved" if payload.decision == "approve" else "rejected"
        entry.updated_at = now
    log_audit(
        db,
        actor,
        f"timesheet_{next_status}",
        "timesheet",
        timesheet_audit_id,
        old,
        {
            "status": next_status,
            "employee_id": employee_id,
            "week_start": week_start.isoformat(),
        },
        payload.reason,
    )
    notify(db, employee_id, f"Timesheet {next_status}", f"Your timesheet for {week_start} to {week_end(week_start)} was {next_status} by {employee_name(actor)}.", "timesheet", entries[0].id)
    db.commit()
    return await admin_time_off_dashboard(db, x_user_id, x_user_email)


@router.get("/reports/{report_type}/csv")
async def export_report(
    report_type: str,
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m")),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    require_admin(db, x_user_id, x_user_email)
    try:
        start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Month must be YYYY-MM.")
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "attendance":
        writer.writerow(["Employee", "Date", "Status", "Check In", "Check Out", "Hours"])
        records = db.query(Attendance).filter(Attendance.date >= start, Attendance.date <= end).order_by(Attendance.date.asc()).all()
        for record in records:
            row = serialize_attendance(db, record)
            writer.writerow([row["employee_name"], row["date"], row["status"], row["check_in"], row["check_out"], row["total_hours"]])
    elif report_type == "leave":
        writer.writerow(["Employee", "Leave Type", "Start", "End", "Days", "Status"])
        requests = db.query(LeaveRequest).filter(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start).order_by(LeaveRequest.start_date.asc()).all()
        for request in requests:
            row = serialize_leave_request(db, request)
            writer.writerow([row["employee_name"], row["leave_type"], row["start_date"], row["end_date"], row["total_days"], row["status"]])
    elif report_type == "overtime":
        writer.writerow(["Employee", "Week Start", "Project", "Date", "Hours", "Overtime", "Status"])
        entries = db.query(TimesheetEntry).filter(TimesheetEntry.work_date >= start, TimesheetEntry.work_date <= end, TimesheetEntry.overtime_hours > 0).order_by(TimesheetEntry.work_date.asc()).all()
        for entry in entries:
            employee = db.query(Employee).filter(Employee.id == entry.employee_id).first()
            writer.writerow([employee_name(employee), entry.week_start, entry.project_name, entry.work_date, decimal_to_float(entry.hours), decimal_to_float(entry.overtime_hours), entry.overtime_status])
    elif report_type == "absenteeism":
        writer.writerow(["Employee", "Absent Days"])
        rows = db.query(Attendance.employee_id, func.count(Attendance.id)).filter(Attendance.date >= start, Attendance.date <= end, Attendance.status == "absent").group_by(Attendance.employee_id).all()
        for employee_id, count in rows:
            employee = db.query(Employee).filter(Employee.id == employee_id).first()
            writer.writerow([employee_name(employee), count])
    else:
        raise HTTPException(status_code=404, detail="Unknown report type.")

    output.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=reknew-{report_type}-{month}.csv"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
