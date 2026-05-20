"""
Pydantic schemas for API validation.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date


# ═══════════════════════════════════════
# ADD EMPLOYEE
# ═══════════════════════════════════════

class AddEmployeeRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    work_email: EmailStr
    country_code: str = Field(default="+91")
    phone: str = Field(..., min_length=1, max_length=20)
    date_of_birth: Optional[date] = None

    workforce_type: str
    role: str
    department: str
    designation: Optional[str] = None
    reporting_manager: str
    joining_date: date
    work_location: str

    create_account: bool = True
    create_checklist: bool = True
    onboarding_type: Optional[str] = "Standard Employee"


class OnboardingTask(BaseModel):
    title: str
    status: str = "pending"


class AddEmployeeResponse(BaseModel):
    success: bool
    message: str
    employee_id: Optional[str] = None
    setup_code: Optional[str] = None
    checklist_created: bool = False
    onboarding_tasks: list[OnboardingTask] = []


# ═══════════════════════════════════════
# AUTH — CHECK EMAIL
# ═══════════════════════════════════════

class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckEmailResponse(BaseModel):
    exists: bool
    is_first_login: bool = False
    message: str


# ═══════════════════════════════════════
# AUTH — VERIFY SETUP CODE
# ═══════════════════════════════════════

class VerifySetupCodeRequest(BaseModel):
    email: EmailStr
    setup_code: str


class VerifySetupCodeResponse(BaseModel):
    success: bool
    message: str


# ═══════════════════════════════════════
# AUTH — SET PASSWORD + GET TOTP QR
# ═══════════════════════════════════════

class SetPasswordRequest(BaseModel):
    email: EmailStr
    setup_code: str
    password: str = Field(..., min_length=6)


class SetPasswordResponse(BaseModel):
    success: bool
    message: str
    totp_qr_base64: Optional[str] = None
    totp_secret: Optional[str] = None


# ═══════════════════════════════════════
# AUTH — CONFIRM TOTP SETUP
# ═══════════════════════════════════════

class ConfirmTotpRequest(BaseModel):
    email: EmailStr
    totp_code: str = Field(..., min_length=6, max_length=6)


class ConfirmTotpResponse(BaseModel):
    success: bool
    message: str


# ═══════════════════════════════════════
# AUTH — LOGIN
# ═══════════════════════════════════════

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str = Field(..., min_length=6, max_length=6)


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    employee: Optional[dict] = None


# ═══════════════════════════════════════
# AUTH — FORGOT PASSWORD
# ═══════════════════════════════════════

class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    totp_code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6)


class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str