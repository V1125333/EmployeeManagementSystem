from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.allocation import AllocationOut


Priority = Literal["low", "medium", "high", "urgent"]
StaffingStatus = Literal["open", "in_review", "fulfilled", "partially_fulfilled", "cancelled", "rejected"]


class StaffingRequestCreate(BaseModel):
    project_name: str
    project_id: str | None = None
    hiring_manager_id: str
    department: str | None = None
    role_needed: str
    designation_needed: str | None = None
    skills_required: list[str] | None = None
    allocation_percentage: int = Field(..., ge=1, le=100)
    headcount_needed: int = Field(..., ge=1)
    start_date: date
    end_date: date | None = None
    priority: Priority
    reason: str | None = None
    notes: str | None = None


class StaffingRequestUpdate(BaseModel):
    project_name: str | None = None
    project_id: str | None = None
    hiring_manager_id: str | None = None
    department: str | None = None
    role_needed: str | None = None
    designation_needed: str | None = None
    skills_required: list[str] | None = None
    allocation_percentage: int | None = Field(None, ge=1, le=100)
    headcount_needed: int | None = Field(None, ge=1)
    start_date: date | None = None
    end_date: date | None = None
    priority: Priority | None = None
    reason: str | None = None
    notes: str | None = None


class StaffingRequestStatusUpdate(BaseModel):
    status: StaffingStatus
    rejection_reason: str | None = None


class AllocationOverrides(BaseModel):
    allocation_percentage: int | None = Field(None, ge=1, le=100)
    allocation_role: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    manager_id: str | None = None
    billing_type: Literal["billable", "non_billable", "internal"] | None = None
    notes: str | None = None


class CreateAllocationFromRequestBody(BaseModel):
    employee_id: str
    overrides: AllocationOverrides | None = None


class CandidateOut(BaseModel):
    id: str
    employee_id: str
    allocation_id: str | None = None
    employee_name: str
    department: str | None = None
    designation: str | None = None
    profile_image_url: str | None = None
    match_status: str
    available_capacity_percentage: int
    current_allocation_percentage: int
    next_available_date: date | None = None
    suggested_by: str
    notes: str | None = None
    created_at: datetime


class StaffingRequestOut(BaseModel):
    id: str
    project_name: str
    project_id: str | None = None
    requested_by_name: str
    hiring_manager_id: str
    hiring_manager_name: str
    department: str | None = None
    role_needed: str
    designation_needed: str | None = None
    skills_required: list[str]
    allocation_percentage: int
    headcount_needed: int
    headcount_fulfilled: int
    start_date: date
    end_date: date | None = None
    priority: str
    status: str
    reason: str | None = None
    notes: str | None = None
    rejection_reason: str | None = None
    fulfilled_allocation_ids: list[str]
    fulfilled_at: datetime | None = None
    fulfilled_by: str | None = None
    fulfilled_by_name: str | None = None
    candidates: list[CandidateOut]
    created_at: datetime
    updated_at: datetime | None = None


class StaffingRequestSummary(BaseModel):
    id: str
    project_name: str
    project_id: str | None = None
    role_needed: str
    allocation_percentage: int
    headcount_needed: int
    headcount_fulfilled: int
    start_date: date
    end_date: date | None = None
    priority: str
    status: str
    requested_by_name: str
    hiring_manager_name: str
    created_at: datetime


class StaffingRequestListResponse(BaseModel):
    items: list[StaffingRequestSummary]
    total: int
    page: int
    per_page: int


class StaffingRequestOptions(BaseModel):
    departments: list[str]
    designations: list[str]
    managers: list[dict]
    projects: list[dict]
    employees: list[dict]


class StaffingFulfillmentResult(BaseModel):
    allocation: AllocationOut
    staffing_request: StaffingRequestOut
    candidate: CandidateOut
    overlap_warning: list[dict] | None = None
