"""
Authentication Service — setup codes, TOTP, password management.
"""

import io
import base64
import logging
import bcrypt
import pyotp
import qrcode
from sqlalchemy.orm import Session
from app.models.employee import Employee

logger = logging.getLogger(__name__)


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


# ═══════════════════════════════════════
# AUTH OPERATIONS
# ═══════════════════════════════════════

def check_email(db: Session, email: str) -> dict:
    """Check if email exists and return login status."""
    employee = db.query(Employee).filter(Employee.work_email == email).first()

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
    }


def verify_setup_code(db: Session, email: str, code: str) -> bool:
    """Verify the setup code for first-time login."""
    employee = db.query(Employee).filter(Employee.work_email == email).first()

    if not employee:
        return False

    return employee.setup_code and employee.setup_code.upper() == code.upper()


def set_password_and_get_qr(db: Session, email: str, setup_code: str, password: str) -> dict:
    """Set password and generate TOTP QR code."""
    employee = db.query(Employee).filter(Employee.work_email == email).first()

    if not employee:
        return {"success": False, "message": "Employee not found"}

    if not employee.setup_code or employee.setup_code.upper() != setup_code.upper():
        return {"success": False, "message": "Invalid setup code"}

    # Hash and store password
    employee.password_hash = hash_password(password)

    # Generate TOTP secret
    totp_secret = generate_totp_secret()
    employee.totp_secret = totp_secret

    db.commit()

    # Generate QR code
    qr_base64 = generate_totp_qr(totp_secret, email)

    logger.info(f"Password set and TOTP generated for {email}")

    return {
        "success": True,
        "message": "Password set. Scan the QR code with Microsoft Authenticator.",
        "totp_qr_base64": qr_base64,
        "totp_secret": totp_secret,  # fallback for manual entry
    }


def confirm_totp_setup(db: Session, email: str, totp_code: str) -> bool:
    """Confirm TOTP is working by verifying a code. Completes first-time setup."""
    employee = db.query(Employee).filter(Employee.work_email == email).first()

    if not employee or not employee.totp_secret:
        return False

    if verify_totp(employee.totp_secret, totp_code):
        employee.is_first_login = False
        employee.setup_code = None  # invalidate setup code after use
        db.commit()
        logger.info(f"TOTP confirmed and setup completed for {email}")
        return True

    return False


def login(db: Session, email: str, password: str, totp_code: str) -> dict:
    """Authenticate with email + password + TOTP code."""
    employee = db.query(Employee).filter(Employee.work_email == email).first()

    if not employee:
        return {"success": False, "message": "Account not found"}

    if not employee.is_active:
        return {"success": False, "message": "Account is deactivated"}

    if employee.is_first_login:
        return {"success": False, "message": "Please complete your first-time setup"}

    if not employee.password_hash:
        return {"success": False, "message": "Password not set"}

    if not verify_password(password, employee.password_hash):
        return {"success": False, "message": "Invalid password"}

    if not employee.totp_secret or not verify_totp(employee.totp_secret, totp_code):
        return {"success": False, "message": "Invalid authenticator code"}

    logger.info(f"Login successful for {email}")

    return {
        "success": True,
        "message": "Login successful",
        "token": "mock-jwt-token",  # Replace with real JWT later
        "employee": {
            "id": employee.id,
            "name": f"{employee.first_name} {employee.last_name}",
            "email": employee.work_email,
            "role": employee.role,
            "department": employee.department,
            "profile_image_url": employee.profile_image_url,
        },
    }


def reset_password(db: Session, email: str, totp_code: str, new_password: str) -> bool:
    """Reset password using TOTP verification."""
    employee = db.query(Employee).filter(Employee.work_email == email).first()

    if not employee or not employee.totp_secret:
        return False

    if not verify_totp(employee.totp_secret, totp_code):
        return False

    employee.password_hash = hash_password(new_password)
    db.commit()
    logger.info(f"Password reset for {email}")
    return True
