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
from app.core.rbac import Permission, Scope, UserRole, canonical_role, grants_for_role, normalize_identifier, role_has_permission

if TYPE_CHECKING:
    from app.core.authentication import AuthenticatedPrincipal


logger = logging.getLogger(__name__)

ADMIN_ROLES = frozenset({UserRole.HR_ADMIN.value, UserRole.SYSTEM_ADMIN.value, UserRole.SUPER_ADMIN.value})
MANAGER_OR_ADMIN_ROLES = frozenset({*ADMIN_ROLES, UserRole.MANAGER.value})
AUDIT_VIEWER_ROLES = frozenset({UserRole.HR_ADMIN.value, UserRole.SYSTEM_ADMIN.value, UserRole.SUPER_ADMIN.value})


def normalize_role(role: str | None) -> str:
    """Normalize spelling only; normalization never grants an unknown role."""
    return normalize_identifier(role)


def normalized_roles(roles: Iterable[str]) -> frozenset[str]:
    return frozenset(normalize_role(role) for role in roles if normalize_role(role))


def has_any_role(
    principal: "AuthenticatedPrincipal",
    allowed_roles: Iterable[str],
) -> bool:
    try:
        return canonical_role(principal.role).value in normalized_roles(allowed_roles)
    except ValueError:
        return False


def employee_has_permission(employee: Employee, permission: str | Permission) -> bool:
    try:
        return role_has_permission(employee.role, permission)
    except ValueError:
        return False


def employee_has_scope(employee: Employee, permission: str | Permission, scope: str | Scope) -> bool:
    try:
        permission_value = Permission(permission) if not isinstance(permission, Permission) else permission
        scope_value = Scope(scope) if not isinstance(scope, Scope) else scope
        return scope_value in grants_for_role(employee.role).get(permission_value, frozenset())
    except ValueError:
        return False


def employee_can(employee: Employee, permission: str | Permission, scope: str | Scope | None = None) -> bool:
    if scope is None:
        return employee_has_permission(employee, permission)
    return employee_has_scope(employee, permission, scope)


def require_permission(
    principal: "AuthenticatedPrincipal",
    permission: str | Permission,
    *,
    scope: str | None = None,
    db: Session | None = None,
    request: Request | None = None,
    actor: Employee | None = None,
    entity_type: str = "protected_resource",
    entity_id: str | None = None,
) -> "AuthenticatedPrincipal":
    value = permission.value if isinstance(permission, Permission) else permission
    if principal.has_permission(value) and (scope is None or principal.has_scope(value, scope)):
        return principal
    deny_authorization(
        db=db, request=request, actor=actor, action=value,
        entity_type=entity_type, entity_id=entity_id,
        reason=f"Permission '{value}' with scope '{scope or 'any'}' is required.",
    )


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
