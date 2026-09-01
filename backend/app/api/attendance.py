"""
Employee attendance self-service endpoints.
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.authentication import AuthenticatedActor, get_authenticated_actor
from app.models.leave_attendance import Attendance
from app.services.audit_service import log_audit
from app.services.attendance_service import (
    employee_joining_date,
    get_my_attendance_today,
    list_my_attendance_history,
    serialize_attendance_record,
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


class AttendanceResponse(BaseModel):
    id: str | None = None
    date: date
    check_in: datetime | None = None
    check_out: datetime | None = None
    total_hours: float | None = None
    status: str
    is_checked_in: bool


class AttendanceContextResponse(BaseModel):
    joining_date: date
    today: date


def serialize_attendance(attendance: Attendance | None, target_date: date | None = None) -> AttendanceResponse:
    snapshot = (
        attendance
        if hasattr(attendance, "is_checked_in") and hasattr(attendance, "total_hours")
        else None
    )
    if snapshot is None:
        snapshot = serialize_attendance_record(attendance, target_date)
    return AttendanceResponse(
        id=snapshot.id,
        date=snapshot.date,
        check_in=snapshot.check_in,
        check_out=snapshot.check_out,
        total_hours=snapshot.total_hours,
        status=snapshot.status,
        is_checked_in=snapshot.is_checked_in,
    )


@router.get("/me/today", response_model=AttendanceResponse)
async def my_attendance_today(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    today = date.today()
    return serialize_attendance(get_my_attendance_today(db, employee, today=today), today)


@router.get("/me/context", response_model=AttendanceContextResponse)
async def my_attendance_context(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return AttendanceContextResponse(
        joining_date=employee_joining_date(employee),
        today=date.today(),
    )


@router.post("/me/check-in", response_model=AttendanceResponse)
async def check_in(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    today = date.today()
    now = datetime.utcnow()
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today,
    ).first()

    if attendance and attendance.check_in and not attendance.check_out:
        raise HTTPException(status_code=400, detail="You are already checked in.")
    if attendance and attendance.check_out:
        raise HTTPException(status_code=400, detail="You already checked out today.")

    if not attendance:
        attendance = Attendance(
            employee_id=employee.id,
            date=today,
            status="present",
            source="web",
        )
        db.add(attendance)

    attendance.check_in = now
    attendance.check_out = None
    attendance.total_hours = None
    attendance.status = "present"
    attendance.source = "web"
    attendance.updated_at = now
    db.flush()
    log_audit(
        db,
        employee,
        action="attendance.checked_in",
        entity_type="attendance",
        entity_id=attendance.id,
        new_values={"date": today, "check_in": now, "status": attendance.status, "source": attendance.source},
        source="user",
    )
    db.commit()
    db.refresh(attendance)
    return serialize_attendance(attendance, today)


@router.post("/me/check-out", response_model=AttendanceResponse)
async def check_out(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    today = date.today()
    now = datetime.utcnow()
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today,
    ).first()

    if not attendance or not attendance.check_in:
        raise HTTPException(status_code=400, detail="Check in before checking out.")
    if attendance.check_out:
        raise HTTPException(status_code=400, detail="You already checked out today.")

    total_hours = round((now - attendance.check_in).total_seconds() / 3600, 2)
    old_values = {"check_out": attendance.check_out, "total_hours": attendance.total_hours, "status": attendance.status}
    attendance.check_out = now
    attendance.total_hours = total_hours
    attendance.updated_at = now
    log_audit(
        db,
        employee,
        action="attendance.checked_out",
        entity_type="attendance",
        entity_id=attendance.id,
        old_values=old_values,
        new_values={"check_out": now, "total_hours": total_hours, "status": attendance.status},
        source="user",
    )
    db.commit()
    db.refresh(attendance)
    return serialize_attendance(attendance, today)


@router.get("/me/history", response_model=list[AttendanceResponse])
async def my_attendance_history(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    joining_date = employee_joining_date(employee)
    today = date.today()
    effective_to = date_to or today
    effective_from = date_from or max(joining_date, today - timedelta(days=29))
    if effective_from < joining_date:
        raise HTTPException(status_code=400, detail="Attendance history cannot start before your joining date.")
    if effective_to > today:
        raise HTTPException(status_code=400, detail="Attendance history cannot include future dates.")
    if effective_from > effective_to:
        raise HTTPException(status_code=400, detail="From date must be on or before To date.")

    records = list_my_attendance_history(
        db,
        employee,
        date_from=effective_from,
        date_to=effective_to,
        today=today,
    )
    return [serialize_attendance(record) for record in records]
