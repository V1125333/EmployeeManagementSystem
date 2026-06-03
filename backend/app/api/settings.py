"""
User settings API endpoints.
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.settings import (
    AppearanceSettingsUpdate,
    GeneralSettingsUpdate,
    NotificationSettingsUpdate,
    PrivacySettingsUpdate,
    SecuritySettingsUpdate,
    UserSettingsResponse,
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

router = APIRouter(prefix="/settings", tags=["Settings"])


def current_employee_from_headers(
    db: Session,
    x_user_id: str | None,
    x_user_email: str | None,
):
    return get_current_employee(db, x_user_id, x_user_email)


@router.get("/me", response_model=UserSettingsResponse)
async def get_my_settings(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    settings = get_or_create_user_settings(db, employee)
    return serialize_settings(settings)


@router.patch("/me/general", response_model=UserSettingsResponse)
async def patch_general_settings(
    payload: GeneralSettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_settings(update_general_settings(db, employee, payload))


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
    return serialize_settings(update_notification_settings(db, employee, payload))


@router.patch("/me/appearance", response_model=UserSettingsResponse)
async def patch_appearance_settings(
    payload: AppearanceSettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_settings(update_appearance_settings(db, employee, payload))


@router.patch("/me/privacy", response_model=UserSettingsResponse)
async def patch_privacy_settings(
    payload: PrivacySettingsUpdate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = current_employee_from_headers(db, x_user_id, x_user_email)
    return serialize_settings(update_privacy_settings(db, employee, payload))
