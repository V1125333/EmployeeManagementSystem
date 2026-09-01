"""Effective MFA policy evaluation shared by authentication and settings."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.settings import OrganizationSecurityPolicy, UserSettings


POLICY_ID = "organization"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_security_policy(db: Session) -> OrganizationSecurityPolicy | None:
    return db.query(OrganizationSecurityPolicy).filter(
        OrganizationSecurityPolicy.id == POLICY_ID,
    ).first()


def get_or_create_security_policy(db: Session, actor_id: str | None = None) -> OrganizationSecurityPolicy:
    policy = get_security_policy(db)
    if policy:
        return policy
    policy = OrganizationSecurityPolicy(
        id=POLICY_ID,
        mfa_enabled=True,
        allow_user_mfa_opt_out=True,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(policy)
    db.flush()
    return policy


def policy_values(db: Session) -> tuple[bool, bool]:
    policy = get_security_policy(db)
    if not policy:
        return True, True
    return bool(policy.mfa_enabled), bool(policy.allow_user_mfa_opt_out)


def user_mfa_preference(db: Session, employee_id: str) -> bool:
    row = db.query(UserSettings.mfa_enabled).filter(UserSettings.user_id == employee_id).first()
    return True if row is None else bool(row[0])


def is_mfa_required(db: Session, employee: Employee) -> bool:
    if not employee.totp_secret:
        return False
    globally_enabled, opt_out_allowed = policy_values(db)
    if not globally_enabled:
        return False
    return True if not opt_out_allowed else user_mfa_preference(db, employee.id)


def update_user_mfa_preference(db: Session, employee: Employee, enabled: bool) -> UserSettings:
    globally_enabled, opt_out_allowed = policy_values(db)
    if not enabled and globally_enabled and not opt_out_allowed:
        raise HTTPException(status_code=403, detail="Your organization requires multi-factor authentication.")
    row = db.query(UserSettings).filter(UserSettings.user_id == employee.id).first()
    if not row:
        row = UserSettings(user_id=employee.id, created_by=employee.id, updated_by=employee.id)
        db.add(row)
    row.mfa_enabled = enabled
    row.updated_at = utc_now()
    row.updated_by = employee.id
    employee.mfa_enabled = enabled and bool(employee.totp_secret)
    return row


def update_organization_security_policy(
    db: Session,
    actor: Employee,
    *,
    mfa_enabled: bool,
    allow_user_mfa_opt_out: bool,
) -> OrganizationSecurityPolicy:
    policy = get_or_create_security_policy(db, actor.id)
    policy.mfa_enabled = mfa_enabled
    policy.allow_user_mfa_opt_out = allow_user_mfa_opt_out
    policy.updated_at = utc_now()
    policy.updated_by = actor.id
    return policy
