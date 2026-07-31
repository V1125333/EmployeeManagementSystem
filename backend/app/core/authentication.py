"""Signed access tokens and the trusted principal used by secure AI routes."""

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
from app.services.settings_service import normalize_role

logger = logging.getLogger(__name__)
_http_bearer = HTTPBearer(auto_error=False)
LEAVE_BALANCE_SELF_PERMISSION = "leave.balance.read.self"
LEAVE_REQUEST_SELF_PERMISSION = "leave.request.read.self"
LEAVE_ASSESS_SELF_PERMISSION = "leave.assess.self"
LEAVE_PREPARE_SELF_PERMISSION = "leave.request.prepare.self"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    employee_id: str
    email: str
    role: str
    status: str
    permissions: frozenset[str]
    token_id: str

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


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


def _deny(
    db: Session,
    request: Request,
    reason: str,
    *,
    actor: Employee | None = None,
) -> None:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    logger.warning("orbit_ai_auth_denied correlation_id=%s reason=%s", correlation_id, reason)
    try:
        log_audit(
            db,
            actor,
            action="ai.chat.denied",
            entity_type="ai_chat",
            reason=reason,
            metadata={"correlation_id": correlation_id, "error_category": "authentication"},
            source="ai",
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist AI authentication denial audit.")
    raise HTTPException(
        status_code=401,
        detail={
            "code": "AUTHENTICATION_REQUIRED",
            "message": "Authentication is required.",
            "correlation_id": correlation_id,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_authenticated_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    db: Session = Depends(get_db),
) -> AuthenticatedPrincipal:
    if not credentials or credentials.scheme.lower() != "bearer":
        _deny(db, request, "Missing bearer credential.")
    try:
        claims = decode_access_token(credentials.credentials)
    except (InvalidTokenError, RuntimeError):
        _deny(db, request, "Invalid or expired bearer credential.")

    employee = db.query(Employee).filter(Employee.id == claims["sub"]).first()
    if not employee:
        _deny(db, request, "Token subject was not found.")
    if (
        not employee.is_active
        or employee.employment_status != "active"
        or employee.account_locked
        or (employee.locked_until and employee.locked_until > datetime.utcnow())
    ):
        _deny(db, request, "Token subject is not an active, unlocked employee.", actor=employee)

    return AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role=normalize_role(employee.role),
        status=employee.employment_status,
        permissions=frozenset(
            {
                LEAVE_BALANCE_SELF_PERMISSION,
                LEAVE_REQUEST_SELF_PERMISSION,
                LEAVE_ASSESS_SELF_PERMISSION,
                LEAVE_PREPARE_SELF_PERMISSION,
            }
        ),
        token_id=str(claims["jti"]),
    )
