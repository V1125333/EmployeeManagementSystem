"""
Security helpers for sensitive data handling, masking, export authorization, and auditing.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from datetime import date, datetime
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.security import SensitiveAccessAuditLog
from app.services.audit_service import log_audit
from app.services.settings_service import normalize_role


PUBLIC_EMPLOYEE_EXPORT_FIELDS = [
    "employee_code",
    "first_name",
    "last_name",
    "work_email",
    "department",
    "designation",
    "role",
    "workforce_type",
    "employment_status",
    "work_location",
    "work_city",
    "work_state",
    "work_country",
    "reporting_manager",
    "joining_date",
    "is_active",
]

HR_EMPLOYEE_EXPORT_FIELDS = PUBLIC_EMPLOYEE_EXPORT_FIELDS + [
    "country_code",
    "phone",
    "full_phone",
    "country_or_region",
    "date_of_birth",
    "gender",
]

PAYROLL_EMPLOYEE_EXPORT_FIELDS = HR_EMPLOYEE_EXPORT_FIELDS + [
    "personal_email",
]


def pii_key_configured() -> bool:
    return bool(settings.PII_ENCRYPTION_KEY.strip())


def _encryption_key() -> bytes:
    raw = settings.PII_ENCRYPTION_KEY.strip()
    if not raw:
        raise HTTPException(
            status_code=500,
            detail="PII encryption key is not configured on the server.",
        )
    try:
        decoded = base64.urlsafe_b64decode(raw)
        if len(decoded) in {16, 24, 32}:
            return hashlib.sha256(decoded).digest()
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_sensitive_value(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    key = _encryption_key()
    nonce = os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce, value.encode("utf-8"), None)
    payload = base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")
    return f"enc:v{settings.FIELD_ENCRYPTION_KEY_VERSION}:{payload}"


def decrypt_sensitive_value(value: str | None) -> str | None:
    if value is None or value == "" or not value.startswith("enc:v"):
        return value
    try:
        _, _version, payload = value.split(":", 2)
        raw = base64.urlsafe_b64decode(payload.encode("ascii"))
        nonce, encrypted = raw[:12], raw[12:]
        return AESGCM(_encryption_key()).decrypt(nonce, encrypted, None).decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to decrypt sensitive field.") from exc


def mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    local, domain = value.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(2, len(local) - len(visible))}@{domain}"


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"


def can_access_export_level(actor: Employee, level: str) -> bool:
    role = normalize_role(actor.role)
    if level == "basic":
        return role in {"super_admin", "admin", "hr_admin", "global_access", "manager"}
    if level == "hr":
        return role in {"super_admin", "admin", "hr_admin", "global_access"}
    if level == "payroll":
        return role in {"super_admin", "hr_admin", "global_access"}
    return False


def require_export_level(actor: Employee, level: str) -> None:
    if not can_access_export_level(actor, level):
        raise HTTPException(status_code=403, detail=f"You are not allowed to export {level} employee data.")


def log_sensitive_access(
    db: Session,
    actor: Employee | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    sensitivity_level: str = "restricted",
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(SensitiveAccessAuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        sensitivity_level=sensitivity_level,
        reason=reason,
        metadata_json=json.dumps(metadata or {}, default=str),
        performed_at=datetime.utcnow(),
    ))
    log_audit(
        db,
        actor,
        action=f"security.{action}",
        entity_type=target_type,
        entity_id=target_id,
        reason=reason,
        metadata={
            "sensitive": True,
            "sensitivity_level": sensitivity_level,
            **(metadata or {}),
        },
        source="api",
    )


def employee_code(index: int) -> str:
    return f"EMP-{index + 1:04d}"


def employee_export_row(emp: Employee, index: int, countries_for_dial_code: dict[str, str] | None = None) -> dict[str, Any]:
    country_code = emp.country_code or ""
    phone = emp.phone or ""
    return {
        "employee_code": employee_code(index),
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "work_email": emp.work_email,
        "personal_email": emp.personal_email,
        "country_code": country_code,
        "phone": phone,
        "full_phone": " ".join(part for part in [country_code.strip(), phone.strip()] if part),
        "country_or_region": (countries_for_dial_code or {}).get(country_code, ""),
        "date_of_birth": emp.date_of_birth.isoformat() if isinstance(emp.date_of_birth, date) else "",
        "gender": emp.gender or "",
        "department": emp.department,
        "designation": emp.designation or "",
        "role": emp.role,
        "workforce_type": emp.workforce_type,
        "employment_status": emp.employment_status,
        "work_location": emp.work_location,
        "work_city": emp.work_city or "",
        "work_state": emp.work_state or "",
        "work_country": emp.work_country or "",
        "reporting_manager": emp.reporting_manager,
        "joining_date": emp.joining_date.isoformat() if isinstance(emp.joining_date, date) else "",
        "is_active": "Yes" if emp.is_active else "No",
    }


def export_employee_csv(employees: list[Employee], level: str) -> str:
    fields = {
        "basic": PUBLIC_EMPLOYEE_EXPORT_FIELDS,
        "hr": HR_EMPLOYEE_EXPORT_FIELDS,
        "payroll": PAYROLL_EMPLOYEE_EXPORT_FIELDS,
    }[level]
    labels = {
        "employee_code": "Employee Code",
        "first_name": "First Name",
        "last_name": "Last Name",
        "work_email": "Work Email",
        "personal_email": "Personal Email",
        "country_code": "Country Code",
        "phone": "Phone",
        "full_phone": "Full Phone",
        "country_or_region": "Country / Region",
        "date_of_birth": "Date of Birth",
        "gender": "Gender",
        "department": "Department",
        "designation": "Designation",
        "role": "Role",
        "workforce_type": "Workforce Type",
        "employment_status": "Status",
        "work_location": "Work Arrangement",
        "work_city": "Work City",
        "work_state": "Work State / Province",
        "work_country": "Work Country",
        "reporting_manager": "Reporting Manager",
        "joining_date": "Joining Date",
        "is_active": "Active",
    }
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([labels[field] for field in fields])
    for index, emp in enumerate(employees):
        row = employee_export_row(emp, index)
        writer.writerow([row.get(field, "") for field in fields])
    return "\ufeff" + buffer.getvalue()
