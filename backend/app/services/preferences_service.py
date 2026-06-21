from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.employee import Employee
from app.models.user_preferences import UserPreferences
from app.schemas.user_preferences import AppearanceUpdate, GeneralUpdate, NotificationsUpdate
from app.services.audit_service import log_audit


ALLOWED_ACCENT_COLORS = ["olive", "blue", "indigo", "purple", "emerald", "rose", "slate"]
ALLOWED_THEME_MODES = ["light", "dark", "system"]
ALLOWED_DATE_FORMATS = ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]
ALLOWED_LANGUAGES = ["en-US", "en-GB"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def preference_values(row: UserPreferences) -> dict[str, Any]:
    return {
        "theme_mode": row.theme_mode,
        "accent_color": row.accent_color,
        "sidebar_collapsed": row.sidebar_collapsed,
        "compact_mode": row.compact_mode,
        "timezone": row.timezone,
        "date_format": row.date_format,
        "default_landing_page": row.default_landing_page,
        "language": row.language,
        "email_notif_leave_approved": row.email_notif_leave_approved,
        "email_notif_leave_rejected": row.email_notif_leave_rejected,
        "email_notif_timesheet_approved": row.email_notif_timesheet_approved,
        "email_notif_timesheet_rejected": row.email_notif_timesheet_rejected,
        "email_notif_allocation_changes": row.email_notif_allocation_changes,
        "inapp_notifications_enabled": row.inapp_notifications_enabled,
    }


def serialize_preferences(row: UserPreferences) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        **preference_values(row),
        "updated_at": row.updated_at,
    }


def get_or_create_preferences(db: Session, user_id: str) -> UserPreferences:
    row = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if row:
        return row
    row = UserPreferences(user_id=user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_preferences(db: Session, user_id: str) -> UserPreferences:
    row = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Preferences not found.")
    return row


def _patch(row: UserPreferences, payload: dict[str, Any]) -> None:
    for field, value in payload.items():
        if value is not None:
            setattr(row, field, value)
    row.updated_at = _now()


def _actor(db: Session, actor_id: str) -> Employee | None:
    return db.query(Employee).filter(Employee.id == actor_id).first()


def _log_preference_change(
    db: Session,
    user_id: str,
    action: str,
    old_values: dict[str, Any],
    new_values: dict[str, Any],
    actor_id: str,
) -> None:
    log_audit(
        db,
        _actor(db, actor_id),
        action,
        "user_preferences",
        user_id,
        old_values=old_values,
        new_values=new_values,
        metadata={"employee_id": user_id, "old": old_values, "new": new_values},
    )


def update_appearance(db: Session, user_id: str, data: AppearanceUpdate, actor_id: str) -> UserPreferences:
    row = get_or_create_preferences(db, user_id)
    payload = data.model_dump(exclude_unset=True)
    if "theme_mode" in payload and payload["theme_mode"] not in ALLOWED_THEME_MODES:
        raise HTTPException(status_code=422, detail="Theme mode must be light, dark, or system.")
    if "accent_color" in payload and payload["accent_color"] not in ALLOWED_ACCENT_COLORS:
        raise HTTPException(status_code=422, detail="Unsupported accent color.")

    old_values = preference_values(row)
    _patch(row, payload)
    new_values = preference_values(row)

    if old_values.get("theme_mode") != new_values.get("theme_mode"):
        _log_preference_change(db, user_id, "user_theme_changed", {"theme_mode": old_values["theme_mode"]}, {"theme_mode": new_values["theme_mode"]}, actor_id)
    if old_values.get("accent_color") != new_values.get("accent_color"):
        _log_preference_change(db, user_id, "user_accent_color_changed", {"accent_color": old_values["accent_color"]}, {"accent_color": new_values["accent_color"]}, actor_id)
    if (
        old_values.get("sidebar_collapsed") != new_values.get("sidebar_collapsed")
        or old_values.get("compact_mode") != new_values.get("compact_mode")
    ):
        _log_preference_change(
            db,
            user_id,
            "user_sidebar_preference_changed",
            {"sidebar_collapsed": old_values["sidebar_collapsed"], "compact_mode": old_values["compact_mode"]},
            {"sidebar_collapsed": new_values["sidebar_collapsed"], "compact_mode": new_values["compact_mode"]},
            actor_id,
        )
    db.commit()
    db.refresh(row)
    return row


def update_general(db: Session, user_id: str, data: GeneralUpdate, actor_id: str) -> UserPreferences:
    row = get_or_create_preferences(db, user_id)
    payload = data.model_dump(exclude_unset=True)
    if "date_format" in payload and payload["date_format"] not in ALLOWED_DATE_FORMATS:
        raise HTTPException(status_code=422, detail="Unsupported date format.")
    if "language" in payload and payload["language"] not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported language.")

    old_values = preference_values(row)
    _patch(row, payload)
    new_values = preference_values(row)
    _log_preference_change(db, user_id, "user_general_settings_updated", old_values, new_values, actor_id)
    db.commit()
    db.refresh(row)
    return row


def update_notifications(db: Session, user_id: str, data: NotificationsUpdate, actor_id: str) -> UserPreferences:
    row = get_or_create_preferences(db, user_id)
    old_values = preference_values(row)
    _patch(row, data.model_dump(exclude_unset=True))
    new_values = preference_values(row)
    _log_preference_change(db, user_id, "user_notification_settings_updated", old_values, new_values, actor_id)
    db.commit()
    db.refresh(row)
    return row


def activity_history(db: Session, user_id: str) -> list[dict[str, Any]]:
    rows = db.query(AuditLog).filter(
        AuditLog.entity_id == user_id,
        AuditLog.action.like("user_%"),
    ).order_by(AuditLog.created_at.desc()).limit(50).all()
    return [
        {
            "id": row.id,
            "action": row.action,
            "old_values": row.old_values,
            "new_values": row.new_values,
            "details": row.metadata_json,
            "performed_by": row.actor_name,
            "performed_at": row.created_at,
        }
        for row in rows
    ]
