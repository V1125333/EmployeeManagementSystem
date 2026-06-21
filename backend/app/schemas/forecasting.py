from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


ForecastStatus = Literal[
    "becoming_available",
    "partially_available",
    "fully_available",
    "overallocated",
    "bench_risk",
]


class ForecastEmployeeRow(BaseModel):
    employee_id: str
    employee_name: str
    department: str | None = None
    designation: str | None = None
    manager_name: str | None = None
    current_allocation_percentage: int
    current_available_percentage: int
    forecast_allocation_percentage: int
    forecast_available_percentage: int
    next_allocation_end_date: date | None = None
    forecast_status: ForecastStatus


class ForecastSummary(BaseModel):
    total_employees: int
    becoming_available_count: int
    fully_available_count: int
    partially_available_count: int
    bench_risk_count: int
    overallocated_count: int


class ForecastBenchRiskRow(BaseModel):
    employee_id: str
    employee_name: str
    department: str | None = None
    manager_name: str | None = None
    date_becoming_available: date | None = None


class ForecastProjectImpactRow(BaseModel):
    project: str
    employee_id: str
    employee_name: str
    role: str | None = None
    allocation_percentage: int
    end_date: date
    days_remaining: int


class ForecastResponse(BaseModel):
    generated_at: datetime
    forecast_window_days: int
    summary: ForecastSummary
    employees: list[ForecastEmployeeRow]
    bench_risk_employees: list[ForecastBenchRiskRow] = []
    projects_losing_resources_soon: list[ForecastProjectImpactRow] = []
