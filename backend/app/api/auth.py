"""
Auth API endpoints — first-time setup + login + forgot password.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.employee import (
    CheckEmailRequest, CheckEmailResponse,
    VerifySetupCodeRequest, VerifySetupCodeResponse,
    SetPasswordRequest, SetPasswordResponse,
    ConfirmTotpRequest, ConfirmTotpResponse,
    LoginRequest, LoginResponse,
    ForgotPasswordRequest, ForgotPasswordResponse,
)
from app.services.auth_service import (
    check_email,
    verify_setup_code,
    set_password_and_get_qr,
    confirm_totp_setup,
    login,
    reset_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/check-email", response_model=CheckEmailResponse)
async def api_check_email(data: CheckEmailRequest, db: Session = Depends(get_db)):
    """Step 1: Check if email exists and whether it's first-time login."""
    result = check_email(db, data.email)
    return result


@router.post("/verify-setup-code", response_model=VerifySetupCodeResponse)
async def api_verify_setup_code(data: VerifySetupCodeRequest, db: Session = Depends(get_db)):
    """Step 2 (first-time): Verify the setup code given by admin."""
    success = verify_setup_code(db, data.email, data.setup_code)
    return VerifySetupCodeResponse(
        success=success,
        message="Setup code verified" if success else "Invalid setup code",
    )


@router.post("/set-password", response_model=SetPasswordResponse)
async def api_set_password(data: SetPasswordRequest, db: Session = Depends(get_db)):
    """Step 3 (first-time): Set password and get TOTP QR code."""
    result = set_password_and_get_qr(db, data.email, data.setup_code, data.password)
    return result


@router.post("/confirm-totp", response_model=ConfirmTotpResponse)
async def api_confirm_totp(data: ConfirmTotpRequest, db: Session = Depends(get_db)):
    """Step 4 (first-time): Confirm TOTP is set up correctly. Completes first-time setup."""
    success = confirm_totp_setup(db, data.email, data.totp_code)
    return ConfirmTotpResponse(
        success=success,
        message="Authenticator setup complete! You can now log in." if success else "Invalid code. Please try again.",
    )


@router.post("/login", response_model=LoginResponse)
async def api_login(data: LoginRequest, db: Session = Depends(get_db)):
    """Normal login: email + password + authenticator code."""
    result = login(db, data.email, data.password, data.totp_code)
    return result


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def api_forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using authenticator code as verification."""
    success = reset_password(db, data.email, data.totp_code, data.new_password)
    return ForgotPasswordResponse(
        success=success,
        message="Password reset successfully" if success else "Invalid authenticator code",
    )
