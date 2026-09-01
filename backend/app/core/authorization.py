"""Small authorization primitives shared by authenticated API boundaries.

This module intentionally does not replace domain-specific authorization.
Routes and services must continue to enforce their existing owner, manager,
project, workflow, and role rules.  These helpers only provide normalized role
comparisons and a sanitized denial path for later Foundation Phase 0 tasks.
"""

from __future__ import annotations

import uuid
import logging
import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, NoReturn

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models.employee import Employee

if TYPE_CHECKING:
    from app.core.authentication import AuthenticatedPrincipal


logger = logging.getLogger(__name__)

ADMIN_ROLES = frozenset(
    {"super_admin", "admin", "hr_admin", "global_access"}
)
MANAGER_OR_ADMIN_ROLES = frozenset({*ADMIN_ROLES, "manager"})
AUDIT_VIEWER_ROLES = frozenset({"super_admin", "hr_admin", "global_access"})


def normalize_role(role: str | None) -> str:
    """Normalize spelling only; normalization never grants an unknown role."""
    return (role or "").strip().lower().replace(" ", "_").replace("-", "_")


def normalized_roles(roles: Iterable[str]) -> frozenset[str]:
    return frozenset(normalize_role(role) for role in roles if normalize_role(role))


def has_any_role(
    principal: "AuthenticatedPrincipal",
    allowed_roles: Iterable[str],
) -> bool:
    return normalize_role(principal.role) in normalized_roles(allowed_roles)


def is_self_or_authorized_role(
    principal: "AuthenticatedPrincipal",
    target_employee_id: str,
    authorized_roles: Iterable[str],
) -> bool:
    return (
        principal.employee_id == target_employee_id
        or has_any_role(principal, authorized_roles)
    )


def _correlation_id(request: Request | None) -> str:
    if request is not None:
        existing = getattr(request.state, "correlation_id", None)
        if existing:
            return str(existing)
    value = str(uuid.uuid4())
    if request is not None:
        request.state.correlation_id = value
    return value


def _safe_denial_reason(reason: str) -> str:
    """Bound and redact a reason in case a future caller passes request text."""
    value = str(reason or "Authorization failed.")[:500]
    value = re.sub(r"(?i)\bbearer\s+\S+", "Bearer [REDACTED]", value)
    value = re.sub(
        r"(?i)\b(x-user-id|x-user-email|x-user-name)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        value,
    )
    return value


def deny_authorization(
    *,
    db: Session | None,
    request: Request | None,
    actor: Employee | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    reason: str = "The authenticated actor is not authorized for this operation.",
) -> NoReturn:
    """Persist a bounded denial event without inspecting credentials or headers."""
    correlation_id = _correlation_id(request)
    safe_reason = _safe_denial_reason(reason)
    if db is not None:
        try:
            # Local import avoids coupling the audit service back to this module.
            from app.services.audit_service import log_authorization_failure

            log_authorization_failure(
                db,
                actor,
                action,
                entity_type,
                entity_id=entity_id,
                reason=safe_reason,
                request=request,
                correlation_id=correlation_id,
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Could not persist authorization denial correlation_id=%s",
                correlation_id,
            )
    raise HTTPException(
        status_code=403,
        detail={
            "code": "AUTHORIZATION_DENIED",
            "message": "You are not authorized to perform this operation.",
            "correlation_id": correlation_id,
        },
    )


def require_roles(
    principal: "AuthenticatedPrincipal",
    *allowed_roles: str,
    db: Session | None = None,
    request: Request | None = None,
    actor: Employee | None = None,
    action: str = "security.authorization",
    entity_type: str = "protected_resource",
    entity_id: str | None = None,
    reason: str = "The authenticated role is not authorized for this operation.",
) -> "AuthenticatedPrincipal":
    if has_any_role(principal, allowed_roles):
        return principal
    deny_authorization(
        db=db,
        request=request,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
    )


def require_self_or_roles(
    principal: "AuthenticatedPrincipal",
    target_employee_id: str,
    *authorized_roles: str,
    db: Session | None = None,
    request: Request | None = None,
    actor: Employee | None = None,
    action: str = "security.authorization",
    entity_type: str = "employee",
    reason: str = "Cross-employee access is not authorized.",
) -> "AuthenticatedPrincipal":
    if is_self_or_authorized_role(
        principal,
        target_employee_id,
        authorized_roles,
    ):
        return principal
    deny_authorization(
        db=db,
        request=request,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=target_employee_id,
        reason=reason,
    )
