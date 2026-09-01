"""Serializable execution metadata; runtime resources remain out of contract."""

from __future__ import annotations

from datetime import datetime

from typing import Protocol

from pydantic import Field, PrivateAttr, ValidationInfo, field_validator, model_validator

from app.ai_platform.contracts import PlatformContract, TraceMetadataItem, require_timezone_aware

_PRINCIPAL_CONTEXT = object()


class AuthenticatedPrincipalLike(Protocol):
    employee_id: str
    email: str
    role: str
    status: str
    permissions: frozenset[str]
    token_id: str
    organization_scope: str


class ExecutionPrincipal(PlatformContract):
    """Minimal runtime identity snapshot created only from server authentication."""

    employee_id: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(min_length=1, max_length=50)
    status: str = Field(min_length=1, max_length=30)
    permissions: frozenset[str] = Field(max_length=128)
    token_id: str = Field(min_length=8, max_length=120)
    organization_scope: str = Field(min_length=1, max_length=80)
    _application_trusted: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def trusted_source(self, info: ValidationInfo) -> "ExecutionPrincipal":
        context_trusted = bool(
            info.context
            and info.context.get("authenticated_principal") is _PRINCIPAL_CONTEXT
        )
        if not context_trusted and not self._application_trusted:
            raise ValueError("execution principal must come from server authentication")
        return self

    @classmethod
    def from_authenticated(cls, principal: AuthenticatedPrincipalLike) -> "ExecutionPrincipal":
        snapshot = cls.model_validate({
            "employee_id": principal.employee_id,
            "email": principal.email,
            "role": principal.role,
            "status": principal.status,
            "permissions": principal.permissions,
            "token_id": principal.token_id,
            "organization_scope": principal.organization_scope,
        }, context={"authenticated_principal": _PRINCIPAL_CONTEXT})
        object.__setattr__(snapshot, "_application_trusted", True)
        return snapshot

    def has_permission(self, permission: str) -> bool:
        """Mirror the server principal's permission check without adding identity input."""
        return permission in self.permissions

    @property
    def is_application_trusted(self) -> bool:
        return self._application_trusted


class CapabilityExecutionContext(PlatformContract):
    """Trusted request metadata passed to an executor.

    A SQLAlchemy Session is supplied as a separate runtime-only executor
    argument. It is deliberately absent here so it cannot be serialized,
    traced, or exposed to an interpreter or model.
    """

    principal: ExecutionPrincipal
    request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    correlation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    conversation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    plan_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    step_id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    deadline_at: datetime
    feature_flags: tuple[TraceMetadataItem, ...] = Field(default=(), max_length=16)

    @field_validator("deadline_at")
    @classmethod
    def aware_deadline(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)
