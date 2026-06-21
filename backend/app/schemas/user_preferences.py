from datetime import datetime

from pydantic import BaseModel


class UserPreferencesOut(BaseModel):
    user_id: str
    theme_mode: str
    accent_color: str
    sidebar_collapsed: bool
    compact_mode: bool
    timezone: str
    date_format: str
    default_landing_page: str
    language: str
    email_notif_leave_approved: bool
    email_notif_leave_rejected: bool
    email_notif_timesheet_approved: bool
    email_notif_timesheet_rejected: bool
    email_notif_allocation_changes: bool
    inapp_notifications_enabled: bool
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AppearanceUpdate(BaseModel):
    theme_mode: str | None = None
    accent_color: str | None = None
    sidebar_collapsed: bool | None = None
    compact_mode: bool | None = None


class GeneralUpdate(BaseModel):
    timezone: str | None = None
    date_format: str | None = None
    default_landing_page: str | None = None
    language: str | None = None


class NotificationsUpdate(BaseModel):
    email_notif_leave_approved: bool | None = None
    email_notif_leave_rejected: bool | None = None
    email_notif_timesheet_approved: bool | None = None
    email_notif_timesheet_rejected: bool | None = None
    email_notif_allocation_changes: bool | None = None
    inapp_notifications_enabled: bool | None = None


class SettingsProfileOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    display_name: str
    work_email: str
    phone: str | None = None
    country_code: str | None = None
    profile_image_url: str | None = None
    timezone: str
    date_format: str
    last_login_at: datetime | None = None
