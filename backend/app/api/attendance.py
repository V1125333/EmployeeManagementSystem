"""
Employee attendance self-service endpoints.
"""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.leave_attendance import Attendance
from app.services.audit_service import log_audit
from app.services.settings_service import get_current_employee

router = APIRouter(prefix="/attendance", tags=["Attendance"])


class AttendanceResponse(BaseModel):
    id: str | None = None
    date: date
    check_in: datetime | None = None
    check_out: datetime | None = None
    total_hours: float | None = None
    status: str
    is_checked_in: bool


def serialize_attendance(attendance: Attendance | None, target_date: date | None = None) -> AttendanceResponse:
    if not attendance:
        return AttendanceResponse(
            date=target_date or date.today(),
            status="not_checked_in",
            is_checked_in=False,
        )

    is_checked_in = bool(attendance.check_in and not attendance.check_out)
    total_hours = float(attendance.total_hours) if isinstance(attendance.total_hours, Decimal) else attendance.total_hours
    return AttendanceResponse(
        id=attendance.id,
        date=attendance.date,
        check_in=attendance.check_in,
        check_out=attendance.check_out,
        total_hours=total_hours,
        status=attendance.status,
        is_checked_in=is_checked_in,
    )


def current_employee(
    db: Session,
    x_user_id: str | None,
    x_user_email: str | None,
):
    return get_current_employee(db, x_user_id, x_user_email)


@router.get("/me/today", response_model=AttendanceResponse)
async def my_attendance_today(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee(db, x_user_id, x_user_email)
    today = date.today()
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today,
    ).first()
    return serialize_attendance(attendance, today)


@router.post("/me/check-in", response_model=AttendanceResponse)
async def check_in(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee(db, x_user_id, x_user_email)
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
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee(db, x_user_id, x_user_email)
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
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee(db, x_user_id, x_user_email)
    records = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
    ).order_by(Attendance.date.desc()).limit(30).all()
    return [serialize_attendance(record) for record in records]
