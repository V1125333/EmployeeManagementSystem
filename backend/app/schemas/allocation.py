from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


BillingType = Literal["billable", "non_billable", "internal"]
AllocationStatus = Literal["active", "upcoming", "completed", "cancelled"]


class AllocationCreate(BaseModel):
    employee_id: str
    manager_id: str
    allocation_percentage: int = Field(..., ge=1, le=100)
    allocation_role: str
    billing_type: BillingType
    start_date: date
    project_id: str | None = None
    project_name: str | None = None
    end_date: date | None = None
    status: AllocationStatus = "active"
    notes: str | None = None


class AllocationUpdate(BaseModel):
    employee_id: str | None = None
    manager_id: str | None = None
    allocation_percentage: int | None = Field(None, ge=1, le=100)
    allocation_role: str | None = None
    billing_type: BillingType | None = None
    start_date: date | None = None
    project_id: str | None = None
    project_name: str | None = None
    end_date: date | None = None
    status: AllocationStatus | None = None
    notes: str | None = None


class AllocationOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str | None = None
    employee_email: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    manager_id: str
    manager_name: str | None = None
    allocation_percentage: int
    allocation_role: str
    billing_type: str
    status: str
    start_date: date
    end_date: date | None = None
    notes: str | None = None
    created_by: str
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AllocationSummary(BaseModel):
    project_id: str | None = None
    project_name: str | None = None
    manager_name: str | None = None
    role: str
    allocation_percentage: int
    billing_type: str
    status: str
    start_date: date
    end_date: date | None = None


class AllocationSummaryOut(BaseModel):
    total_active_allocation_percentage: int
    available_capacity_percentage: int
    allocation_status: str
    active_projects_count: int
    next_end_date: date | None = None


class BenchEmployeeOut(BaseModel):
    employee_id: str
    employee_name: str
    department: str | None = None
    designation: str | None = None
    profile_image_url: str | None = None
    total_active_allocation_percentage: int
    available_capacity_percentage: int
    allocation_status: str
    active_project_names: list[str]
    next_available_date: date | None = None
