"""
Deterministic workforce forecasting from allocation data.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.employee import Employee
from app.schemas.forecasting import (
    ForecastBenchRiskRow,
    ForecastEmployeeRow,
    ForecastProjectImpactRow,
    ForecastResponse,
    ForecastSummary,
)


SUPPORTED_FORECAST_WINDOWS = {30, 60, 90}


def employee_name(employee: Employee) -> str:
    middle_name = getattr(employee, "middle_name", None)
    parts = [employee.first_name, middle_name, employee.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip()) or employee.work_email


def manager_name(db: Session, employee: Employee) -> str | None:
    if employee.manager_id:
        manager = db.query(Employee).filter(Employee.id == employee.manager_id).first()
        if manager:
            return employee_name(manager)
    return employee.reporting_manager or None


def active_allocations_for_date(db: Session, employee_id: str, target_date: date) -> list[Allocation]:
    return db.query(Allocation).filter(
        Allocation.employee_id == employee_id,
        Allocation.status.in_(["active", "upcoming"]),
        Allocation.start_date <= target_date,
        or_(Allocation.end_date.is_(None), Allocation.end_date >= target_date),
    ).all()


def allocation_sum(allocations: list[Allocation]) -> int:
    return int(sum(int(allocation.allocation_percentage or 0) for allocation in allocations))


def classify_forecast(
    current_allocation: int,
    forecast_allocation: int,
    next_end_date: date | None,
    cutoff: date,
) -> str:
    if current_allocation > 100 or forecast_allocation > 100:
        return "overallocated"
    if current_allocation > 0 and forecast_allocation == 0 and next_end_date and next_end_date <= cutoff:
        return "bench_risk"
    if forecast_allocation == 0:
        return "fully_available"
    if forecast_allocation < 100:
        if forecast_allocation < current_allocation:
            return "becoming_available"
        return "partially_available"
    if forecast_allocation == 100:
        return "fully_allocated"
    if forecast_allocation < current_allocation:
        return "becoming_available"
    return "overallocated"


def get_workforce_forecast(
    db: Session,
    forecast_window_days: int,
    manager_employee_id: str | None = None,
) -> ForecastResponse:
    if forecast_window_days not in SUPPORTED_FORECAST_WINDOWS:
        raise ValueError("forecast_window_days must be one of 30, 60, or 90.")

    today = date.today()
    cutoff = today + timedelta(days=forecast_window_days)
    query = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai")
    if manager_employee_id:
        manager = db.query(Employee).filter(Employee.id == manager_employee_id).first()
        manager_label = employee_name(manager) if manager else ""
        query = query.filter(
            or_(
                Employee.manager_id == manager_employee_id,
                Employee.reporting_manager == manager_label,
            )
        )

    employees = query.order_by(Employee.first_name.asc(), Employee.last_name.asc()).all()
    employee_rows: list[ForecastEmployeeRow] = []
    bench_risk_rows: list[ForecastBenchRiskRow] = []
    project_impact_rows: list[ForecastProjectImpactRow] = []

    for employee in employees:
        current_allocations = active_allocations_for_date(db, employee.id, today)
        forecast_allocations = active_allocations_for_date(db, employee.id, cutoff)
        current_allocation = allocation_sum(current_allocations)
        forecast_allocation = allocation_sum(forecast_allocations)
        ending_allocations = [
            allocation for allocation in current_allocations
            if allocation.end_date and today <= allocation.end_date <= cutoff
        ]
        next_end_date = min((allocation.end_date for allocation in ending_allocations if allocation.end_date), default=None)
        status = classify_forecast(current_allocation, forecast_allocation, next_end_date, cutoff)
        current_available = max(0, 100 - current_allocation)
        forecast_available = max(0, 100 - forecast_allocation)
        employee_manager_name = manager_name(db, employee)
        row = ForecastEmployeeRow(
            employee_id=employee.id,
            employee_name=employee_name(employee),
            department=employee.department,
            designation=employee.designation,
            manager_name=employee_manager_name,
            current_allocation_percentage=current_allocation,
            current_available_percentage=current_available,
            forecast_allocation_percentage=forecast_allocation,
            forecast_available_percentage=forecast_available,
            next_allocation_end_date=next_end_date,
            forecast_status=status,
        )
        employee_rows.append(row)

        if status == "bench_risk":
            bench_risk_rows.append(ForecastBenchRiskRow(
                employee_id=employee.id,
                employee_name=row.employee_name,
                department=employee.department,
                manager_name=employee_manager_name,
                date_becoming_available=next_end_date,
            ))

        for allocation in ending_allocations:
            project_impact_rows.append(ForecastProjectImpactRow(
                project=allocation.project_name or allocation.project_id or "Unassigned project",
                employee_id=employee.id,
                employee_name=row.employee_name,
                role=allocation.allocation_role,
                allocation_percentage=int(allocation.allocation_percentage or 0),
                end_date=allocation.end_date,
                days_remaining=(allocation.end_date - today).days,
            ))

    counts = {
        "becoming_available": 0,
        "fully_allocated": 0,
        "fully_available": 0,
        "partially_available": 0,
        "bench_risk": 0,
        "overallocated": 0,
    }
    for row in employee_rows:
        counts[row.forecast_status] += 1

    employee_rows.sort(key=lambda item: (
        {
            "overallocated": 0,
            "bench_risk": 1,
            "becoming_available": 2,
            "partially_available": 3,
            "fully_allocated": 4,
            "fully_available": 5,
        }[item.forecast_status],
        item.next_allocation_end_date or date.max,
        item.employee_name.lower(),
    ))
    project_impact_rows.sort(key=lambda item: (item.end_date, item.project.lower(), item.employee_name.lower()))

    return ForecastResponse(
        generated_at=datetime.utcnow(),
        forecast_window_days=forecast_window_days,
        summary=ForecastSummary(
            total_employees=len(employee_rows),
            becoming_available_count=counts["becoming_available"],
            fully_allocated_count=counts["fully_allocated"],
            fully_available_count=counts["fully_available"],
            partially_available_count=counts["partially_available"],
            bench_risk_count=counts["bench_risk"],
            overallocated_count=counts["overallocated"],
        ),
        employees=employee_rows,
        bench_risk_employees=bench_risk_rows,
        projects_losing_resources_soon=project_impact_rows,
    )
