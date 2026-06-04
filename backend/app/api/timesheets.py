"""
Employee timesheet self-service endpoints.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import Allocation, Notification, Project, TimesheetEntry
from app.services.settings_service import get_current_employee

router = APIRouter(prefix="/timesheets", tags=["Timesheets"])

ENTRY_CODES = [
    {"code": "PRJ", "label": "Project work", "requires_project": True},
    {"code": "POC", "label": "Proof of concept", "requires_project": False},
    {"code": "BRK", "label": "Break / non-working", "requires_project": False},
    {"code": "TRN", "label": "Training", "requires_project": False},
    {"code": "MTG", "label": "Meetings", "requires_project": False},
    {"code": "ADM", "label": "Admin", "requires_project": False},
]

GENERIC_PROJECTS = [
    {"id": None, "name": "Proof of Concept", "code": "POC"},
    {"id": None, "name": "Break / Non-working", "code": "BRK"},
    {"id": None, "name": "Training", "code": "TRN"},
    {"id": None, "name": "Meetings", "code": "MTG"},
    {"id": None, "name": "Admin", "code": "ADM"},
]


class TimesheetEntryPayload(BaseModel):
    work_date: date
    entry_code: str = Field(..., max_length=10)
    project_id: str | None = None
    project_name: str = Field(..., min_length=1, max_length=200)
    start_time: time
    end_time: time
    notes: str | None = Field(default=None, max_length=500)


class TimesheetSaveRequest(BaseModel):
    week_start: date
    time_zone: str = Field(default="UTC", max_length=80)
    entries: list[TimesheetEntryPayload]


class TimesheetCopyRequest(BaseModel):
    source_week_start: date
    target_week_start: date
    time_zone: str = Field(default="UTC", max_length=80)


class TimesheetDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reviewer_notes: str | None = Field(default=None, max_length=300)


class LeaveDayResponse(BaseModel):
    date: date
    status: str
    leave_type: str
    hours: float


class TimesheetEntryResponse(BaseModel):
    id: str
    work_date: date
    week_start: date
    entry_code: str
    project_id: str | None
    project_name: str
    start_time: time | None
    end_time: time | None
    hours: float
    overtime_hours: float
    overtime_requires_approval: bool
    overtime_status: str
    notes: str | None
    status: str
    submitted_at: datetime | None
    time_zone: str


class TimesheetWeekResponse(BaseModel):
    week_start: date
    week_end: date
    status: str
    total_hours: float
    working_hours: float
    break_hours: float
    leave_hours: float
    regular_hours: float
    overtime_hours: float
    weekly_limit_hours: float
    daily_limit_hours: float | None
    warnings: list[str]
    time_zone: str
    submitted_to: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    reviewer_notes: str | None
    entries: list[TimesheetEntryResponse]
    leave_days: list[LeaveDayResponse]


def get_employee(db: Session, user_id: str | None, user_email: str | None):
    return get_current_employee(db, user_id, user_email)


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown"
    return f"{employee.first_name} {employee.last_name}".strip()


def is_admin(role: str | None) -> bool:
    normalized = (role or "").lower().replace(" ", "_")
    return normalized in {"super_admin", "admin", "hr_admin", "global_access"}


def create_notification(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    related_entity_id: str,
) -> None:
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        type="timesheet",
        notification_type="timesheet",
        related_entity_type="timesheet",
        related_entity_id=related_entity_id,
        link_url="/employee/timesheets",
    ))


def manager_for_employee(db: Session, employee: Employee) -> Employee | None:
    if not employee.reporting_manager:
        return None
    manager_name = employee.reporting_manager.strip().lower()
    for candidate in db.query(Employee).all():
        if candidate.id != employee.id and employee_name(candidate).lower() == manager_name:
            return candidate
    return None


def reviewer_name_for_entries(db: Session, entries: list[TimesheetEntry]) -> str | None:
    reviewer_id = next((entry.reviewed_by for entry in entries if entry.reviewed_by), None)
    if not reviewer_id:
        return None
    return employee_name(db.query(Employee).filter(Employee.id == reviewer_id).first())


def serialize_employee_week(
    db: Session,
    employee: Employee,
    week_start: date,
    entries: list[TimesheetEntry],
    requested_time_zone: str = "UTC",
) -> TimesheetWeekResponse:
    return serialize_week(
        week_start,
        entries,
        employee.workforce_type,
        requested_time_zone,
        leave_days_for_week(db, employee.id, week_start),
        submitted_to=employee.reporting_manager,
        reviewed_by_name=reviewer_name_for_entries(db, entries),
    )


def week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def serialize_entry(entry: TimesheetEntry, overtime_override: float | None = None) -> TimesheetEntryResponse:
    hours = float(entry.hours) if isinstance(entry.hours, Decimal) else entry.hours
    stored_overtime = float(entry.overtime_hours) if isinstance(entry.overtime_hours, Decimal) else entry.overtime_hours
    overtime_hours = overtime_override if overtime_override is not None else stored_overtime
    return TimesheetEntryResponse(
        id=entry.id,
        work_date=entry.work_date,
        week_start=entry.week_start,
        entry_code=entry.entry_code,
        project_id=entry.project_id,
        project_name=entry.project_name,
        start_time=entry.start_time,
        end_time=entry.end_time,
        hours=hours,
        overtime_hours=overtime_hours or 0,
        overtime_requires_approval=(overtime_hours or 0) > 0,
        overtime_status="pending" if (overtime_hours or 0) > 0 else "none",
        notes=entry.notes,
        status=entry.status,
        submitted_at=entry.submitted_at,
        time_zone=entry.time_zone,
    )


def work_policy(workforce_type: str, time_zone: str) -> dict:
    normalized_workforce = (workforce_type or "").lower()
    if "intern" in normalized_workforce:
        return {
            "region": "Intern",
            "daily_limit_hours": None,
            "weekly_limit_hours": 20.0,
        }
    if time_zone == "Asia/Kolkata":
        return {
            "region": "India",
            "daily_limit_hours": 9.0,
            "weekly_limit_hours": 48.0,
        }
    if time_zone.startswith("America/"):
        return {
            "region": "USA",
            "daily_limit_hours": None,
            "weekly_limit_hours": 40.0,
        }
    return {
        "region": "Default",
        "daily_limit_hours": 8.0,
        "weekly_limit_hours": 40.0,
    }


def week_warnings(total_work_hours: float, overtime_hours: float, policy: dict) -> list[str]:
    if overtime_hours <= 0:
        return []
    overtime_label = f"{overtime_hours:g}h"
    weekly_limit_label = f"{policy['weekly_limit_hours']:g}h"
    return [
        f"You have {overtime_label} of overtime this week.",
        f"Your standard limit is {weekly_limit_label} for this week. Overtime will be sent to your manager for approval when you submit the timesheet.",
    ]


def serialize_week(
    week_start: date,
    entries: list[TimesheetEntry],
    workforce_type: str = "",
    requested_time_zone: str = "UTC",
    leave_days: list[LeaveDayResponse] | None = None,
    submitted_to: str | None = None,
    reviewed_by_name: str | None = None,
) -> TimesheetWeekResponse:
    leave_days = leave_days or []
    leave_dates = {item.date for item in leave_days}
    entries = [entry for entry in entries if entry.work_date.weekday() not in {5, 6}]
    entries = [entry for entry in entries if entry.work_date not in leave_dates]
    statuses = {entry.status for entry in entries}
    status = "not_started"
    if "approved" in statuses:
        status = "approved"
    elif "rejected" in statuses:
        status = "rejected"
    elif "submitted" in statuses:
        status = "submitted"
    elif entries:
        status = "draft"
    time_zone = entries[0].time_zone if entries else requested_time_zone
    policy = work_policy(workforce_type, time_zone)
    total_hours = round(sum(float(entry.hours) for entry in entries), 2)
    break_hours = round(sum(float(entry.hours) for entry in entries if entry.entry_code == "BRK"), 2)
    working_hours = round(sum(float(entry.hours) for entry in entries if entry.entry_code != "BRK"), 2)
    recalculation_payloads = [
        TimesheetEntryPayload(
            work_date=entry.work_date,
            entry_code=entry.entry_code,
            project_id=entry.project_id,
            project_name=entry.project_name,
            start_time=entry.start_time or time(9, 0),
            end_time=entry.end_time or time(17, 0),
            notes=entry.notes,
        )
        for entry in entries
    ]
    overtime_map = overtime_by_payload(recalculation_payloads, policy)
    overtime_hours = round(sum(overtime_map.values()), 2)
    leave_hours = round(sum(item.hours for item in leave_days), 2)
    reviewed_by = None
    reviewed_at = None
    reviewer_notes = None
    if entries:
        reviewed_at = entries[0].reviewed_at
        reviewer_notes = entries[0].reviewer_notes
        if entries[0].reviewed_by:
            reviewed_by = reviewed_by_name or entries[0].reviewed_by
    return TimesheetWeekResponse(
        week_start=week_start,
        week_end=week_end(week_start),
        status=status,
        total_hours=total_hours,
        working_hours=working_hours,
        break_hours=break_hours,
        leave_hours=leave_hours,
        regular_hours=round(working_hours - overtime_hours, 2),
        overtime_hours=overtime_hours,
        weekly_limit_hours=policy["weekly_limit_hours"],
        daily_limit_hours=policy["daily_limit_hours"],
        warnings=week_warnings(working_hours, overtime_hours, policy),
        time_zone=time_zone,
        submitted_to=submitted_to,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        reviewer_notes=reviewer_notes,
        entries=[serialize_entry(entry, overtime_map.get(index, 0.0)) for index, entry in enumerate(entries)],
        leave_days=leave_days,
    )


def validate_code(payload: TimesheetEntryPayload) -> None:
    valid_codes = {item["code"] for item in ENTRY_CODES}
    code = payload.entry_code.upper()
    if code not in valid_codes:
        raise HTTPException(status_code=400, detail=f"Unsupported timesheet code: {payload.entry_code}")
    if code == "PRJ" and not payload.project_id:
        raise HTTPException(status_code=400, detail="Project work requires a project selection.")
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time. Split overnight work into separate days.")


def entry_hours(payload: TimesheetEntryPayload) -> float:
    start_dt = datetime.combine(payload.work_date, payload.start_time)
    end_dt = datetime.combine(payload.work_date, payload.end_time)
    return round((end_dt - start_dt).total_seconds() / 3600, 2)


def overtime_by_payload(entries: list[TimesheetEntryPayload], policy: dict) -> dict[int, float]:
    overtime: dict[int, float] = {}
    weekly_work_total = 0.0
    daily_totals: dict[date, float] = {}
    indexed_entries = sorted(
        enumerate(entries),
        key=lambda item: (item[1].work_date, item[1].start_time, item[0]),
    )

    for index, entry in indexed_entries:
        hours = entry_hours(entry)
        if entry.entry_code.upper() == "BRK":
            overtime[index] = 0.0
            continue

        daily_before = daily_totals.get(entry.work_date, 0.0)
        weekly_before = weekly_work_total
        daily_after = daily_before + hours
        weekly_after = weekly_before + hours

        daily_limit = policy["daily_limit_hours"]
        daily_overtime = 0.0
        if daily_limit is not None:
            daily_overtime = max(0.0, daily_after - daily_limit) - max(0.0, daily_before - daily_limit)
        weekly_overtime = max(0.0, weekly_after - policy["weekly_limit_hours"]) - max(0.0, weekly_before - policy["weekly_limit_hours"])
        entry_overtime = min(hours, max(daily_overtime, weekly_overtime))

        overtime[index] = round(entry_overtime, 2)
        daily_totals[entry.work_date] = daily_after
        weekly_work_total = weekly_after

    return overtime


def leave_days_for_week(db: Session, employee_id: str, target_week_start: date) -> list[LeaveDayResponse]:
    target_week_end = week_end(target_week_start)
    requests = db.query(LeaveRequest, LeaveType).join(
        LeaveType,
        LeaveType.id == LeaveRequest.leave_type_id,
    ).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= target_week_end,
        LeaveRequest.end_date >= target_week_start,
    ).all()

    leave_days: list[LeaveDayResponse] = []
    for request, leave_type in requests:
        current = max(request.start_date, target_week_start)
        end = min(request.end_date, target_week_end)
        hours = 4.0 if request.is_half_day else 8.0
        while current <= end:
            leave_days.append(LeaveDayResponse(
                date=current,
                status=request.status,
                leave_type=leave_type.name,
                hours=hours,
            ))
            current += timedelta(days=1)
    return leave_days


def locked_leave_dates(db: Session, employee_id: str, target_week_start: date) -> set[date]:
    return {item.date for item in leave_days_for_week(db, employee_id, target_week_start)}


def assert_no_leave_conflicts(entries: list[TimesheetEntryPayload], leave_dates: set[date]) -> None:
    blocked = sorted({entry.work_date for entry in entries if entry.work_date in leave_dates})
    if blocked:
        formatted = ", ".join(day.isoformat() for day in blocked)
        raise HTTPException(
            status_code=400,
            detail=f"Timesheet entries cannot be added on pending or approved leave dates: {formatted}.",
        )


def assert_no_weekend_entries(entries: list[TimesheetEntryPayload]) -> None:
    blocked = sorted({entry.work_date for entry in entries if entry.work_date.weekday() in {5, 6}})
    if blocked:
        formatted = ", ".join(day.isoformat() for day in blocked)
        raise HTTPException(
            status_code=400,
            detail=f"Timesheet entries cannot be added on Saturday or Sunday: {formatted}.",
        )


def load_week_entries(db: Session, employee_id: str, target_week_start: date) -> list[TimesheetEntry]:
    return db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee_id,
        TimesheetEntry.week_start == target_week_start,
    ).order_by(TimesheetEntry.work_date.asc(), TimesheetEntry.project_name.asc()).all()


@router.get("/me/options")
async def my_timesheet_options(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    today = date.today()
    allocated_projects = db.query(Project).join(Allocation, Allocation.project_id == Project.id).filter(
        Allocation.employee_id == employee.id,
        Allocation.is_active == True,
        Allocation.start_date <= today,
        or_(Allocation.end_date.is_(None), Allocation.end_date >= today),
    ).order_by(Project.name.asc()).all()

    active_projects = db.query(Project).filter(Project.status.in_(["active", "planning"])).order_by(Project.name.asc()).all()
    projects = allocated_projects or active_projects
    return {
        "entry_codes": ENTRY_CODES,
        "projects": [
            {"id": project.id, "name": project.name, "code": project.code}
            for project in projects
        ] + GENERIC_PROJECTS,
        "requires_timesheet": employee.workforce_type.lower() not in {"unpaid intern", "volunteer"},
        "workforce_type": employee.workforce_type,
    }


@router.get("/me/week", response_model=TimesheetWeekResponse)
async def my_timesheet_week(
    week_start: date = Query(...),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    return serialize_employee_week(db, employee, week_start, load_week_entries(db, employee.id, week_start))


@router.post("/me/week", response_model=TimesheetWeekResponse)
async def save_my_timesheet_week(
    payload: TimesheetSaveRequest,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    existing = load_week_entries(db, employee.id, payload.week_start)
    if any(entry.status in {"submitted", "approved"} for entry in existing):
        raise HTTPException(status_code=400, detail="Submitted or approved timesheets cannot be edited.")

    for entry in payload.entries:
        validate_code(entry)
    assert_no_weekend_entries(payload.entries)
    assert_no_leave_conflicts(payload.entries, locked_leave_dates(db, employee.id, payload.week_start))
    policy = work_policy(employee.workforce_type, payload.time_zone)
    overtime_map = overtime_by_payload(payload.entries, policy)

    db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee.id,
        TimesheetEntry.week_start == payload.week_start,
        TimesheetEntry.status.in_(["draft", "rejected"]),
    ).delete(synchronize_session=False)

    now = datetime.utcnow()
    for index, entry in enumerate(payload.entries):
        hours = entry_hours(entry)
        if hours <= 0:
            continue
        overtime_hours = overtime_map.get(index, 0.0)
        db.add(TimesheetEntry(
            employee_id=employee.id,
            work_date=entry.work_date,
            week_start=payload.week_start,
            entry_code=entry.entry_code.upper(),
            project_id=entry.project_id,
            project_name=entry.project_name,
            start_time=entry.start_time,
            end_time=entry.end_time,
            hours=hours,
            overtime_hours=overtime_hours,
            overtime_requires_approval=overtime_hours > 0,
            overtime_status="pending" if overtime_hours > 0 else "none",
            notes=entry.notes,
            status="draft",
            time_zone=payload.time_zone,
            created_at=now,
            updated_at=now,
        ))
    db.commit()
    return serialize_employee_week(db, employee, payload.week_start, load_week_entries(db, employee.id, payload.week_start), payload.time_zone)


@router.post("/me/week/submit", response_model=TimesheetWeekResponse)
async def submit_my_timesheet_week(
    payload: TimesheetSaveRequest,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    await save_my_timesheet_week(payload, db, x_user_id, x_user_email)
    employee = get_employee(db, x_user_id, x_user_email)
    entries = load_week_entries(db, employee.id, payload.week_start)
    if not entries:
        raise HTTPException(status_code=400, detail="Add at least one timesheet entry before submitting.")
    now = datetime.utcnow()
    for entry in entries:
        entry.status = "submitted"
        entry.submitted_at = now
        entry.updated_at = now
    manager = manager_for_employee(db, employee)
    notification_targets = []
    if manager:
        notification_targets.append(manager)
    notification_targets.extend(db.query(Employee).filter(Employee.role.in_(["super_admin", "admin", "hr_admin", "global_access"])).all())
    seen_targets = set()
    for target in notification_targets:
        if not target or target.id in seen_targets:
            continue
        seen_targets.add(target.id)
        create_notification(
            db,
            target.id,
            "Timesheet submitted",
            f"{employee_name(employee)} submitted a timesheet for {payload.week_start} to {week_end(payload.week_start)}.",
            entries[0].id,
        )
    db.commit()
    return serialize_employee_week(db, employee, payload.week_start, load_week_entries(db, employee.id, payload.week_start), payload.time_zone)


@router.post("/me/week/recall", response_model=TimesheetWeekResponse)
async def recall_my_timesheet_week(
    week_start: date = Query(...),
    time_zone: str = Query("UTC"),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    entries = load_week_entries(db, employee.id, week_start)
    if not entries:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    if not any(entry.status == "submitted" for entry in entries):
        raise HTTPException(status_code=400, detail="Only submitted timesheets can be recalled.")

    now = datetime.utcnow()
    for entry in entries:
        entry.status = "draft"
        entry.submitted_at = None
        entry.reviewed_by = None
        entry.reviewed_at = None
        entry.reviewer_notes = None
        entry.updated_at = now
    manager = manager_for_employee(db, employee)
    if manager:
        create_notification(
            db,
            manager.id,
            "Timesheet recalled",
            f"{employee_name(employee)} recalled the timesheet for {week_start} to {week_end(week_start)}.",
            entries[0].id,
        )
    db.commit()
    return serialize_employee_week(db, employee, week_start, load_week_entries(db, employee.id, week_start), time_zone)


@router.post("/me/week/copy", response_model=TimesheetWeekResponse)
async def copy_my_timesheet_week(
    payload: TimesheetCopyRequest,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    target_existing = load_week_entries(db, employee.id, payload.target_week_start)
    if any(entry.status in {"submitted", "approved"} for entry in target_existing):
        raise HTTPException(status_code=400, detail="Recall the submitted target week before copying into it. Approved weeks cannot be changed.")

    source_entries = load_week_entries(db, employee.id, payload.source_week_start)
    if not source_entries:
        raise HTTPException(status_code=404, detail="Source timesheet has no entries to copy.")

    offset_days = (payload.target_week_start - payload.source_week_start).days
    copied_payloads = [
        TimesheetEntryPayload(
            work_date=entry.work_date + timedelta(days=offset_days),
            entry_code=entry.entry_code,
            project_id=entry.project_id,
            project_name=entry.project_name,
            start_time=entry.start_time or time(9, 0),
            end_time=entry.end_time or time(17, 0),
            notes=entry.notes,
        )
        for entry in source_entries
    ]
    assert_no_weekend_entries(copied_payloads)
    assert_no_leave_conflicts(copied_payloads, locked_leave_dates(db, employee.id, payload.target_week_start))

    db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee.id,
        TimesheetEntry.week_start == payload.target_week_start,
        TimesheetEntry.status.in_(["draft", "rejected"]),
    ).delete(synchronize_session=False)

    now = datetime.utcnow()
    policy = work_policy(employee.workforce_type, payload.time_zone)
    overtime_map = overtime_by_payload(copied_payloads, policy)
    for index, entry in enumerate(copied_payloads):
        hours = entry_hours(entry)
        overtime_hours = overtime_map.get(index, 0.0)
        db.add(TimesheetEntry(
            employee_id=employee.id,
            work_date=entry.work_date,
            week_start=payload.target_week_start,
            entry_code=entry.entry_code,
            project_id=entry.project_id,
            project_name=entry.project_name,
            start_time=entry.start_time,
            end_time=entry.end_time,
            hours=hours,
            overtime_hours=overtime_hours,
            overtime_requires_approval=overtime_hours > 0,
            overtime_status="pending" if overtime_hours > 0 else "none",
            notes=entry.notes,
            status="draft",
            time_zone=payload.time_zone,
            created_at=now,
            updated_at=now,
        ))
    db.commit()
    return serialize_employee_week(db, employee, payload.target_week_start, load_week_entries(db, employee.id, payload.target_week_start), payload.time_zone)


@router.delete("/me/week", response_model=TimesheetWeekResponse)
async def delete_my_timesheet_week(
    week_start: date = Query(...),
    time_zone: str = Query("UTC"),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    existing = load_week_entries(db, employee.id, week_start)
    if any(entry.status in {"submitted", "approved"} for entry in existing):
        raise HTTPException(status_code=400, detail="Submitted or approved timesheets cannot be deleted.")
    db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee.id,
        TimesheetEntry.week_start == week_start,
    ).delete(synchronize_session=False)
    db.commit()
    return serialize_employee_week(db, employee, week_start, [], time_zone)


def serialize_timesheet_approval(db: Session, employee: Employee, week_start: date) -> dict:
    entries = load_week_entries(db, employee.id, week_start)
    week = serialize_employee_week(
        db,
        employee,
        week_start,
        entries,
        entries[0].time_zone if entries else "UTC",
    )
    submitted_at = min((entry.submitted_at for entry in entries if entry.submitted_at), default=None)
    reviewer = db.query(Employee).filter(Employee.id == entries[0].reviewed_by).first() if entries and entries[0].reviewed_by else None
    return {
        "employee_id": employee.id,
        "employee_name": employee_name(employee),
        "reporting_manager": employee.reporting_manager,
        "week_start": week.week_start,
        "week_end": week.week_end,
        "status": week.status,
        "total_hours": week.total_hours,
        "working_hours": week.working_hours,
        "break_hours": week.break_hours,
        "leave_hours": week.leave_hours,
        "regular_hours": week.regular_hours,
        "overtime_hours": week.overtime_hours,
        "submitted_at": submitted_at,
        "reviewed_by": employee_name(reviewer) if reviewer else None,
        "reviewer_notes": entries[0].reviewer_notes if entries else None,
        "entries": [entry.model_dump(mode="json") for entry in week.entries],
        "leave_days": [leave.model_dump(mode="json") for leave in week.leave_days],
    }


@router.get("/approvals")
async def timesheet_approvals(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    reviewer = get_employee(db, x_user_id, x_user_email)
    query = db.query(TimesheetEntry.employee_id, TimesheetEntry.week_start).join(
        Employee,
        Employee.id == TimesheetEntry.employee_id,
    ).filter(
        TimesheetEntry.status == "submitted",
    )
    if not is_admin(reviewer.role):
        query = query.filter(Employee.reporting_manager == employee_name(reviewer))
    rows = query.group_by(TimesheetEntry.employee_id, TimesheetEntry.week_start).order_by(TimesheetEntry.week_start.desc()).all()
    approvals = []
    for employee_id, target_week_start in rows:
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if employee:
            approvals.append(serialize_timesheet_approval(db, employee, target_week_start))
    return {"approvals": approvals}


@router.post("/approvals/{employee_id}/{week_start}/decision")
async def decide_timesheet(
    employee_id: str,
    week_start: date,
    payload: TimesheetDecisionRequest,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    reviewer = get_employee(db, x_user_id, x_user_email)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if not is_admin(reviewer.role) and employee.reporting_manager != employee_name(reviewer):
        raise HTTPException(status_code=403, detail="Not authorized to review this timesheet.")

    entries = load_week_entries(db, employee.id, week_start)
    if not entries:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    if not all(entry.status == "submitted" for entry in entries):
        raise HTTPException(status_code=400, detail="Only submitted timesheets can be reviewed.")

    now = datetime.utcnow()
    next_status = "approved" if payload.decision == "approve" else "rejected"
    for entry in entries:
        entry.status = next_status
        entry.reviewed_by = reviewer.id
        entry.reviewed_at = now
        entry.reviewer_notes = payload.reviewer_notes
        if entry.overtime_hours and float(entry.overtime_hours) > 0:
            entry.overtime_status = "approved" if payload.decision == "approve" else "rejected"
        entry.updated_at = now
    create_notification(
        db,
        employee.id,
        f"Timesheet {next_status}",
        f"Your timesheet for {week_start} to {week_end(week_start)} was {next_status} by {employee_name(reviewer)}."
        + (f" Note: {payload.reviewer_notes}" if payload.reviewer_notes else ""),
        entries[0].id,
    )
    db.commit()
    return await timesheet_approvals(db, x_user_id, x_user_email)


@router.get("/me/history", response_model=list[TimesheetWeekResponse])
async def my_timesheet_history(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    week_rows = db.query(TimesheetEntry.week_start).filter(
        TimesheetEntry.employee_id == employee.id,
    ).group_by(TimesheetEntry.week_start).order_by(TimesheetEntry.week_start.desc()).limit(12).all()
    weeks = []
    for row in week_rows:
        target_week_start = row[0]
        weeks.append(serialize_employee_week(
            db,
            employee,
            target_week_start,
            load_week_entries(db, employee.id, target_week_start),
        ))
    return weeks
