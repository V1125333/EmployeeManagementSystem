"""
Reusable centralized audit logging.

The audit service intentionally stores masked old/new values. Raw passwords,
tokens, OTPs, bank/tax identifiers, and other secrets should never reach this
table.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.employee import Employee
from app.services.settings_service import normalize_role

NEVER_LOG_FIELDS = {
    "password",
    "password_hash",
    "otp",
    "token",
    "access_token",
    "refresh_token",
    "reset_link",
    "session_id",
    "totp_secret",
    "mfa_secret",
    "setup_code",
}

SENSITIVE_VALUE_FIELDS = {
    "ssn",
    "aadhaar",
    "pan",
    "passport",
    "passport_number",
    "driver_license",
    "bank_account",
    "routing_number",
    "salary",
    "bonus",
    "medical",
    "tax",
}

ADDRESS_FIELDS = {"address", "current_address", "permanent_address", "home_address"}
DOB_FIELDS = {"date_of_birth", "dob"}
PHONE_FIELDS = {"phone", "contact_phone", "emergency_contact_phone"}
EMAIL_FIELDS = {"email", "work_email", "personal_email", "contact_email"}


def actor_name(actor: Employee | None) -> str | None:
    if not actor:
        return None
    return f"{actor.first_name} {actor.last_name}".strip() or actor.work_email


def audit_source(actor: Employee | None, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    role = normalize_role(actor.role if actor else None)
    if role in {"super_admin", "admin", "hr_admin", "global_access"}:
        return "admin"
    if actor:
        return "user"
    return "system"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _field_key(field_name: str) -> str:
    return field_name.lower().strip()


def _is_never_log(field_name: str) -> bool:
    key = _field_key(field_name)
    return any(token in key for token in NEVER_LOG_FIELDS)


def _is_sensitive_value(field_name: str) -> bool:
    key = _field_key(field_name)
    return any(token in key for token in SENSITIVE_VALUE_FIELDS)


def mask_phone(value: Any) -> Any:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return "[PHONE_CHANGED]"
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"


def mask_email(value: Any) -> Any:
    if not value:
        return value
    text = str(value)
    if "@" not in text:
        return "[EMAIL_CHANGED]"
    local, domain = text.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(2, len(local) - len(visible))}@{domain}"


def mask_dob(value: Any) -> Any:
    if value is None:
        return None
    text = _json_safe(value)
    text = str(text)
    if len(text) >= 10:
        return f"****-**-{text[-2:]}"
    return "[DOB_CHANGED]"


def mask_audit_value(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    key = _field_key(field_name)
    if _is_never_log(key):
        return "[REDACTED]"
    if _is_sensitive_value(key):
        return "[SENSITIVE_VALUE_CHANGED]"
    if key in ADDRESS_FIELDS or key.endswith("_address"):
        return "[ADDRESS_CHANGED]"
    if key in DOB_FIELDS:
        return mask_dob(value)
    if key in PHONE_FIELDS or key.endswith("_phone"):
        return mask_phone(value)
    if key in EMAIL_FIELDS or key.endswith("_email"):
        return mask_email(value)
    return _json_safe(value)


def sanitize_values(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if not values:
        return None
    sanitized: dict[str, Any] = {}
    for field, value in values.items():
        if _is_never_log(field):
            continue
        sanitized[field] = mask_audit_value(field, value)
    return sanitized


def changed_fields(old_values: dict[str, Any] | None, new_values: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    old_values = old_values or {}
    new_values = new_values or {}
    fields = sorted(set(old_values.keys()) | set(new_values.keys()))
    changes: dict[str, dict[str, Any]] = {}
    for field in fields:
        if _is_never_log(field):
            continue
        old_raw = _json_safe(old_values.get(field))
        new_raw = _json_safe(new_values.get(field))
        if old_raw == new_raw:
            continue
        changes[field] = {
            "old": mask_audit_value(field, old_raw),
            "new": mask_audit_value(field, new_raw),
        }
    return changes


def request_ip(request: Request | None) -> str | None:
    if not request:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def log_audit(
    db: Session,
    actor: Employee | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    changed_fields_payload: dict[str, Any] | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    changes = changed_fields_payload if changed_fields_payload is not None else changed_fields(old_values, new_values)
    row = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_name=actor_name(actor),
        actor_role=actor.role if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_values=sanitize_values(old_values),
        new_values=sanitize_values(new_values),
        changed_fields=_json_safe(changes) if changes else None,
        reason=reason,
        metadata_json=_json_safe(metadata or {}),
        source=audit_source(actor, source),
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent") if request else None,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    return row


def log_authorization_failure(
    db: Session,
    actor: Employee | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    reason: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    return log_audit(
        db=db,
        actor=actor,
        action=f"{action}.denied",
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason or "Authorization failed",
        metadata={"security_event": True},
        source="api",
        request=request,
    )
