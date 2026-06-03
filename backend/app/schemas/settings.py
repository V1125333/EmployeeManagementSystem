"""
Schemas for user settings and support tickets.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


DateFormat = Literal["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"]
Theme = Literal["light", "dark", "system"]
SidebarMode = Literal["expanded", "collapsed"]
DashboardDensity = Literal["comfortable", "compact"]
PrivacyValue = Literal["Everyone", "Managers Only", "HR Only", "Private"]


class UserSettingsResponse(BaseModel):
    id: str
    user_id: str
    time_zone: str
    date_format: str
    default_landing_page: str
    theme: str
    sidebar_mode: str
    dashboard_density: str
    mfa_enabled: bool
    notification_company_announcements: bool
    notification_leave_updates: bool
    notification_attendance_reminders: bool
    notification_task_assignments: bool
    notification_training_notifications: bool
    notification_project_allocation_updates: bool
    profile_visibility: str
    phone_visibility: str
    birthday_visibility: str
    created_at: datetime | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None

    model_config = {"from_attributes": True}


class GeneralSettingsUpdate(BaseModel):
    time_zone: Literal["America/New_York", "America/Chicago", "America/Los_Angeles", "Asia/Kolkata"]
    date_format: DateFormat
    default_landing_page: Literal["Dashboard", "Employees", "Team Allocation", "Time Off & Attendance", "Assets & Access"]


class SecuritySettingsUpdate(BaseModel):
    mfa_enabled: bool


class NotificationSettingsUpdate(BaseModel):
    notification_company_announcements: bool
    notification_leave_updates: bool
    notification_attendance_reminders: bool
    notification_task_assignments: bool
    notification_training_notifications: bool
    notification_project_allocation_updates: bool


class AppearanceSettingsUpdate(BaseModel):
    theme: Theme
    sidebar_mode: SidebarMode
    dashboard_density: DashboardDensity


class PrivacySettingsUpdate(BaseModel):
    profile_visibility: PrivacyValue
    phone_visibility: PrivacyValue
    birthday_visibility: PrivacyValue


class SupportTicketCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)


class SupportTicketResponse(BaseModel):
    id: str
    user_id: str
    category: str
    subject: str
    description: str
    status: str
    created_at: datetime | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None

    model_config = {"from_attributes": True}
