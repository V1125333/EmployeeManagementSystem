from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.leave_attendance import LeaveType
from app.models.operations import CompanyHoliday


WEEKDAY_ALIASES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}

DEFAULT_WORKING_WEEKDAYS = {0, 1, 2, 3, 4}


def iter_dates(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def region_from_location(work_location: str | None) -> str:
    location = " ".join((work_location or "").lower().replace(",", " ").split())
    if location in {"ae", "uae"} or any(token in location for token in ["dubai", "united arab emirates"]):
        return "AE"
    if location == "in" or any(token in location for token in ["india", "bangalore", "hyderabad", "mumbai", "delhi"]):
        return "IN"
    if location in {"us", "usa"} or any(token in location for token in ["united states", "america"]):
        return "US"
    return "all"


def employee_region(employee: Employee) -> str:
    structured_location = " ".join(
        part.strip()
        for part in [
            getattr(employee, "work_city", None),
            getattr(employee, "work_state", None),
            getattr(employee, "work_country", None),
        ]
        if part and part.strip()
    )
    return region_from_location(
        structured_location
        or getattr(employee, "work_location", None)
        or getattr(employee, "location", None)
    )


def region_visible(regions: str | None, region: str) -> bool:
    values = {item.strip().upper() for item in (regions or "all").split(",") if item.strip()}
    return "ALL" in values or region.upper() in values


def _parse_weekday_value(value: object) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return set()
        if text.startswith("["):
            try:
                return _parse_weekday_value(json.loads(text))
            except Exception:
                pass
        normalized = text.lower().replace("-", "_").replace("/", ",")
        if normalized in {"mon_fri", "monday_friday", "weekday", "weekdays", "standard"}:
            return set(DEFAULT_WORKING_WEEKDAYS)
        tokens = [token.strip().lower() for token in normalized.replace(";", ",").split(",")]
        return {
            WEEKDAY_ALIASES[token]
            for token in tokens
            if token in WEEKDAY_ALIASES
        }
    if isinstance(value, (list, tuple, set)):
        days: set[int] = set()
        for item in value:
            if isinstance(item, int) and 0 <= item <= 6:
                days.add(item)
            else:
                days.update(_parse_weekday_value(str(item)))
        return days
    return set()


def employee_working_weekdays(employee: Employee) -> set[int]:
    for attr in ("working_days", "work_days", "work_schedule", "weekly_working_days"):
        days = _parse_weekday_value(getattr(employee, attr, None))
        if days:
            return days
    return set(DEFAULT_WORKING_WEEKDAYS)


def is_employee_working_day(employee: Employee, target_date: date) -> bool:
    return target_date.weekday() in employee_working_weekdays(employee)


def company_holiday_dates(
    db: Session,
    employee: Employee,
    start_date: date,
    end_date: date,
    holiday_types: set[str] | None = None,
) -> set[date]:
    region = employee_region(employee)
    query = db.query(CompanyHoliday).filter(
        CompanyHoliday.is_active == True,
        CompanyHoliday.holiday_date >= start_date,
        CompanyHoliday.holiday_date <= end_date,
    )
    if holiday_types:
        query = query.filter(CompanyHoliday.holiday_type.in_(sorted(holiday_types)))
    return {
        row.holiday_date
        for row in query.all()
        if region_visible(row.regions, region)
    }


def leave_type_can_apply_on_selected_holiday(leave_type: LeaveType) -> bool:
    return (leave_type.code or "").upper() in {"FL", "OH"}


def payable_leave_dates(
    db: Session,
    employee: Employee,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
) -> list[date]:
    company_holidays = company_holiday_dates(db, employee, start_date, end_date, {"public", "company"})
    allow_selected_holiday = leave_type_can_apply_on_selected_holiday(leave_type)
    days: list[date] = []
    for current in iter_dates(start_date, end_date):
        if not is_employee_working_day(employee, current):
            continue
        if current in company_holidays and not allow_selected_holiday:
            continue
        days.append(current)
    return days


def payable_leave_day_count(
    db: Session,
    employee: Employee,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
    is_half_day: bool = False,
) -> float:
    days = payable_leave_dates(db, employee, leave_type, start_date, end_date)
    return len(days) * (0.5 if is_half_day else 1.0)
