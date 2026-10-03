"""
Pydantic schemas for API validation.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional
from datetime import date
from app.core.rbac import EmploymentType, UserRole, canonical_employment_type, canonical_role


# ═══════════════════════════════════════
# ADD EMPLOYEE
# ═══════════════════════════════════════

class AddEmployeeRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    work_email: EmailStr
    country_code: str = Field(default="+91")
    phone: str = Field(..., min_length=1, max_length=20)
    date_of_birth: Optional[date] = None  # needed for setup code

    workforce_type: EmploymentType
    employment_type: Optional[EmploymentType] = None
    role: UserRole
    department: str
    designation: Optional[str] = None
    reporting_manager: str
    joining_date: date
    work_location: str
    work_city: Optional[str] = Field(default=None, max_length=120)
    work_state: Optional[str] = Field(default=None, max_length=120)
    work_country: Optional[str] = Field(default=None, max_length=120)

    @field_validator("first_name", "last_name", "department", "reporting_manager", "work_location")
    @classmethod
    def validate_required_text(cls, value: str):
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str):
        normalized = value.strip()
        digit_count = sum(character.isdigit() for character in normalized)
        if digit_count < 7 or digit_count > 15:
            raise ValueError("must contain 7 to 15 digits")
        return normalized

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: Optional[date]):
        if value is not None and value > date.today():
            raise ValueError("cannot be in the future")
        return value

    @field_validator("work_city", "work_state", "work_country")
    @classmethod
    def normalize_optional_location(cls, value: Optional[str]):
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, value):
        return canonical_role(value, allow_safe_legacy=False)

    @field_validator("workforce_type", "employment_type", mode="before")
    @classmethod
    def validate_employment_type(cls, value):
        return None if value is None else canonical_employment_type(value)

    @model_validator(mode="after")
    def align_employment_type(self):
        if self.employment_type is None:
            self.employment_type = self.workforce_type
        return self


class AddEmployeeResponse(BaseModel):
    success: bool
    message: str
    employee_id: Optional[str] = None
    setup_code: Optional[str] = None


# ═══════════════════════════════════════
# UPDATE EMPLOYEE
# ═══════════════════════════════════════

class UpdateEmployeeRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    personal_email: Optional[str] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    department: Optional[str] = Field(default=None, max_length=100)
    designation: Optional[str] = None
    role: Optional[UserRole] = None
    workforce_type: Optional[EmploymentType] = None
    employment_type: Optional[EmploymentType] = None
    workforce_status: Optional[str] = None
    employment_status: Optional[str] = None
    work_location: Optional[str] = None
    work_city: Optional[str] = Field(default=None, max_length=120)
    work_state: Optional[str] = Field(default=None, max_length=120)
    work_country: Optional[str] = Field(default=None, max_length=120)
    reporting_manager: Optional[str] = Field(default=None, max_length=100)
    joining_date: Optional[date] = None
    location: Optional[str] = None
    date_of_exit: Optional[date] = None
    inactive_reason: Optional[str] = None
    onboarding_type: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    current_address: Optional[str] = None
    permanent_address: Optional[str] = None
    profile_image_url: Optional[str] = None
    access_level: Optional[str] = None
    mfa_enabled: Optional[bool] = None
    device_assigned: Optional[bool] = None
    notes: Optional[str] = None
    change_reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, value):
        return None if value is None else canonical_role(value, allow_safe_legacy=False)

    @field_validator("workforce_type", "employment_type", mode="before")
    @classmethod
    def validate_employment_type(cls, value):
        return None if value is None else canonical_employment_type(value)


# ═══════════════════════════════════════
# AUTH — CHECK EMAIL
# ═══════════════════════════════════════

class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckEmailResponse(BaseModel):
    exists: bool
    is_first_login: bool = False
    message: str
    employee_id: str | None = None
    role: str | None = None
    profile_image_url: str | None = None
    force_password_change: bool = False


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
    mfa_setup_required: bool = True
    totp_qr_base64: Optional[str] = None
    totp_secret: Optional[str] = None  # manual entry fallback


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
    force_password_change: bool = False


class CurrentUserProfile(BaseModel):
    """Bounded owner-only profile returned from the authenticated subject."""

    id: str
    first_name: str
    last_name: str
    work_email: EmailStr
    personal_email: Optional[EmailStr] = None
    phone: str
    country_code: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    department: str
    designation: Optional[str] = None
    role: str
    permissions: list[str] = Field(default_factory=list)
    scopes: dict[str, list[str]] = Field(default_factory=dict)
    workforce_type: str
    employment_type: Optional[str] = None
    employment_status: str
    work_location: str
    work_city: Optional[str] = None
    work_state: Optional[str] = None
    work_country: Optional[str] = None
    joining_date: Optional[str] = None
    reporting_manager: str
    manager_id: Optional[str] = None
    profile_image_url: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    current_address: Optional[str] = None
    is_active: bool
    account_locked: bool
    access_level: str
    mfa_enabled: bool
    force_password_change: bool
    last_login_at: Optional[str] = None
    last_active_at: Optional[str] = None
    created_at: str
    last_updated_at: Optional[str] = None


class CurrentUserProfileResponse(BaseModel):
    success: bool = True
    employee: CurrentUserProfile


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


class ForgotPasswordInitiateRequest(BaseModel):
    email: EmailStr


class ForgotPasswordInitiateResponse(BaseModel):
    success: bool
    message: str


class ForgotPasswordVerifyMfaRequest(BaseModel):
    reset_token: str = Field(..., min_length=20)
    totp_code: str = Field(..., min_length=6, max_length=6)


class ForgotPasswordVerifyMfaResponse(BaseModel):
    success: bool
    message: str


class ForgotPasswordResetRequest(BaseModel):
    reset_token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class AdminResetPasswordRequest(BaseModel):
    employee_id: str
    reason: str = Field(..., min_length=3, max_length=500)


class AdminResetPasswordResponse(BaseModel):
    success: bool
    message: str
    temporary_password: Optional[str] = None


class ForceChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class ForceChangePasswordResponse(BaseModel):
    success: bool
    message: str


class VerifyLoginPasswordRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyLoginPasswordResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    login_challenge_token: Optional[str] = None
    account_locked: bool = False
    attempts_remaining: Optional[int] = None
    employee: Optional[dict] = None
    force_password_change: bool = False


class CompleteLoginMfaRequest(BaseModel):
    login_challenge_token: str = Field(..., min_length=20)
    totp_code: str = Field(..., min_length=6, max_length=6)


class RequestUnlockRequest(BaseModel):
    email: EmailStr
    reason: str = Field(..., min_length=10, max_length=500)


class RequestUnlockForColleagueRequest(BaseModel):
    employee_id: str
    reason: str = Field(..., min_length=10, max_length=500)


class ReviewUnlockRequest(BaseModel):
    admin_notes: Optional[str] = Field(default=None, max_length=500)
