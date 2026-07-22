"""
Authentication Service — setup codes, TOTP, password management.
"""

import io
import base64
import logging
import hashlib
import secrets
import string
from urllib.parse import urlencode
from datetime import datetime, timedelta
import bcrypt
import pyotp
import qrcode
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.employee import Employee
from app.models.login_challenge import LoginChallengeSession
from app.models.operations import Notification
from app.models.password_reset import PasswordResetSession
from app.models.unlock_request import AccountUnlockRequest
from app.models.transactional_email import AccountActivationToken
from app.services.audit_service import log_audit, mask_email
from app.services.preferences_service import get_or_create_preferences
from app.services.transactional_email_service import enqueue_email, verify_activation_token

logger = logging.getLogger(__name__)


def normalize_email(email: str | None) -> str:
    """Normalize email input before lookup or logging."""
    return (email or "").strip().lower()


def find_employee_by_email(db: Session, email: str | None) -> Employee | None:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return None
    return db.query(Employee).filter(func.lower(Employee.work_email) == normalized_email).first()


# ═══════════════════════════════════════
# SETUP CODE GENERATION
# ═══════════════════════════════════════

def generate_setup_code(last_name: str, date_of_birth) -> str:
    """
    Generate setup code: RK-{first 3 of last name}-{birth month}{last 2 of birth year}
    Example: Pendurthi, born 06/1995 → RK-PEN-0695
    """
    # Get first 3 letters, pad if short
    name_part = last_name.upper().replace(" ", "")[:3].ljust(3, "0")

    if date_of_birth:
        month = f"{date_of_birth.month:02d}"
        year = f"{date_of_birth.year % 100:02d}"
        date_part = f"{month}{year}"
    else:
        # Fallback if no DOB provided
        date_part = "0000"

    return f"RK-{name_part}-{date_part}"


# ═══════════════════════════════════════
# PASSWORD HASHING
# ═══════════════════════════════════════

def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ═══════════════════════════════════════
# TOTP (Authenticator App)
# ═══════════════════════════════════════

def generate_totp_secret() -> str:
    """Generate a new TOTP secret key."""
    return pyotp.random_base32()


def generate_totp_qr(secret: str, email: str) -> str:
    """
    Generate QR code for Microsoft Authenticator.
    Returns base64-encoded PNG image.
    """
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=email,
        issuer_name="Reknew Orbit"
    )

    # Generate QR code image
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#66785F", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code. Allows 1 window of tolerance (±30 seconds)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_reset_token() -> tuple[str, str]:
    """Generate a one-time reset token and its SHA-256 hash."""
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_reset_locked(employee: Employee) -> bool:
    return bool(employee.locked_until and employee.locked_until > datetime.utcnow())


def increment_failed_reset(db: Session, employee: Employee) -> None:
    employee.failed_reset_attempts = (employee.failed_reset_attempts or 0) + 1
    if employee.failed_reset_attempts >= settings.RESET_MAX_ATTEMPTS:
        employee.locked_until = datetime.utcnow() + timedelta(minutes=settings.RESET_LOCKOUT_MINUTES)
    db.commit()


def clear_failed_reset(db: Session, employee: Employee) -> None:
    employee.failed_reset_attempts = 0
    employee.locked_until = None
    db.commit()


def _admin_roles() -> set[str]:
    return {"super_admin", "admin", "hr_admin", "global_access"}


def _normalize_role(role: str | None) -> str:
    return (role or "").strip().lower().replace(" ", "_")


def _login_response(employee: Employee) -> dict:
    return {
        "success": True,
        "message": "Login successful",
        "token": "mock-jwt-token",
        "force_password_change": bool(employee.force_password_change),
        "employee": {
            "id": employee.id,
            "name": f"{employee.first_name} {employee.last_name}",
            "email": employee.work_email,
            "role": employee.role,
            "department": employee.department,
            "profile_image_url": employee.profile_image_url,
        },
    }


def notify_admins_account_locked(db: Session, locked_employee: Employee, ip_address: str | None = None) -> None:
    admins = db.query(Employee).filter(
        Employee.role.in_(list(_admin_roles())),
        Employee.is_active == True,
    ).all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            title=f"Account Locked: {_employee_name(locked_employee)}",
            message=f"{mask_email(locked_employee.work_email)} was locked after too many failed login attempts.",
            type="security",
            notification_type="account_locked",
            related_entity_type="employee",
            related_entity_id=locked_employee.id,
            link_url="/admin/security",
        ))


def notify_admins_unlock_requested(db: Session, request_row: AccountUnlockRequest, target_employee: Employee) -> None:
    admins = db.query(Employee).filter(
        Employee.role.in_(list(_admin_roles())),
        Employee.is_active == True,
    ).all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            title="Unlock request submitted",
            message=f"{_employee_name(target_employee)} requested account unlock review.",
            type="security",
            notification_type="unlock_requested",
            related_entity_type="account_unlock_request",
            related_entity_id=request_row.id,
            link_url="/admin/security",
        ))


def notify_employee_unlocked(db: Session, target_employee: Employee, admin: Employee) -> None:
    db.add(Notification(
        user_id=target_employee.id,
        title="Account unlocked",
        message=f"Your account was unlocked by {_employee_name(admin)}. Please sign in and update your password if prompted.",
        type="security",
        notification_type="unlock_approved",
        related_entity_type="employee",
        related_entity_id=target_employee.id,
        link_url="/login",
    ))


def increment_login_attempts(db: Session, employee: Employee, ip_address: str | None = None) -> None:
    employee.failed_login_attempts = (employee.failed_login_attempts or 0) + 1
    if employee.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS and not employee.account_locked:
        employee.account_locked = True
        employee.locked_at = datetime.utcnow()
        employee.locked_reason = "Too many failed login attempts"
        notify_admins_account_locked(db, employee, ip_address)
        _audit(
            db,
            employee,
            "account_locked",
            employee.id,
            reason=employee.locked_reason,
            metadata={"ip_address": ip_address, "failed_login_attempts": employee.failed_login_attempts},
        )
        return
    db.commit()


def clear_login_attempts(db: Session, employee: Employee) -> None:
    employee.failed_login_attempts = 0
    db.commit()


def generate_temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "RK-" + "".join(secrets.choice(alphabet) for _ in range(12))


def unlock_account(db: Session, employee: Employee, admin: Employee, notes: str | None = None) -> str:
    temporary_password = generate_temporary_password()
    employee.account_locked = False
    employee.failed_login_attempts = 0
    employee.unlocked_at = datetime.utcnow()
    employee.unlocked_by_user_id = admin.id
    employee.password_hash = hash_password(temporary_password)
    employee.password_changed_at = datetime.utcnow()
    employee.force_password_change = True
    employee.failed_reset_attempts = 0
    employee.locked_until = None
    db.query(PasswordResetSession).filter(PasswordResetSession.employee_id == employee.id).delete(synchronize_session=False)
    db.commit()
    return temporary_password


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password policy without logging the supplied value."""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters."
    if not any(char.islower() for char in password):
        return False, "Password must include a lowercase letter."
    if not any(char.isupper() for char in password):
        return False, "Password must include an uppercase letter."
    if not any(char.isdigit() for char in password):
        return False, "Password must include a number."
    if not any(char in string.punctuation for char in password):
        return False, "Password must include a special character."
    return True, "Password is valid."


def _employee_name(employee: Employee | None) -> str | None:
    if not employee:
        return None
    return f"{employee.first_name} {employee.last_name}".strip() or employee.work_email


def _audit(
    db: Session,
    actor: Employee | None,
    action: str,
    entity_id: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    log_audit(
        db=db,
        actor=actor,
        action=action,
        entity_type="auth",
        entity_id=entity_id or (actor.id if actor else None),
        reason=reason,
        metadata=metadata or {},
        source="api",
    )
    db.commit()


def _generic_reset_response() -> dict:
    return {
        "success": True,
        "message": "If the account exists and is eligible, reset instructions have been prepared.",
    }


# ═══════════════════════════════════════
# AUTH OPERATIONS
# ═══════════════════════════════════════

def check_email(db: Session, email: str) -> dict:
    """Check if email exists and return login status."""
    employee = find_employee_by_email(db, email)

    if not employee:
        return {"exists": False, "is_first_login": False, "message": "Account not found"}

    if not employee.is_active:
        return {"exists": True, "is_first_login": False, "message": "Account is deactivated", "employee_id": None, "role": None, "profile_image_url": None}

    return {
        "exists": True,
        "is_first_login": employee.is_first_login,
        "message": "First time setup required" if employee.is_first_login else "Enter your password",
        "employee_id": employee.id,
        "role": employee.role,
        "profile_image_url": employee.profile_image_url,
        "force_password_change": bool(employee.force_password_change),
    }


def verify_setup_code(db: Session, email: str, code: str) -> bool:
    """Verify a random, hashed, expiring activation token."""
    employee = find_employee_by_email(db, email)

    if not employee:
        return False

    return bool(verify_activation_token(db, employee.id, code))


def set_password_and_get_qr(db: Session, email: str, setup_code: str, password: str) -> dict:
    """Set password and generate TOTP QR code."""
    employee = find_employee_by_email(db, email)

    if not employee:
        return {"success": False, "message": "Employee not found"}

    activation = verify_activation_token(db, employee.id, setup_code)
    if not activation:
        return {"success": False, "message": "Invalid or expired activation link"}

    # Hash and store password
    employee.password_hash = hash_password(password)
    employee.password_changed_at = datetime.utcnow()
    employee.force_password_change = False

    # Generate TOTP secret
    totp_secret = generate_totp_secret()
    employee.totp_secret = totp_secret
    activation.used_at = datetime.utcnow()

    db.commit()

    # Generate QR code
    qr_base64 = generate_totp_qr(totp_secret, employee.work_email)

    logger.info(f"Password set and TOTP generated for {mask_email(employee.work_email)}")

    return {
        "success": True,
        "message": "Password set. Scan the QR code with Microsoft Authenticator.",
        "totp_qr_base64": qr_base64,
        "totp_secret": totp_secret,  # fallback for manual entry
    }


def confirm_totp_setup(db: Session, email: str, totp_code: str) -> bool:
    """Confirm TOTP is working by verifying a code. Completes first-time setup."""
    employee = find_employee_by_email(db, email)

    if not employee or not employee.totp_secret:
        return False

    if verify_totp(employee.totp_secret, totp_code):
        employee.is_first_login = False
        employee.setup_code = None  # invalidate setup code after use
        db.commit()
        logger.info(f"TOTP confirmed and setup completed for {mask_email(employee.work_email)}")
        return True

    return False


def _dev_log(msg: str) -> None:
    """Log diagnostic info in development only — never in production."""
    if settings.APP_ENV == "development":
        logger.info("[AUTH_DEBUG] " + msg)


def verify_login_password(db: Session, email: str, password: str, ip_address: str | None = None) -> dict:
    """Step 1: verify email + password and create a short-lived MFA challenge."""
    normalized_email = normalize_email(email)
    _dev_log(f"verify_login_password called for email='{mask_email(normalized_email)}' ip={ip_address}")
    employee = find_employee_by_email(db, normalized_email)
    generic = {"success": False, "message": "Invalid email or password."}

    if not employee:
        _dev_log(f"no employee found for email='{mask_email(normalized_email)}'")
        return generic
    _dev_log(
        f"employee found: id={employee.id} is_active={employee.is_active} "
        f"is_first_login={employee.is_first_login} account_locked={employee.account_locked} "
        f"has_password_hash={bool(employee.password_hash)} "
        f"failed_login_attempts={employee.failed_login_attempts} "
        f"force_password_change={employee.force_password_change}"
    )
    if employee.account_locked:
        return {
            "success": False,
            "message": "Your account is locked. Please request an unlock or contact your administrator.",
            "account_locked": True,
        }
    if not employee.is_active:
        return {"success": False, "message": "Account is deactivated."}
    if employee.is_first_login:
        return {"success": False, "message": "Please complete your first-time setup."}
    pw_ok = bool(employee.password_hash) and verify_password(password, employee.password_hash)
    _dev_log(f"password verification result: {pw_ok} (hash present: {bool(employee.password_hash)})")
    if not pw_ok:
        increment_login_attempts(db, employee, ip_address)
        attempts = int(employee.failed_login_attempts or 0)
        attempts_remaining = max(0, settings.MAX_LOGIN_ATTEMPTS - attempts)
        _audit(
            db,
            employee,
            "login_failed_wrong_password",
            employee.id,
            reason="Invalid email or password",
            metadata={"attempts_remaining": attempts_remaining, "ip_address": ip_address},
        )
        if employee.account_locked:
            return {
                "success": False,
                "message": "Your account is locked. Please request an unlock or contact your administrator.",
                "account_locked": True,
                "attempts_remaining": 0,
            }
        return {**generic, "attempts_remaining": attempts_remaining}

    employee.failed_login_attempts = 0
    if employee.force_password_change:
        db.commit()
        _audit(db, employee, "temporary_password_verified", employee.id, metadata={"ip_address": ip_address})
        result = _login_response(employee)
        result["message"] = "Temporary password verified. Create a new password."
        return result
    db.query(LoginChallengeSession).filter(
        LoginChallengeSession.employee_id == employee.id,
        LoginChallengeSession.used_at.is_(None),
    ).delete(synchronize_session=False)
    plain_token, token_hash = generate_reset_token()
    db.add(LoginChallengeSession(
        employee_id=employee.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.LOGIN_CHALLENGE_EXPIRY_MINUTES),
    ))
    db.commit()
    _audit(db, employee, "login_password_verified", employee.id, metadata={"ip_address": ip_address})
    return {
        "success": True,
        "message": "Password verified. Enter your authenticator code.",
        "login_challenge_token": plain_token,
    }


def complete_login_mfa(db: Session, login_challenge_token: str, totp_code: str) -> dict:
    """Step 2: verify MFA for a password-verified login challenge."""
    token_hash = hash_reset_token(login_challenge_token)
    session = db.query(LoginChallengeSession).filter(
        LoginChallengeSession.token_hash == token_hash,
        LoginChallengeSession.used_at.is_(None),
    ).first()
    if not session or session.expires_at <= datetime.utcnow():
        return {"success": False, "message": "Login session is invalid or expired. Please enter your password again."}

    employee = db.query(Employee).filter(Employee.id == session.employee_id).first()
    if not employee or not employee.is_active:
        return {"success": False, "message": "Account is not available."}
    if employee.account_locked:
        return {"success": False, "message": "Your account is locked.", "account_locked": True}
    if not employee.totp_secret or not verify_totp(employee.totp_secret, totp_code):
        _audit(db, employee, "login_mfa_failed", employee.id, reason="Invalid authenticator code")
        return {"success": False, "message": "Invalid authenticator code."}

    session.used_at = datetime.utcnow()
    employee.last_login_at = datetime.utcnow()
    db.commit()
    get_or_create_preferences(db, employee.id)
    _audit(db, employee, "login_mfa_success", employee.id)
    return _login_response(employee)


def login(db: Session, email: str, password: str, totp_code: str) -> dict:
    """Authenticate with email + password + TOTP code."""
    normalized_email = normalize_email(email)
    _dev_log(f"login called for email='{mask_email(normalized_email)}'")
    employee = find_employee_by_email(db, normalized_email)

    if not employee:
        _dev_log(f"login user found: false email='{mask_email(normalized_email)}'")
        return {"success": False, "message": "Account not found"}
    _dev_log(
        f"login user found: true id={employee.id} locked={employee.account_locked} "
        f"force_password_change={employee.force_password_change} failed_login_attempts={employee.failed_login_attempts} "
        f"has_password_hash={bool(employee.password_hash)}"
    )

    if employee.account_locked:
        return {"success": False, "message": "Your account is locked.", "account_locked": True}

    if not employee.is_active:
        return {"success": False, "message": "Account is deactivated"}

    if employee.is_first_login:
        return {"success": False, "message": "Please complete your first-time setup"}

    if not employee.password_hash:
        return {"success": False, "message": "Password not set"}

    password_verified = verify_password(password, employee.password_hash)
    _dev_log(f"login password verification result: {password_verified}")
    if not password_verified:
        increment_login_attempts(db, employee)
        return {"success": False, "message": "Invalid password", "account_locked": bool(employee.account_locked)}

    if not employee.totp_secret or not verify_totp(employee.totp_secret, totp_code):
        return {"success": False, "message": "Invalid authenticator code"}

    employee.failed_login_attempts = 0
    employee.last_login_at = datetime.utcnow()
    db.commit()
    get_or_create_preferences(db, employee.id)
    logger.info(f"Login successful for {mask_email(employee.work_email)}")

    return _login_response(employee)


def reset_password(db: Session, email: str, totp_code: str, new_password: str) -> bool:
    """Reset password using TOTP verification."""
    employee = find_employee_by_email(db, email)

    if not employee or not employee.totp_secret:
        return False

    if not verify_totp(employee.totp_secret, totp_code):
        return False

    employee.password_hash = hash_password(new_password)
    employee.password_changed_at = datetime.utcnow()
    employee.force_password_change = False
    db.commit()
    logger.info(f"Password reset for {mask_email(employee.work_email)}")
    return True


def initiate_reset(db: Session, email: str) -> dict:
    """Create a one-time reset token and queue it for email without returning it."""
    normalized_email = normalize_email(email)
    employee = find_employee_by_email(db, normalized_email)
    metadata = {"email": mask_email(normalized_email)}

    if not employee or not employee.is_active or is_reset_locked(employee):
        logger.info(
            "password_reset_queue matching_user_found=%s eligible=%s outbox_enqueued=false",
            bool(employee),
            bool(employee and employee.is_active and not is_reset_locked(employee)),
        )
        _audit(db, employee, "password_reset_requested", getattr(employee, "id", None), metadata=metadata)
        return _generic_reset_response()

    token, token_hash = generate_reset_token()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_EXPIRY_MINUTES)

    db.query(PasswordResetSession).filter(
        PasswordResetSession.employee_id == employee.id,
        PasswordResetSession.used_at.is_(None),
    ).delete(synchronize_session=False)

    db.add(PasswordResetSession(
        employee_id=employee.id,
        reset_token_hash=token_hash,
        expires_at=expires_at,
    ))
    query = urlencode({"email": normalized_email, "reset_token": token, "has_mfa": "1" if employee.totp_secret else "0"})
    outbox_row = enqueue_email(
        db,
        recipient=employee.work_email,
        template_name="password_reset",
        idempotency_key=f"password-reset:{employee.id}:{token_hash}",
        context={
            "reset_url": f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login?{query}",
            "expires_minutes": settings.RESET_TOKEN_EXPIRY_MINUTES,
        },
    )
    db.commit()
    logger.info(
        "password_reset_queue matching_user_found=true eligible=true outbox_enqueued=%s",
        bool(outbox_row),
    )
    _audit(db, employee, "password_reset_requested", employee.id, metadata=metadata)
    return _generic_reset_response()


def _active_reset_session(db: Session, reset_token: str) -> tuple[PasswordResetSession | None, Employee | None]:
    token_hash = hash_reset_token(reset_token)
    session = db.query(PasswordResetSession).filter(
        PasswordResetSession.reset_token_hash == token_hash,
        PasswordResetSession.used_at.is_(None),
    ).first()
    if not session:
        return None, None
    employee = db.query(Employee).filter(Employee.id == session.employee_id).first()
    if not employee or not employee.is_active or session.expires_at <= datetime.utcnow():
        return session, employee
    return session, employee


def verify_reset_mfa(db: Session, reset_token: str, totp_code: str) -> dict:
    """Verify MFA before allowing password reset completion."""
    session, employee = _active_reset_session(db, reset_token)
    if not session or not employee or session.expires_at <= datetime.utcnow():
        return {"success": False, "message": "Reset session is invalid or expired."}
    if is_reset_locked(employee):
        return {"success": False, "message": "Too many failed attempts. Please try again later."}
    if not employee.totp_secret:
        return {"success": False, "message": "Authenticator is not configured for this account."}

    if not verify_totp(employee.totp_secret, totp_code):
        increment_failed_reset(db, employee)
        _audit(db, employee, "password_reset_mfa_failed", employee.id, reason="Invalid authenticator code")
        if is_reset_locked(employee):
            _audit(db, employee, "account_temporarily_locked", employee.id, reason="Too many failed reset attempts")
        return {"success": False, "message": "Invalid authenticator code."}

    session.mfa_verified = True
    clear_failed_reset(db, employee)
    db.commit()
    _audit(db, employee, "password_reset_mfa_verified", employee.id)
    return {"success": True, "message": "Authenticator verified. You can now set a new password."}


def complete_reset(db: Session, reset_token: str, new_password: str, confirm_password: str) -> dict:
    """Complete a staged password reset."""
    if new_password != confirm_password:
        return {"success": False, "message": "Passwords do not match."}
    valid, message = validate_password_strength(new_password)
    if not valid:
        return {"success": False, "message": message}

    session, employee = _active_reset_session(db, reset_token)
    if not session or not employee or session.expires_at <= datetime.utcnow():
        return {"success": False, "message": "Reset session is invalid or expired."}
    if employee.totp_secret and not session.mfa_verified:
        return {"success": False, "message": "Authenticator verification is required."}

    employee.password_hash = hash_password(new_password)
    employee.password_changed_at = datetime.utcnow()
    employee.force_password_change = False
    employee.failed_reset_attempts = 0
    employee.locked_until = None
    session.used_at = datetime.utcnow()
    db.query(PasswordResetSession).filter(
        PasswordResetSession.employee_id == employee.id,
        PasswordResetSession.id != session.id,
    ).delete(synchronize_session=False)
    enqueue_email(
        db,
        recipient=employee.work_email,
        template_name="password_changed",
        idempotency_key=f"password-changed:{session.id}",
        context={"first_name": employee.first_name, "changed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M")},
    )
    db.commit()
    _audit(db, employee, "user_password_changed", employee.id, reason="Self-service password reset")
    return {"success": True, "message": "Password reset successfully. You can now log in."}


def admin_reset_password(db: Session, actor: Employee, employee_id: str, reason: str) -> dict:
    """Admin-triggered temporary password reset with forced change on next login."""
    if actor.role not in {"super_admin", "hr_admin", "admin"}:
        _audit(db, actor, "admin_password_reset_denied", employee_id, reason="Insufficient role")
        raise HTTPException(status_code=403, detail="You are not allowed to reset employee passwords.")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if actor.id == employee.id:
        raise HTTPException(status_code=400, detail="Use the password change flow for your own account.")

    temporary_password = generate_temporary_password()
    employee.account_locked = False
    employee.locked_at = None
    employee.locked_reason = None
    employee.unlocked_at = datetime.utcnow()
    employee.unlocked_by_user_id = actor.id
    employee.failed_login_attempts = 0
    employee.password_hash = hash_password(temporary_password)
    employee.password_changed_at = datetime.utcnow()
    employee.force_password_change = True
    employee.failed_reset_attempts = 0
    employee.locked_until = None
    db.query(PasswordResetSession).filter(PasswordResetSession.employee_id == employee.id).delete(synchronize_session=False)
    db.commit()
    _audit(
        db,
        actor,
        "admin_password_reset",
        employee.id,
        reason=reason,
        metadata={"employee": _employee_name(employee), "email": mask_email(employee.work_email)},
    )
    return {
        "success": True,
        "message": "Temporary password generated. Employee must change it on next login.",
        "temporary_password": temporary_password,
    }


def force_change_password(db: Session, employee: Employee, current_password: str | None, new_password: str, confirm_password: str) -> dict:
    """Change a temporary/admin-reset password after login."""
    if not employee.force_password_change:
        return {"success": False, "message": "Password change is not required for this account."}
    if current_password:
        if not employee.password_hash or not verify_password(current_password, employee.password_hash):
            _audit(db, employee, "forced_password_change_failed", employee.id, reason="Invalid current password")
            return {"success": False, "message": "Current password is incorrect."}
        if current_password == new_password:
            return {"success": False, "message": "New password must be different from the temporary password."}
    if new_password != confirm_password:
        return {"success": False, "message": "Passwords do not match."}
    valid, message = validate_password_strength(new_password)
    if not valid:
        return {"success": False, "message": message}

    employee.password_hash = hash_password(new_password)
    employee.password_changed_at = datetime.utcnow()
    employee.force_password_change = False
    db.commit()
    _audit(db, employee, "forced_password_changed", employee.id)
    return {"success": True, "message": "Password changed successfully."}


def create_unlock_request_anonymous(db: Session, email: str, reason: str) -> dict:
    """Create an unlock request from the login screen without revealing account existence."""
    normalized_email = normalize_email(email)
    employee = find_employee_by_email(db, normalized_email)
    if employee and employee.account_locked:
        existing = db.query(AccountUnlockRequest).filter(
            AccountUnlockRequest.locked_user_id == employee.id,
            AccountUnlockRequest.status == "pending",
        ).first()
        if not existing:
            row = AccountUnlockRequest(
                locked_user_id=employee.id,
                requested_email=normalized_email,
                request_reason=reason,
                status="pending",
            )
            db.add(row)
            db.flush()
            notify_admins_unlock_requested(db, row, employee)
            db.commit()
            _audit(
                db,
                employee,
                "account_unlock_requested",
                employee.id,
                reason="Self-service unlock request",
                metadata={"request_id": row.id, "requested_by": "anonymous"},
            )
    return {"success": True, "message": "If this account is locked, an unlock request has been sent for admin review."}


def create_unlock_request_authenticated(db: Session, requester: Employee, target_employee_id: str, reason: str) -> dict:
    target = db.query(Employee).filter(Employee.id == target_employee_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if not target.account_locked:
        raise HTTPException(status_code=400, detail="This employee account is not locked.")
    existing = db.query(AccountUnlockRequest).filter(
        AccountUnlockRequest.locked_user_id == target.id,
        AccountUnlockRequest.status == "pending",
    ).first()
    if existing:
        return {"success": True, "message": "An unlock request is already pending."}
    row = AccountUnlockRequest(
        locked_user_id=target.id,
        requested_by_user_id=requester.id,
        requested_email=target.work_email,
        request_reason=reason,
        status="pending",
    )
    db.add(row)
    db.flush()
    notify_admins_unlock_requested(db, row, target)
    db.commit()
    _audit(db, requester, "account_unlock_requested", target.id, metadata={"request_id": row.id, "requested_by": requester.id})
    return {"success": True, "message": "Unlock request submitted."}


def _require_unlock_admin(admin: Employee) -> None:
    if _normalize_role(admin.role) not in _admin_roles():
        raise HTTPException(status_code=403, detail="Only Super Admin, Admin, or HR can review account unlocks.")


def approve_unlock(db: Session, admin: Employee, request_id: str, admin_notes: str | None = None) -> dict:
    _require_unlock_admin(admin)
    row = db.query(AccountUnlockRequest).filter(AccountUnlockRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Unlock request not found.")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Unlock request is already reviewed.")
    target = db.query(Employee).filter(Employee.id == row.locked_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own unlock request.")
    temporary_password = unlock_account(db, target, admin, admin_notes)
    row.status = "approved"
    row.reviewed_by_user_id = admin.id
    row.reviewed_at = datetime.utcnow()
    row.admin_notes = admin_notes
    row.updated_at = datetime.utcnow()
    notify_employee_unlocked(db, target, admin)
    db.commit()
    _audit(db, admin, "account_unlock_approved", target.id, reason=admin_notes, metadata={"request_id": row.id})
    return {
        "success": True,
        "message": "Account unlocked. Share the temporary password with the employee; they must change it on next login.",
        "temporary_password": temporary_password,
    }


def reject_unlock(db: Session, admin: Employee, request_id: str, admin_notes: str | None = None) -> dict:
    _require_unlock_admin(admin)
    row = db.query(AccountUnlockRequest).filter(AccountUnlockRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Unlock request not found.")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Unlock request is already reviewed.")
    row.status = "rejected"
    row.reviewed_by_user_id = admin.id
    row.reviewed_at = datetime.utcnow()
    row.admin_notes = admin_notes
    row.updated_at = datetime.utcnow()
    target = db.query(Employee).filter(Employee.id == row.locked_user_id).first()
    if target:
        db.add(Notification(
            user_id=target.id,
            title="Unlock request rejected",
            message="Your account unlock request was reviewed and rejected. Please contact HR for help.",
            type="security",
            notification_type="unlock_rejected",
            related_entity_type="account_unlock_request",
            related_entity_id=row.id,
            link_url="/login",
        ))
    db.commit()
    _audit(db, admin, "account_unlock_rejected", row.locked_user_id, reason=admin_notes, metadata={"request_id": row.id})
    return {"success": True, "message": "Unlock request rejected."}


def direct_unlock(db: Session, admin: Employee, employee_id: str, admin_notes: str | None = None) -> dict:
    _require_unlock_admin(admin)
    target = db.query(Employee).filter(Employee.id == employee_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=403, detail="You cannot unlock your own account.")
    temporary_password = unlock_account(db, target, admin, admin_notes)
    notify_employee_unlocked(db, target, admin)
    db.commit()
    _audit(db, admin, "account_directly_unlocked", target.id, reason=admin_notes)
    return {
        "success": True,
        "message": "Account unlocked directly. Share the temporary password with the employee; they must change it on next login.",
        "temporary_password": temporary_password,
    }
