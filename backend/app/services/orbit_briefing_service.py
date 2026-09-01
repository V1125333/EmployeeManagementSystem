"""Read-only data assembly for the legacy Orbit briefing surface."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday, TimesheetEntry
from app.services.work_calendar_service import employee_region


def _employee_name(employee: Employee | None) -> str:
    if not employee:
        return "your manager"
    return f"{employee.first_name} {employee.last_name}".strip()


def _current_week_start(today: date) -> date:
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _weekly_target(employee: Employee, time_zone: str) -> float:
    if "intern" in (employee.workforce_type or "").lower():
        return 20.0
    return 48.0 if time_zone == "Asia/Kolkata" else 40.0


def _manager_for(db: Session, employee: Employee) -> Employee | None:
    if employee.manager_id:
        manager = db.query(Employee).filter(Employee.id == employee.manager_id).first()
        if manager and manager.id != employee.id:
            return manager
    wanted = (employee.reporting_manager or "").strip().lower()
    if not wanted:
        return None
    return next(
        (
            candidate
            for candidate in db.query(Employee).all()
            if candidate.id != employee.id and _employee_name(candidate).lower() == wanted
        ),
        None,
    )


def _deadline_words(deadline: date, today: date) -> str:
    delta = (deadline - today).days
    if delta < 0:
        days = abs(delta)
        return f"{days} day{'s' if days != 1 else ''} overdue"
    if delta == 0:
        return "Due today"
    if delta == 1:
        return "Due tomorrow"
    return f"Due in {delta} days"


def get_action_items(db: Session, employee: Employee, *, today: date | None = None) -> dict:
    """Return employee-scoped briefing facts with navigation actions only."""
    current_date = today or date.today()
    week_start = _current_week_start(current_date)
    week_end = week_start + timedelta(days=6)
    entries = db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee.id,
        TimesheetEntry.week_start == week_start,
    ).all()
    items: list[dict] = []

    if entries and not any(row.status in {"submitted", "approved"} for row in entries):
        work_entries = [row for row in entries if row.entry_code.upper() != "BRK"]
        total = round(sum(float(row.hours or 0) for row in work_entries), 1)
        target = _weekly_target(employee, entries[0].time_zone or "UTC")
        daily = {
            week_start + timedelta(days=offset): round(
                sum(float(row.hours or 0) for row in work_entries if row.work_date == week_start + timedelta(days=offset)),
                1,
            )
            for offset in range(1, 6)
        }
        thin_days = [day.strftime("%A") for day, hours in daily.items() if hours < target / 5]
        noticed = f"{' and '.join(thin_days[:2]) or 'This week'} {'are' if len(thin_days) > 1 else 'is'} thin."
        items.append({
            "key": "timesheet_attention",
            "kind": "timesheet",
            "severity": "due_soon" if (week_end - current_date).days <= 1 else "advisory",
            "title": "This week's timesheet",
            "urgencyLabel": _deadline_words(week_end, current_date),
            "heroValue": f"{total:g}",
            "heroUnit": f"of {target:g} hours logged",
            "weekBars": [
                {
                    "day": day.strftime("%a")[0],
                    "pct": min(100, round(hours / max(target / 5, 1) * 100)),
                    "deficient": hours < target / 5,
                }
                for day, hours in daily.items()
            ],
            "reasoning": f"{noticed} Review the recorded hours before taking any action on the timesheet page.",
            "primaryAction": {
                "type": "navigate",
                "label": "Review timesheet",
                "href": f"/employee/timesheets?week_start={week_start.isoformat()}",
            },
            "dismissLabel": "Later",
        })

    pending_leave = db.query(LeaveRequest, LeaveType).join(
        LeaveType, LeaveRequest.leave_type_id == LeaveType.id
    ).filter(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.status == "pending",
    ).order_by(LeaveRequest.created_at.asc()).first()
    if pending_leave:
        leave_request, leave_type = pending_leave
        manager = _manager_for(db, employee)
        waited = max(0, (current_date - leave_request.created_at.date()).days)
        date_text = (
            leave_request.start_date.strftime("%d %B")
            if leave_request.start_date == leave_request.end_date
            else f"{leave_request.start_date.strftime('%d')}–{leave_request.end_date.strftime('%d %B')}"
        )
        items.append({
            "key": "leave_request_waiting",
            "kind": "leave",
            "severity": "waiting",
            "title": f"{leave_type.name}, {date_text}",
            "urgencyLabel": "Waiting",
            "heroValue": None,
            "heroUnit": None,
            "weekBars": [],
            "reasoning": (
                f"This request has been pending with {_employee_name(manager)} for "
                f"{waited or 'less than one'} day{'s' if waited != 1 else ''}."
            ),
            "primaryAction": {
                "type": "navigate",
                "label": "View request",
                "href": "/employee/apply-leave",
            },
            "dismissLabel": "Leave it",
        })

    priority = {"overdue": 0, "due_soon": 1, "waiting": 2, "advisory": 3}
    items.sort(key=lambda item: priority[item["severity"]])
    return {"items": items, "total": len(items)}


def get_upcoming(db: Session, employee: Employee, *, today: date | None = None) -> dict:
    """Return the next active holiday visible in the actor's region."""
    current_date = today or date.today()
    region = employee_region(employee)
    holiday = db.query(CompanyHoliday).filter(
        CompanyHoliday.is_active.is_(True),
        CompanyHoliday.holiday_date >= current_date,
        or_(
            CompanyHoliday.regions.ilike("%all%"),
            CompanyHoliday.regions.ilike(f"%{region}%"),
        ),
    ).order_by(CompanyHoliday.holiday_date.asc()).first()
    if not holiday:
        return {"item": None}
    return {
        "item": {
            "title": holiday.name,
            "date": holiday.holiday_date.isoformat(),
            "displayDate": holiday.holiday_date.strftime("%d %B"),
            "kind": "holiday",
        }
    }
