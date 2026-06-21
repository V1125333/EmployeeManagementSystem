"""
Read-only timesheet allocation compliance calculations.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from re import sub

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.operations import Allocation, TimesheetEntry
from app.schemas.compliance import ComplianceReport, ProjectComplianceRow


def _week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def _hours(value: float | Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _normalize(value: str | None) -> str:
    return sub(r"\s+", " ", (value or "").strip().lower())


def _allocation_key(project_id: str | None, project_name: str | None) -> str:
    return project_id or f"name:{_normalize(project_name)}"


def _work_policy(workforce_type: str | None, time_zone: str | None) -> tuple[float, bool]:
    normalized_workforce = (workforce_type or "").lower()
    if "intern" in normalized_workforce:
        return 20.0, False
    if time_zone == "Asia/Kolkata":
        return 48.0, False
    if (time_zone or "").startswith("America/"):
        return 40.0, False
    return 40.0, True


def _row_status(variance_hours: float) -> str:
    variance = abs(variance_hours)
    if variance <= settings.COMPLIANCE_COMPLIANT_THRESHOLD_HOURS:
        return "compliant"
    if variance <= settings.COMPLIANCE_WARNING_THRESHOLD_HOURS:
        return "warning"
    return "violation"


def _worse_status(current: str, candidate: str) -> str:
    order = {"compliant": 0, "warning": 1, "violation": 2}
    return candidate if order[candidate] > order[current] else current


def calculate_compliance(db: Session, employee_id: str, timesheet_id: str) -> ComplianceReport:
    seed_entry = db.query(TimesheetEntry).filter(TimesheetEntry.id == timesheet_id).first()
    if not seed_entry or seed_entry.employee_id != employee_id:
        raise HTTPException(status_code=404, detail="Timesheet not found.")

    employee = db.query(Employee).filter(Employee.id == seed_entry.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    week_start = seed_entry.week_start
    target_week_end = _week_end(week_start)
    expected_weekly_hours, used_default_hours = _work_policy(employee.workforce_type, seed_entry.time_zone)

    allocations = db.query(Allocation).filter(
        Allocation.employee_id == employee.id,
        Allocation.status == "active",
        Allocation.start_date <= target_week_end,
        or_(Allocation.end_date.is_(None), Allocation.end_date >= week_start),
    ).order_by(Allocation.project_name.asc(), Allocation.start_date.asc()).all()

    entries = db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee.id,
        TimesheetEntry.week_start == week_start,
    ).all()
    work_entries = [entry for entry in entries if entry.entry_code.upper() != "BRK"]

    actual_by_key: dict[str, float] = {}
    for entry in work_entries:
        key = _allocation_key(entry.project_id, entry.project_name)
        actual_by_key[key] = actual_by_key.get(key, 0.0) + _hours(entry.hours)

    project_rows: list[ProjectComplianceRow] = []
    matched_keys: set[str] = set()
    overall_status = "compliant"

    for allocation in allocations:
        key = _allocation_key(allocation.project_id, allocation.project_name)
        matched_keys.add(key)
        actual_hours = round(actual_by_key.get(key, 0.0), 2)
        allocation_percentage = int(allocation.allocation_percentage or 0)
        expected_hours = round(expected_weekly_hours * allocation_percentage / 100, 2)
        variance_hours = round(actual_hours - expected_hours, 2)
        status = _row_status(variance_hours)
        overall_status = _worse_status(overall_status, status)
        project_rows.append(ProjectComplianceRow(
            project_id=allocation.project_id,
            project_name=allocation.project_name or "Unnamed allocation",
            allocation_percentage=allocation_percentage,
            expected_hours=expected_hours,
            actual_hours=actual_hours,
            variance_hours=variance_hours,
            status=status,
        ))

    unallocated_hours = round(
        sum(hours for key, hours in actual_by_key.items() if key not in matched_keys),
        2,
    )
    if allocations:
        unallocated_status = _row_status(unallocated_hours)
        overall_status = _worse_status(overall_status, unallocated_status)
    else:
        overall_status = "not_applicable"

    total_expected_hours = round(sum(row.expected_hours for row in project_rows), 2)
    total_actual_hours = round(sum(row.actual_hours for row in project_rows) + unallocated_hours, 2)

    return ComplianceReport(
        employee_id=employee.id,
        timesheet_id=timesheet_id,
        week_start=week_start,
        week_end=target_week_end,
        expected_weekly_hours=expected_weekly_hours,
        used_default_hours=used_default_hours,
        no_allocations_found=len(allocations) == 0,
        project_rows=project_rows,
        unallocated_hours=unallocated_hours,
        total_expected_hours=total_expected_hours,
        total_actual_hours=total_actual_hours,
        total_variance_hours=round(total_actual_hours - total_expected_hours, 2),
        overall_status=overall_status,
        compliant_threshold=settings.COMPLIANCE_COMPLIANT_THRESHOLD_HOURS,
        warning_threshold=settings.COMPLIANCE_WARNING_THRESHOLD_HOURS,
    )
