"""
Service layer for user settings and support tickets.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.settings import SupportTicket, UserSettings
from app.schemas.settings import (
    AppearanceSettingsUpdate,
    GeneralSettingsUpdate,
    NotificationSettingsUpdate,
    PrivacySettingsUpdate,
    SecuritySettingsUpdate,
    SupportTicketCreate,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_current_employee(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    employee = None
    if user_id:
        employee = db.query(Employee).filter(Employee.id == user_id).first()
    if employee and user_email and employee.work_email.lower() != user_email.lower():
        raise HTTPException(status_code=401, detail="Authenticated user headers do not match.")
    if not employee and user_email:
        employee = db.query(Employee).filter(Employee.work_email == user_email).first()
    if not employee:
        raise HTTPException(status_code=401, detail="Authenticated user not found.")
    return employee


def normalize_role(role: str | None) -> str:
    return (role or "").strip().lower().replace(" ", "_").replace("-", "_")


def is_admin_role(role: str | None) -> bool:
    return normalize_role(role) in {"super_admin", "admin", "hr_admin", "global_access"}


def is_manager_or_admin_role(role: str | None) -> bool:
    return normalize_role(role) in {"manager", "super_admin", "admin", "hr_admin", "global_access"}


def require_admin_employee(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    employee = get_current_employee(db, user_id, user_email)
    if not is_admin_role(employee.role):
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return employee


def serialize_settings(settings: UserSettings) -> dict:
    return {
        "id": settings.id,
        "user_id": settings.user_id,
        "time_zone": settings.time_zone,
        "date_format": settings.date_format,
        "default_landing_page": settings.default_landing_page,
        "theme": settings.theme,
        "sidebar_mode": settings.sidebar_mode,
        "dashboard_density": settings.dashboard_density,
        "mfa_enabled": settings.mfa_enabled,
        "notification_company_announcements": settings.notification_company_announcements,
        "notification_leave_updates": settings.notification_leave_updates,
        "notification_attendance_reminders": settings.notification_attendance_reminders,
        "notification_task_assignments": settings.notification_task_assignments,
        "notification_training_notifications": settings.notification_training_notifications,
        "notification_project_allocation_updates": settings.notification_project_allocation_updates,
        "profile_visibility": settings.profile_visibility,
        "phone_visibility": settings.phone_visibility,
        "birthday_visibility": settings.birthday_visibility,
        "created_at": settings.created_at,
        "created_by": settings.created_by,
        "updated_at": settings.updated_at,
        "updated_by": settings.updated_by,
    }


def get_or_create_user_settings(db: Session, employee: Employee) -> UserSettings:
    settings = db.query(UserSettings).filter(UserSettings.user_id == employee.id).first()
    if settings:
        return settings

    now = utc_now()
    settings = UserSettings(
        user_id=employee.id,
        created_at=now,
        created_by=employee.id,
        updated_at=now,
        updated_by=employee.id,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def mark_updated(settings: UserSettings, employee: Employee) -> None:
    settings.updated_at = utc_now()
    settings.updated_by = employee.id


def update_general_settings(db: Session, employee: Employee, payload: GeneralSettingsUpdate) -> UserSettings:
    settings = get_or_create_user_settings(db, employee)
    settings.time_zone = payload.time_zone
    settings.date_format = payload.date_format
    settings.default_landing_page = payload.default_landing_page
    mark_updated(settings, employee)
    db.commit()
    db.refresh(settings)
    return settings


def update_security_settings(db: Session, employee: Employee, payload: SecuritySettingsUpdate) -> UserSettings:
    settings = get_or_create_user_settings(db, employee)
    settings.mfa_enabled = payload.mfa_enabled
    mark_updated(settings, employee)
    db.commit()
    db.refresh(settings)
    return settings


def update_notification_settings(db: Session, employee: Employee, payload: NotificationSettingsUpdate) -> UserSettings:
    settings = get_or_create_user_settings(db, employee)
    for field, value in payload.model_dump().items():
        setattr(settings, field, value)
    mark_updated(settings, employee)
    db.commit()
    db.refresh(settings)
    return settings


def update_appearance_settings(db: Session, employee: Employee, payload: AppearanceSettingsUpdate) -> UserSettings:
    settings = get_or_create_user_settings(db, employee)
    settings.theme = payload.theme
    settings.sidebar_mode = payload.sidebar_mode
    settings.dashboard_density = payload.dashboard_density
    mark_updated(settings, employee)
    db.commit()
    db.refresh(settings)
    return settings


def update_privacy_settings(db: Session, employee: Employee, payload: PrivacySettingsUpdate) -> UserSettings:
    settings = get_or_create_user_settings(db, employee)
    settings.profile_visibility = payload.profile_visibility
    settings.phone_visibility = payload.phone_visibility
    settings.birthday_visibility = payload.birthday_visibility
    mark_updated(settings, employee)
    db.commit()
    db.refresh(settings)
    return settings


def create_support_ticket(db: Session, employee: Employee, payload: SupportTicketCreate) -> SupportTicket:
    now = utc_now()
    ticket = SupportTicket(
        user_id=employee.id,
        category=payload.category.strip(),
        subject=payload.subject.strip(),
        description=payload.description.strip(),
        status="Open",
        created_at=now,
        created_by=employee.id,
        updated_at=now,
        updated_by=employee.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket
