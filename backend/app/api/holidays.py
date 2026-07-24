"""
Employee holiday calendar endpoints.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday
from app.services.settings_service import get_current_employee
from app.services.work_calendar_service import employee_region

router = APIRouter(prefix="/holidays", tags=["Holidays"])


def get_employee(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    return get_current_employee(db, user_id, user_email)


def region_visible(regions: str | None, region: str) -> bool:
    normalized = {item.strip().upper() for item in (regions or "all").split(",") if item.strip()}
    return "ALL" in normalized or region.upper() in normalized


def serialize_holiday(holiday: CompanyHoliday) -> dict:
    return {
        "id": holiday.id,
        "name": holiday.name,
        "holiday_date": holiday.holiday_date,
        "holiday_type": holiday.holiday_type,
        "regions": holiday.regions,
    }


def visible_holidays_query(db: Session, region: str):
    return db.query(CompanyHoliday).filter(
        CompanyHoliday.is_active == True,
        or_(
            CompanyHoliday.regions.ilike("%all%"),
            CompanyHoliday.regions.ilike(f"%{region}%"),
        ),
    )


@router.get("")
async def holidays(
    region: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    selected_region = (region or employee_region(employee)).upper()
    start = from_date or date.today()
    end = to_date or start + timedelta(days=365)
    base_query = db.query(CompanyHoliday).filter(CompanyHoliday.is_active == True) if selected_region == "ALL" else visible_holidays_query(db, selected_region)
    rows = base_query.filter(
        CompanyHoliday.holiday_date >= start,
        CompanyHoliday.holiday_date <= end,
    ).order_by(CompanyHoliday.holiday_date.asc(), CompanyHoliday.name.asc()).all()
    return {"holidays": [serialize_holiday(row) for row in rows if selected_region == "ALL" or region_visible(row.regions, selected_region)]}


@router.get("/available-floating")
async def available_floating_holidays(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    region = employee_region(employee)
    taken_holiday_ids = {
        item.holiday_id
        for item in db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.holiday_id.isnot(None),
            LeaveRequest.status.in_(["pending", "approved"]),
        ).all()
        if item.holiday_id
    }
    rows = visible_holidays_query(db, region).filter(
        CompanyHoliday.holiday_type.in_(["floating", "optional"]),
        CompanyHoliday.holiday_date >= date.today(),
    ).order_by(CompanyHoliday.holiday_date.asc(), CompanyHoliday.name.asc()).all()
    return {
        "holidays": [
            serialize_holiday(row)
            for row in rows
            if row.id not in taken_holiday_ids and region_visible(row.regions, region)
        ],
        "region": region,
    }


@router.get("/working-days")
async def working_days(
    start_date: date = Query(...),
    end_date: date = Query(...),
    region: str | None = Query(default=None),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")
    employee = get_employee(db, x_user_id, x_user_email)
    selected_region = (region or employee_region(employee)).upper()
    rows = visible_holidays_query(db, selected_region).filter(
        CompanyHoliday.holiday_date >= start_date,
        CompanyHoliday.holiday_date <= end_date,
        CompanyHoliday.holiday_type.in_(["public", "company"]),
    ).all()
    holiday_dates = {
        row.holiday_date: row.name
        for row in rows
        if row.holiday_date.weekday() < 5 and region_visible(row.regions, selected_region)
    }
    weekends = 0
    weekdays = 0
    current = start_date
    while current <= end_date:
        if current.weekday() >= 5:
            weekends += 1
        else:
            weekdays += 1
        current += timedelta(days=1)
    return {
        "working_days": max(weekdays - len(holiday_dates), 0),
        "weekends": weekends,
        "holidays": len(holiday_dates),
        "holiday_names": list(holiday_dates.values()),
    }
