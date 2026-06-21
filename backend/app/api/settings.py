"""
User settings API endpoints.
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.settings import (
    AppearanceSettingsUpdate,
    GeneralSettingsUpdate,
    NotificationSettingsUpdate,
    PrivacySettingsUpdate,
    SecuritySettingsUpdate,
    UserSettingsResponse,
)
from app.schemas.user_preferences import (
    AppearanceUpdate,
    GeneralUpdate,
    NotificationsUpdate,
    SettingsProfileOut,
    UserPreferencesOut,
)
from app.services.settings_service import (
    get_current_employee,
    get_or_create_user_settings,
    serialize_settings,
    update_appearance_settings,
    update_general_settings,
    update_notification_settings,
    update_privacy_settings,
    update_security_settings,
)
from app.services.preferences_service import (
    activity_history,
    get_or_create_preferences,
    serialize_preferences,
    update_appearance,
    update_general,
    update_notifications,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


def current_employee_from_headers(
    db: Session,
    x_user_id: str | None,
    x_user_email: str | None,
):
    return get_current_employee(db, x_user_id, x_user_email)


def legacy_settings_response(db: Session, employee: Employee) -> dict:
    legacy = get_or_create_user_settings(db, employee)
    preferences = get_or_create_preferences(db, employee.id)
    base = serialize_settings(legacy)
    base.update({
        "time_zone": preferences.timezone,
        "date_format": preferences.date_format,
        "default_landing_page": preferences.default_landing_page,
        "theme": preferences.theme_mode,
        "sidebar_mode": "collapsed" if preferences.sidebar_collapsed else "expanded",
        "dashboard_density": "compact" if preferences.compact_mode else "comfortable",
        "notification_leave_updates": preferences.email_notif_leave_approved or preferences.email_notif_leave_rejected,
        "notification_project_allocation_updates": preferences.email_notif_allocation_changes,
    })
    return base


def profile_response(employee: Employee, preferences) -> dict:
    display_name = " ".join(part for part in [employee.first_name, employee.last_name] if part).strip()
    return {
        "id": employee.id,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "display_name": display_name,
        "work_email": employee.work_email,
        "phone": employee.phone,
        "country_code": employee.country_code,
        "profile_image_url": employee.profile_image_url,
        "timezone": preferences.timezone,
        "date_format": preferences.date_format,
        "last_login_at": employee.last_login_at,
    }


@router.get("/me", response_model=UserSettingsResponse)
async def get_my_settings(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return legacy_settings_response(db, employee)


@router.get("/preferences", response_model=UserPreferencesOut)
async def get_my_preferences(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_preferences(get_or_create_preferences(db, employee.id))


@router.patch("/preferences/appearance", response_model=UserPreferencesOut)
async def patch_preference_appearance(
    payload: AppearanceUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_preferences(update_appearance(db, employee.id, payload, employee.id))


@router.patch("/preferences/general", response_model=UserPreferencesOut)
async def patch_preference_general(
    payload: GeneralUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_preferences(update_general(db, employee.id, payload, employee.id))


@router.patch("/preferences/notifications", response_model=UserPreferencesOut)
async def patch_preference_notifications(
    payload: NotificationsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_preferences(update_notifications(db, employee.id, payload, employee.id))


@router.get("/activity")
async def get_my_settings_activity(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return activity_history(db, employee.id)


@router.get("/profile", response_model=SettingsProfileOut)
async def get_settings_profile(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    preferences = get_or_create_preferences(db, employee.id)
    return profile_response(employee, preferences)


@router.patch("/me/general", response_model=UserSettingsResponse)
async def patch_general_settings(
    payload: GeneralSettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    update_general_settings(db, employee, payload)
    update_general(
        db,
        employee.id,
        GeneralUpdate(
            timezone=payload.time_zone,
            date_format=payload.date_format,
            default_landing_page=payload.default_landing_page,
        ),
        employee.id,
    )
    return legacy_settings_response(db, employee)


@router.patch("/me/security", response_model=UserSettingsResponse)
async def patch_security_settings(
    payload: SecuritySettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_settings(update_security_settings(db, employee, payload))


@router.patch("/me/notifications", response_model=UserSettingsResponse)
async def patch_notification_settings(
    payload: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    update_notification_settings(db, employee, payload)
    update_notifications(
        db,
        employee.id,
        NotificationsUpdate(
            email_notif_leave_approved=payload.notification_leave_updates,
            email_notif_leave_rejected=payload.notification_leave_updates,
            email_notif_allocation_changes=payload.notification_project_allocation_updates,
        ),
        employee.id,
    )
    return legacy_settings_response(db, employee)


@router.patch("/me/appearance", response_model=UserSettingsResponse)
async def patch_appearance_settings(
    payload: AppearanceSettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    update_appearance_settings(db, employee, payload)
    update_appearance(
        db,
        employee.id,
        AppearanceUpdate(
            theme_mode=payload.theme,
            sidebar_collapsed=payload.sidebar_mode == "collapsed",
            compact_mode=payload.dashboard_density == "compact",
        ),
        employee.id,
    )
    return legacy_settings_response(db, employee)


@router.patch("/me/privacy", response_model=UserSettingsResponse)
async def patch_privacy_settings(
    payload: PrivacySettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_settings(update_privacy_settings(db, employee, payload))
