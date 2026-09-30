"""
Auth API endpoints — first-time setup + login + forgot password.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.authentication import (
    AuthenticatedActor,
    get_authenticated_actor,
    get_password_change_actor,
)
from app.models.employee import Employee
from app.schemas.employee import (
    CheckEmailRequest,
    VerifySetupCodeRequest, VerifySetupCodeResponse,
    SetPasswordRequest, SetPasswordResponse,
    ConfirmTotpRequest, ConfirmTotpResponse,
    LoginRequest, LoginResponse,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ForgotPasswordInitiateRequest, ForgotPasswordInitiateResponse,
    ForgotPasswordVerifyMfaRequest, ForgotPasswordVerifyMfaResponse,
    ForgotPasswordResetRequest, AdminResetPasswordRequest, AdminResetPasswordResponse,
    ForceChangePasswordRequest, ForceChangePasswordResponse,
    VerifyLoginPasswordRequest, VerifyLoginPasswordResponse, CompleteLoginMfaRequest,
    RequestUnlockRequest, RequestUnlockForColleagueRequest,
    CurrentUserProfileResponse,
)
from app.services.auth_service import (
    verify_setup_code,
    set_password_and_get_qr,
    confirm_totp_setup,
    initiate_reset,
    verify_reset_mfa,
    complete_reset,
    admin_reset_password,
    change_password,
    force_change_password,
    verify_login_password,
    complete_login_mfa,
    create_unlock_request_anonymous,
    create_unlock_request_authenticated,
    find_employee_by_email,
)
from app.services.audit_service import log_audit
from app.services.rate_limit_service import consume_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _employee_by_email(db: Session, email: str):
    return find_employee_by_email(db, email)


def _audit_auth_event(db: Session, action: str, employee, reason: str | None = None, source: str = "api"):
    log_audit(
        db=db,
        actor=employee,
        action=action,
        entity_type="auth",
        entity_id=getattr(employee, "id", None),
        reason=reason,
        source=source,
    )
    db.commit()


def _request_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{email.lower().strip()}"


def _check_public_rate_limit(
    db: Session,
    request: Request,
    *,
    scope: str,
    identifier: str,
    limit: int | None = None,
) -> None:
    # Deliberately use the socket peer. X-Forwarded-For is untrusted unless a
    # separately configured proxy layer has already replaced request.client.
    key = _request_key(request, identifier)
    if not consume_rate_limit(
        db,
        scope=scope,
        key=key,
        limit=limit or settings.PUBLIC_AUTH_ATTEMPTS_PER_HOUR,
    ):
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")


def _retired_auth_route(code: str) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": code,
            "message": "This authentication flow is no longer available. Use the staged authentication flow.",
        },
    )


def _check_reset_rate_limit(db: Session, request: Request, email: str):
    key = _request_key(request, email)
    if not consume_rate_limit(db, scope="password_reset", key=key, limit=settings.RESET_RATE_LIMIT_PER_HOUR):
        raise HTTPException(status_code=429, detail="Too many reset attempts. Please try again later.")


def _check_unlock_rate_limit(db: Session, request: Request, email: str):
    key = _request_key(request, email)
    if not consume_rate_limit(db, scope="unlock_request", key=key, limit=settings.UNLOCK_REQUEST_RATE_LIMIT_PER_HOUR):
        raise HTTPException(status_code=429, detail="Too many unlock requests. Please try again later.")


@router.post("/check-email", status_code=410)
async def api_check_email(data: CheckEmailRequest):
    """Non-enumerating tombstone for the retired account-discovery route."""
    del data
    _retired_auth_route("ACCOUNT_DISCOVERY_RETIRED")


@router.post("/verify-setup-code", response_model=VerifySetupCodeResponse)
async def api_verify_setup_code(data: VerifySetupCodeRequest, request: Request, db: Session = Depends(get_db)):
    """Step 2 (first-time): Verify the setup code given by admin."""
    _check_public_rate_limit(db, request, scope="setup_code_verify", identifier=data.email)
    success = verify_setup_code(db, data.email, data.setup_code)
    employee = _employee_by_email(db, data.email)
    _audit_auth_event(
        db,
        "setup_code_verified" if success else "setup_code_verification_failed",
        employee,
        None if success else "Invalid setup code",
    )
    return VerifySetupCodeResponse(
        success=success,
        message="Setup code verified" if success else "Invalid setup code",
    )


@router.post("/set-password", response_model=SetPasswordResponse)
async def api_set_password(data: SetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Step 3 (first-time): Set password and get TOTP QR code."""
    _check_public_rate_limit(db, request, scope="initial_password_setup", identifier=data.email)
    result = set_password_and_get_qr(db, data.email, data.setup_code, data.password)
    employee = _employee_by_email(db, data.email)
    _audit_auth_event(
        db,
        "user_password_changed" if result.get("success") else "user_password_change_failed",
        employee,
        None if result.get("success") else result.get("message", "Password setup failed"),
    )
    return result


@router.post("/confirm-totp", response_model=ConfirmTotpResponse)
async def api_confirm_totp(data: ConfirmTotpRequest, request: Request, db: Session = Depends(get_db)):
    """Step 4 (first-time): Confirm TOTP is set up correctly. Completes first-time setup."""
    _check_public_rate_limit(
        db, request, scope="totp_setup_confirm", identifier=data.email,
        limit=settings.PUBLIC_AUTH_CHALLENGE_ATTEMPTS_PER_HOUR,
    )
    success = confirm_totp_setup(db, data.email, data.totp_code)
    employee = _employee_by_email(db, data.email)
    _audit_auth_event(
        db,
        "totp_setup_confirmed" if success else "totp_setup_failed",
        employee,
        None if success else "Invalid authenticator code",
    )
    return ConfirmTotpResponse(
        success=success,
        message="Authenticator setup complete! You can now log in." if success else "Invalid code. Please try again.",
    )


@router.post("/login", status_code=410)
async def api_login(data: LoginRequest):
    """Stable tombstone for the retired combined password/MFA flow."""
    del data
    _retired_auth_route("LEGACY_LOGIN_RETIRED")


@router.post("/login/verify-password", response_model=VerifyLoginPasswordResponse)
async def api_verify_login_password(
    data: VerifyLoginPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Step 1 login: validate password before showing MFA."""
    _check_public_rate_limit(db, request, scope="login_password", identifier=data.email)
    ip_address = request.client.host if request.client else None
    return verify_login_password(db, data.email, data.password, ip_address=ip_address)


@router.post("/login/verify-mfa", response_model=LoginResponse)
async def api_complete_login_mfa(
    data: CompleteLoginMfaRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Step 2 login: validate MFA for a short-lived login challenge."""
    _check_public_rate_limit(
        db, request, scope="login_mfa", identifier=data.login_challenge_token,
        limit=settings.PUBLIC_AUTH_CHALLENGE_ATTEMPTS_PER_HOUR,
    )
    return complete_login_mfa(db, data.login_challenge_token, data.totp_code)


@router.post("/forgot-password", status_code=410)
async def api_forgot_password(data: ForgotPasswordRequest):
    """Stable tombstone for the retired direct-reset flow."""
    del data
    _retired_auth_route("LEGACY_PASSWORD_RESET_RETIRED")


@router.post("/forgot-password/initiate", response_model=ForgotPasswordInitiateResponse)
async def api_forgot_password_initiate(
    data: ForgotPasswordInitiateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Queue reset instructions while returning a non-enumerating response."""
    _check_reset_rate_limit(db, request, data.email)
    return initiate_reset(db, data.email)


@router.post("/forgot-password/verify-mfa", response_model=ForgotPasswordVerifyMfaResponse)
async def api_forgot_password_verify_mfa(
    data: ForgotPasswordVerifyMfaRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Verify authenticator code for a reset session."""
    _check_public_rate_limit(
        db, request, scope="password_reset_mfa", identifier=data.reset_token,
        limit=settings.PUBLIC_AUTH_CHALLENGE_ATTEMPTS_PER_HOUR,
    )
    return verify_reset_mfa(db, data.reset_token, data.totp_code)


@router.post("/forgot-password/reset", response_model=ForgotPasswordResponse)
async def api_forgot_password_reset(
    data: ForgotPasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Complete staged password reset."""
    _check_public_rate_limit(
        db, request, scope="password_reset_complete", identifier=data.reset_token,
        limit=settings.PUBLIC_AUTH_CHALLENGE_ATTEMPTS_PER_HOUR,
    )
    return complete_reset(db, data.reset_token, data.new_password, data.confirm_password)


@router.post("/admin-reset-password", response_model=AdminResetPasswordResponse)
async def api_admin_reset_password(
    data: AdminResetPasswordRequest,
    request: Request,
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
    db: Session = Depends(get_db),
):
    """Allow Super Admin/HR/Admin to issue a temporary password."""
    return admin_reset_password(
        db, actor.employee, data.employee_id, data.reason, request=request
    )


@router.post("/force-change-password", response_model=ForceChangePasswordResponse)
async def api_force_change_password(
    data: ForceChangePasswordRequest,
    request: Request,
    actor: AuthenticatedActor = Depends(get_password_change_actor),
    db: Session = Depends(get_db),
):
    """Required password change after admin reset."""
    return force_change_password(
        db,
        actor.employee,
        data.current_password,
        data.new_password,
        data.confirm_password,
        request=request,
    )


@router.post("/change-password", response_model=ForceChangePasswordResponse)
async def api_change_password(
    data: ForceChangePasswordRequest,
    request: Request,
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
    db: Session = Depends(get_db),
):
    """Authenticated self-service password change."""
    return change_password(
        db,
        actor.employee,
        data.current_password or "",
        data.new_password,
        data.confirm_password,
        request=request,
    )


@router.post("/request-unlock")
async def api_request_unlock(
    data: RequestUnlockRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Request account unlock from the login screen. Always returns a generic response."""
    _check_unlock_rate_limit(db, request, data.email)
    return create_unlock_request_anonymous(db, data.email, data.reason)


@router.post("/request-unlock-for-colleague")
async def api_request_unlock_for_colleague(
    data: RequestUnlockForColleagueRequest,
    request: Request,
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
    db: Session = Depends(get_db),
):
    """Authenticated request to unlock a colleague's locked account."""
    return create_unlock_request_authenticated(
        db, actor.employee, data.employee_id, data.reason, request=request
    )


def _safe_current_profile(employee: Employee, principal=None) -> dict:
    profile = {
        "id": employee.id,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "work_email": employee.work_email,
        "personal_email": employee.personal_email,
        "phone": employee.phone,
        "country_code": employee.country_code,
        "date_of_birth": str(employee.date_of_birth) if employee.date_of_birth else None,
        "gender": employee.gender,
        "department": employee.department,
        "designation": employee.designation,
        "role": principal.role if principal else employee.role,
        "workforce_type": employee.workforce_type,
        "employment_type": employee.employment_type or employee.workforce_type,
        "employment_status": employee.employment_status,
        "work_location": employee.work_location,
        "work_city": employee.work_city,
        "work_state": employee.work_state,
        "work_country": employee.work_country,
        "joining_date": str(employee.joining_date) if employee.joining_date else None,
        "reporting_manager": employee.reporting_manager,
        "manager_id": employee.manager_id,
        "profile_image_url": employee.profile_image_url,
        "emergency_contact_name": employee.emergency_contact_name,
        "emergency_contact_phone": employee.emergency_contact_phone,
        "emergency_contact_relation": employee.emergency_contact_relation,
        "current_address": employee.current_address,
        "is_active": employee.is_active,
        "account_locked": employee.account_locked,
        "access_level": employee.access_level,
        "mfa_enabled": employee.mfa_enabled,
        "force_password_change": employee.force_password_change,
        "last_login_at": str(employee.last_login_at) if employee.last_login_at else None,
        "last_active_at": str(employee.last_active_at) if employee.last_active_at else None,
        "created_at": str(employee.created_at),
        "last_updated_at": str(employee.last_updated_at) if employee.last_updated_at else None,
    }
    if principal:
        profile["permissions"] = sorted(principal.permissions)
        profile["scopes"] = {key: sorted(values) for key, values in principal.scopes.items()}
    return profile


@router.get("/me", response_model=CurrentUserProfileResponse)
async def get_my_profile(
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    """Return the current database profile for the JWT subject only."""
    return {"success": True, "employee": _safe_current_profile(actor.employee, actor.principal)}


@router.get("/me/{email}", status_code=410)
async def retired_profile_lookup(email: str):
    """Return a non-disclosing tombstone for the retired email lookup."""
    del email
    raise HTTPException(
        status_code=410,
        detail={
            "code": "PROFILE_LOOKUP_RETIRED",
            "message": "This profile lookup is no longer available.",
        },
    )
