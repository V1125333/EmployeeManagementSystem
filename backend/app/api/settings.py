"""
User settings API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.authentication import AuthenticatedActor, get_authenticated_actor
from app.models.employee import Employee
from app.schemas.settings import (
    AppearanceSettingsUpdate,
    GeneralSettingsUpdate,
    NotificationSettingsUpdate,
    OrganizationSecurityPolicyResponse,
    OrganizationSecurityPolicyUpdate,
    PrivacySettingsUpdate,
    SecuritySettingsUpdate,
    UserSettingsResponse,
)
from app.services.audit_service import log_audit
from app.services.mfa_policy_service import (
    get_security_policy,
    get_or_create_security_policy,
    is_mfa_required,
    policy_values,
    update_organization_security_policy,
)
from app.schemas.user_preferences import (
    AppearanceUpdate,
    GeneralUpdate,
    NotificationsUpdate,
    SettingsProfileOut,
    UserPreferencesOut,
)
from app.services.settings_service import (
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
from app.core.authorization import employee_can
from app.core.rbac import Permission, Scope

router = APIRouter(prefix="/settings", tags=["Settings"])


def legacy_settings_response(db: Session, employee: Employee) -> dict:
    legacy = get_or_create_user_settings(db, employee)
    preferences = get_or_create_preferences(db, employee.id)
    base = serialize_settings(legacy)
    globally_enabled, opt_out_allowed = policy_values(db)
    base.update({
        "time_zone": preferences.timezone,
        "date_format": preferences.date_format,
        "default_landing_page": preferences.default_landing_page,
        "theme": preferences.theme_mode,
        "sidebar_mode": "collapsed" if preferences.sidebar_collapsed else "expanded",
        "dashboard_density": "compact" if preferences.compact_mode else "comfortable",
        "notification_leave_updates": preferences.email_notif_leave_approved or preferences.email_notif_leave_rejected,
        "notification_project_allocation_updates": preferences.email_notif_allocation_changes,
        "mfa_globally_enabled": globally_enabled,
        "mfa_user_opt_out_allowed": opt_out_allowed,
        "mfa_effective": is_mfa_required(db, employee),
        "mfa_configured": bool(employee.totp_secret),
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
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return legacy_settings_response(db, employee)


@router.get("/preferences", response_model=UserPreferencesOut)
async def get_my_preferences(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return serialize_preferences(get_or_create_preferences(db, employee.id))


@router.patch("/preferences/appearance", response_model=UserPreferencesOut)
async def patch_preference_appearance(
    payload: AppearanceUpdate,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return serialize_preferences(update_appearance(db, employee.id, payload, employee.id))


@router.patch("/preferences/general", response_model=UserPreferencesOut)
async def patch_preference_general(
    payload: GeneralUpdate,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return serialize_preferences(update_general(db, employee.id, payload, employee.id))


@router.patch("/preferences/notifications", response_model=UserPreferencesOut)
async def patch_preference_notifications(
    payload: NotificationsUpdate,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return serialize_preferences(update_notifications(db, employee.id, payload, employee.id))


@router.get("/activity")
async def get_my_settings_activity(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return activity_history(db, employee.id)


@router.get("/profile", response_model=SettingsProfileOut)
async def get_settings_profile(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    preferences = get_or_create_preferences(db, employee.id)
    return profile_response(employee, preferences)


@router.patch("/me/general", response_model=UserSettingsResponse)
async def patch_general_settings(
    payload: GeneralSettingsUpdate,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
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
    request: Request,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    before = legacy_settings_response(db, employee)
    update_security_settings(db, employee, payload)
    after = legacy_settings_response(db, employee)
    log_audit(
        db, employee, "mfa.preference.updated", "user_settings", employee.id,
        old_values={"mfa_enabled": before["mfa_enabled"]},
        new_values={"mfa_enabled": after["mfa_enabled"]},
        reason="User updated their MFA preference.", request=request,
    )
    db.commit()
    return after


@router.get("/security-policy", response_model=OrganizationSecurityPolicyResponse)
async def get_organization_security_policy(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    policy = get_security_policy(db)
    if not policy:
        return {
            "mfa_enabled": True,
            "allow_user_mfa_opt_out": True,
            "updated_at": None,
            "updated_by": None,
        }
    return policy


@router.patch("/security-policy", response_model=OrganizationSecurityPolicyResponse)
async def patch_organization_security_policy(
    payload: OrganizationSecurityPolicyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    if not employee_can(employee, Permission.SECURITY_POLICY_MANAGE, Scope.ORGANIZATION):
        raise HTTPException(status_code=403, detail="security.policy.manage permission is required.")
    policy = get_or_create_security_policy(db, employee.id)
    before = {
        "mfa_enabled": bool(policy.mfa_enabled),
        "allow_user_mfa_opt_out": bool(policy.allow_user_mfa_opt_out),
    }
    policy = update_organization_security_policy(
        db,
        employee,
        mfa_enabled=payload.mfa_enabled,
        allow_user_mfa_opt_out=payload.allow_user_mfa_opt_out,
    )
    after = {
        "mfa_enabled": bool(policy.mfa_enabled),
        "allow_user_mfa_opt_out": bool(policy.allow_user_mfa_opt_out),
    }
    log_audit(
        db, employee, "mfa.organization_policy.updated", "organization_security_policy", policy.id,
        old_values=before, new_values=after,
        reason="Administrator updated the organization MFA policy.", request=request,
    )
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/me/notifications", response_model=UserSettingsResponse)
async def patch_notification_settings(
    payload: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
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
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
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
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    employee = actor.employee
    return serialize_settings(update_privacy_settings(db, employee, payload))
