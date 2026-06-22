"""
Auth API endpoints — first-time setup + login + forgot password.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.employee import (
    CheckEmailRequest, CheckEmailResponse,
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
)
from app.services.auth_service import (
    check_email,
    verify_setup_code,
    set_password_and_get_qr,
    confirm_totp_setup,
    login,
    reset_password,
    initiate_reset,
    verify_reset_mfa,
    complete_reset,
    admin_reset_password,
    force_change_password,
    verify_login_password,
    complete_login_mfa,
    create_unlock_request_anonymous,
    create_unlock_request_authenticated,
    find_employee_by_email,
)
from app.services.audit_service import log_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
RESET_INITIATE_RATE_LIMIT: dict[str, list[datetime]] = defaultdict(list)
UNLOCK_REQUEST_RATE_LIMIT: dict[str, list[datetime]] = defaultdict(list)


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


def _check_reset_rate_limit(request: Request, email: str):
    key = _request_key(request, email)
    cutoff = datetime.utcnow() - timedelta(hours=1)
    RESET_INITIATE_RATE_LIMIT[key] = [ts for ts in RESET_INITIATE_RATE_LIMIT[key] if ts > cutoff]
    if len(RESET_INITIATE_RATE_LIMIT[key]) >= settings.RESET_RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many reset attempts. Please try again later.")
    RESET_INITIATE_RATE_LIMIT[key].append(datetime.utcnow())


def _check_unlock_rate_limit(request: Request, email: str):
    key = _request_key(request, email)
    cutoff = datetime.utcnow() - timedelta(hours=1)
    UNLOCK_REQUEST_RATE_LIMIT[key] = [ts for ts in UNLOCK_REQUEST_RATE_LIMIT[key] if ts > cutoff]
    if len(UNLOCK_REQUEST_RATE_LIMIT[key]) >= settings.UNLOCK_REQUEST_RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many unlock requests. Please try again later.")
    UNLOCK_REQUEST_RATE_LIMIT[key].append(datetime.utcnow())


def _actor_from_headers(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
) -> Employee:
    actor = None
    if x_user_id:
        actor = db.query(Employee).filter(Employee.id == x_user_id).first()
    if not actor and x_user_email:
        actor = find_employee_by_email(db, x_user_email)
    if not actor:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return actor


@router.post("/check-email", response_model=CheckEmailResponse)
async def api_check_email(data: CheckEmailRequest, db: Session = Depends(get_db)):
    """Step 1: Check if email exists and whether it's first-time login."""
    result = check_email(db, data.email)
    return result


@router.post("/verify-setup-code", response_model=VerifySetupCodeResponse)
async def api_verify_setup_code(data: VerifySetupCodeRequest, db: Session = Depends(get_db)):
    """Step 2 (first-time): Verify the setup code given by admin."""
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
async def api_set_password(data: SetPasswordRequest, db: Session = Depends(get_db)):
    """Step 3 (first-time): Set password and get TOTP QR code."""
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
async def api_confirm_totp(data: ConfirmTotpRequest, db: Session = Depends(get_db)):
    """Step 4 (first-time): Confirm TOTP is set up correctly. Completes first-time setup."""
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


@router.post("/login", response_model=LoginResponse)
async def api_login(data: LoginRequest, db: Session = Depends(get_db)):
    """Normal login: email + password + authenticator code."""
    result = login(db, data.email, data.password, data.totp_code)
    employee = _employee_by_email(db, data.email)
    _audit_auth_event(
        db,
        "user_login" if result.get("success") else "user_login_failed",
        employee,
        None if result.get("success") else result.get("message", "Login failed"),
    )
    return result


@router.post("/login/verify-password", response_model=VerifyLoginPasswordResponse)
async def api_verify_login_password(
    data: VerifyLoginPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Step 1 login: validate password before showing MFA."""
    ip_address = request.client.host if request.client else None
    return verify_login_password(db, data.email, data.password, ip_address=ip_address)


@router.post("/login/verify-mfa", response_model=LoginResponse)
async def api_complete_login_mfa(
    data: CompleteLoginMfaRequest,
    db: Session = Depends(get_db),
):
    """Step 2 login: validate MFA for a short-lived login challenge."""
    return complete_login_mfa(db, data.login_challenge_token, data.totp_code)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def api_forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using authenticator code as verification."""
    success = reset_password(db, data.email, data.totp_code, data.new_password)
    employee = _employee_by_email(db, data.email)
    _audit_auth_event(
        db,
        "user_password_changed" if success else "user_password_change_failed",
        employee,
        None if success else "Invalid authenticator code",
    )
    return ForgotPasswordResponse(
        success=success,
        message="Password reset successfully" if success else "Invalid authenticator code",
    )


@router.post("/forgot-password/initiate", response_model=ForgotPasswordInitiateResponse)
async def api_forgot_password_initiate(
    data: ForgotPasswordInitiateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Start staged password recovery. Returns a dev token until email delivery is wired."""
    _check_reset_rate_limit(request, data.email)
    return initiate_reset(db, data.email)


@router.post("/forgot-password/verify-mfa", response_model=ForgotPasswordVerifyMfaResponse)
async def api_forgot_password_verify_mfa(
    data: ForgotPasswordVerifyMfaRequest,
    db: Session = Depends(get_db),
):
    """Verify authenticator code for a reset session."""
    return verify_reset_mfa(db, data.reset_token, data.totp_code)


@router.post("/forgot-password/reset", response_model=ForgotPasswordResponse)
async def api_forgot_password_reset(
    data: ForgotPasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Complete staged password reset."""
    return complete_reset(db, data.reset_token, data.new_password, data.confirm_password)


@router.post("/admin-reset-password", response_model=AdminResetPasswordResponse)
async def api_admin_reset_password(
    data: AdminResetPasswordRequest,
    actor: Employee = Depends(_actor_from_headers),
    db: Session = Depends(get_db),
):
    """Allow Super Admin/HR/Admin to issue a temporary password."""
    return admin_reset_password(db, actor, data.employee_id, data.reason)


@router.post("/force-change-password", response_model=ForceChangePasswordResponse)
async def api_force_change_password(
    data: ForceChangePasswordRequest,
    actor: Employee = Depends(_actor_from_headers),
    db: Session = Depends(get_db),
):
    """Required password change after admin reset."""
    return force_change_password(db, actor, data.current_password, data.new_password, data.confirm_password)


@router.post("/request-unlock")
async def api_request_unlock(
    data: RequestUnlockRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Request account unlock from the login screen. Always returns a generic response."""
    _check_unlock_rate_limit(request, data.email)
    return create_unlock_request_anonymous(db, data.email, data.reason)


@router.post("/request-unlock-for-colleague")
async def api_request_unlock_for_colleague(
    data: RequestUnlockForColleagueRequest,
    actor: Employee = Depends(_actor_from_headers),
    db: Session = Depends(get_db),
):
    """Authenticated request to unlock a colleague's locked account."""
    return create_unlock_request_authenticated(db, actor, data.employee_id, data.reason)


@router.get("/me/{email}")
async def get_my_profile(email: str, db: Session = Depends(get_db)):
    """Get employee profile by email — used for 'View My Profile'."""
    emp = find_employee_by_email(db, email)
    if not emp:
        return {"success": False, "message": "Profile not found"}

    from app.api.employees import serialize_employee

    return {
        "success": True,
        "employee": serialize_employee(emp),
    }
