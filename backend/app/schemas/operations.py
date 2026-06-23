from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


ProjectStatus = Literal["planning", "active", "on_hold", "completed", "cancelled"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=20)
    description: str | None = None
    client_name: str | None = Field(None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus = "planning"


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    code: str | None = Field(None, min_length=2, max_length=20)
    description: str | None = None
    client_name: str | None = Field(None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus | None = None


class ProjectManagerSchema(BaseModel):
    manager_employee_id: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    client_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str
    project_manager_id: str | None = None
    project_manager_name: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    allocation_count: int = 0
    active_allocation_count: int = 0
    active_employee_count: int = 0

    model_config = {"from_attributes": True}
