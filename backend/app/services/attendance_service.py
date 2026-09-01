from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.leave_attendance import Attendance


@dataclass(frozen=True)
class AttendanceSnapshot:
    id: str | None
    date: date
    check_in: datetime | None
    check_out: datetime | None
    total_hours: float | None
    status: str
    is_checked_in: bool


def employee_joining_date(employee) -> date:
    return employee.date_of_joining or employee.joining_date


def serialize_attendance_record(
    attendance: Attendance | None,
    target_date: date | None = None,
) -> AttendanceSnapshot:
    if not attendance:
        return AttendanceSnapshot(
            id=None,
            date=target_date or date.today(),
            check_in=None,
            check_out=None,
            total_hours=None,
            status="not_checked_in",
            is_checked_in=False,
        )

    total_hours = (
        float(attendance.total_hours)
        if isinstance(attendance.total_hours, Decimal)
        else attendance.total_hours
    )
    return AttendanceSnapshot(
        id=attendance.id,
        date=attendance.date,
        check_in=attendance.check_in,
        check_out=attendance.check_out,
        total_hours=total_hours,
        status=attendance.status,
        is_checked_in=bool(attendance.check_in and not attendance.check_out),
    )


def get_my_attendance_today(
    db: Session,
    employee,
    *,
    today: date | None = None,
) -> AttendanceSnapshot:
    observed = today or date.today()
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == observed,
    ).first()
    return serialize_attendance_record(attendance, observed)


def get_my_attendance_on_date(
    db: Session,
    employee,
    target_date: date,
) -> AttendanceSnapshot:
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == target_date,
    ).first()
    return serialize_attendance_record(attendance, target_date)


def list_my_attendance_history(
    db: Session,
    employee,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    today: date | None = None,
) -> list[AttendanceSnapshot]:
    joining_date = employee_joining_date(employee)
    observed_today = today or date.today()
    effective_to = date_to or observed_today
    effective_from = date_from or max(joining_date, observed_today - timedelta(days=29))
    if effective_from < joining_date:
        raise ValueError("Attendance history cannot start before your joining date.")
    if effective_to > observed_today:
        raise ValueError("Attendance history cannot include future dates.")
    if effective_from > effective_to:
        raise ValueError("From date must be on or before To date.")

    records = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date >= effective_from,
        Attendance.date <= effective_to,
    ).order_by(Attendance.date.desc()).all()
    return [serialize_attendance_record(record) for record in records]

