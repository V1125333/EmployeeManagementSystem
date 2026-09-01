"""Signed access tokens and reusable server-derived authentication context."""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings, validate_security_settings
from app.core.database import get_db
from app.models.employee import Employee
from app.services.audit_service import log_audit
from app.core.authorization import normalize_role

logger = logging.getLogger(__name__)
_http_bearer = HTTPBearer(auto_error=False)
LEAVE_BALANCE_SELF_PERMISSION = "leave.balance.read.self"
LEAVE_REQUEST_SELF_PERMISSION = "leave.request.read.self"
LEAVE_ASSESS_SELF_PERMISSION = "leave.assess.self"
LEAVE_PREPARE_SELF_PERMISSION = "leave.request.prepare.self"
ATTENDANCE_SELF_PERMISSION = "attendance.read.self"
EMPLOYEE_MANAGER_SELF_PERMISSION = "employee.manager.read.self"
EMPLOYEE_DIRECTORY_READ_PERMISSION = "employee.directory.read"
TIMESHEET_SELF_PERMISSION = "timesheet.read.self"
PROJECT_ASSIGNMENTS_SELF_PERMISSION = "project.assignments.read.self"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    employee_id: str
    email: str
    role: str
    status: str
    permissions: frozenset[str]
    token_id: str
    access_level: str = "standard"
    manager_id: str | None = None
    department_id: str | None = None
    organization_scope: str = "reknew"

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


@dataclass(frozen=True)
class AuthenticatedActor:
    """Request-scoped principal plus the Employee loaded from the JWT subject."""

    principal: AuthenticatedPrincipal
    employee: Employee


def _jwt_secret() -> str:
    validate_security_settings()
    return settings.AUTH_JWT_SECRET.strip()


def create_access_token(employee: Employee, *, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(timezone.utc)
    payload = {
        "sub": employee.id,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.AUTH_ACCESS_TOKEN_MINUTES),
        "jti": secrets.token_urlsafe(18),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        _jwt_secret(),
        algorithms=["HS256"],
        audience=settings.AUTH_JWT_AUDIENCE,
        issuer=settings.AUTH_JWT_ISSUER,
        options={"require": ["sub", "iss", "aud", "iat", "exp", "jti"]},
    )


def _correlation_id(request: Request) -> str:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    return str(correlation_id)


def _deny_authentication(
    db: Session,
    request: Request,
    reason: str,
    *,
    actor: Employee | None = None,
) -> None:
    correlation_id = _correlation_id(request)
    logger.warning(
        "authentication_denied correlation_id=%s reason=%s",
        correlation_id,
        reason,
    )
    try:
        log_audit(
            db,
            actor,
            action="security.authentication.denied",
            entity_type="authenticated_request",
            reason=reason,
            metadata={"correlation_id": correlation_id, "error_category": "authentication"},
            source="security",
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist authentication denial audit.")
    raise HTTPException(
        status_code=401,
        detail={
            "code": "AUTHENTICATION_REQUIRED",
            "message": "Authentication is required.",
            "correlation_id": correlation_id,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def _deny_password_change_required(
    db: Session,
    request: Request,
    employee: Employee,
) -> None:
    correlation_id = _correlation_id(request)
    try:
        log_audit(
            db,
            employee,
            action="security.password_change_required",
            entity_type="authenticated_request",
            entity_id=employee.id,
            reason="The account requires a password change.",
            metadata={
                "correlation_id": correlation_id,
                "error_category": "account_state",
            },
            source="security",
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist password-change-required audit.")
    raise HTTPException(
        status_code=403,
        detail={
            "code": "PASSWORD_CHANGE_REQUIRED",
            "message": "A password change is required before continuing.",
            "correlation_id": correlation_id,
        },
    )


def _permissions_for_employee(_employee: Employee) -> frozenset[str]:
    """Preserve the current server-owned AI permission contract.

    Broader business permissions remain governed by existing route/service role
    and ownership rules until their later, explicitly approved migration tasks.
    """
    return frozenset(
        {
            LEAVE_BALANCE_SELF_PERMISSION,
            LEAVE_REQUEST_SELF_PERMISSION,
            LEAVE_ASSESS_SELF_PERMISSION,
            LEAVE_PREPARE_SELF_PERMISSION,
            ATTENDANCE_SELF_PERMISSION,
            EMPLOYEE_MANAGER_SELF_PERMISSION,
            EMPLOYEE_DIRECTORY_READ_PERMISSION,
            TIMESHEET_SELF_PERMISSION,
            PROJECT_ASSIGNMENTS_SELF_PERMISSION,
        }
    )


def _build_principal(employee: Employee, claims: dict) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role=normalize_role(employee.role),
        status=employee.employment_status,
        permissions=_permissions_for_employee(employee),
        token_id=str(claims["jti"]),
        access_level=(employee.access_level or "standard").strip().lower(),
        manager_id=employee.manager_id,
        department_id=employee.department_id,
        organization_scope=(
            settings.AUTH_ORGANIZATION_SCOPE.strip() or "reknew"
        ),
    )


def _resolve_authenticated_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
    *,
    allow_forced_password_change: bool,
) -> AuthenticatedActor:
    if not credentials or credentials.scheme.lower() != "bearer":
        _deny_authentication(db, request, "Missing bearer credential.")
    try:
        claims = decode_access_token(credentials.credentials)
    except (InvalidTokenError, RuntimeError):
        _deny_authentication(db, request, "Invalid or expired bearer credential.")

    employee = db.query(Employee).filter(Employee.id == claims["sub"]).first()
    if not employee:
        _deny_authentication(db, request, "Token subject was not found.")
    if (
        not employee.is_active
        or employee.employment_status != "active"
        or employee.account_locked
        or (employee.locked_until and employee.locked_until > datetime.utcnow())
    ):
        # Preserve the established AI endpoint's 401 response contract for
        # inactive and locked accounts during Task 1.
        _deny_authentication(
            db,
            request,
            "Token subject is not an active, unlocked employee.",
            actor=employee,
        )
    if employee.force_password_change and not allow_forced_password_change:
        _deny_password_change_required(db, request, employee)

    actor = AuthenticatedActor(
        principal=_build_principal(employee, claims),
        employee=employee,
    )
    request.state.authenticated_actor = actor
    return actor


def get_authenticated_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    db: Session = Depends(get_db),
) -> AuthenticatedActor:
    return _resolve_authenticated_actor(
        request,
        credentials,
        db,
        allow_forced_password_change=False,
    )


def get_authenticated_principal(
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> AuthenticatedPrincipal:
    return actor.principal


def get_authenticated_employee(
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> Employee:
    return actor.employee


def get_password_change_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    db: Session = Depends(get_db),
) -> AuthenticatedActor:
    """Authenticate an account that may be limited to changing its password.

    No existing route uses this dependency in Task 1. It is provided for the
    separately approved authentication-route migration and grants no broader
    authorization by itself.
    """
    return _resolve_authenticated_actor(
        request,
        credentials,
        db,
        allow_forced_password_change=True,
    )
