from datetime import date
from typing import Literal

from pydantic import BaseModel


ComplianceStatus = Literal["compliant", "warning", "violation"]
OverallComplianceStatus = Literal["compliant", "warning", "violation", "not_applicable"]


class ProjectComplianceRow(BaseModel):
    project_id: str | None = None
    project_name: str
    allocation_percentage: int
    expected_hours: float
    actual_hours: float
    variance_hours: float
    status: ComplianceStatus


class ComplianceReport(BaseModel):
    employee_id: str
    timesheet_id: str
    week_start: date
    week_end: date
    expected_weekly_hours: float
    used_default_hours: bool
    no_allocations_found: bool
    project_rows: list[ProjectComplianceRow]
    unallocated_hours: float
    total_expected_hours: float
    total_actual_hours: float
    total_variance_hours: float
    overall_status: OverallComplianceStatus
    compliant_threshold: float
    warning_threshold: float
