"""Immutable application-produced authorization decisions."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum

from pydantic import Field, PrivateAttr, ValidationInfo, field_validator, model_validator

from app.ai_platform.contracts import ActorScope, PlatformContract, require_timezone_aware

_AUTHORIZATION_CONTEXT = object()


class AuthorizationState(str, Enum):
    PENDING = "pending"
    ALLOWED = "allowed"
    DENIED = "denied"


class AuthorizationDecision(PlatformContract):
    """Trusted only when created by application authorization factories."""

    allowed: bool
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    evaluated_scope: ActorScope
    policy_version: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9._-]+$")
    target_reference_hash: str | None = Field(
        default=None, min_length=16, max_length=64, pattern=r"^[a-f0-9]+$"
    )
    evaluated_at: datetime
    _application_trusted: bool = PrivateAttr(default=False)

    @field_validator("evaluated_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)

    @model_validator(mode="after")
    def trusted_construction(self, info: ValidationInfo) -> "AuthorizationDecision":
        context_trusted = bool(
            info.context
            and info.context.get("authorization_factory") is _AUTHORIZATION_CONTEXT
        )
        if not context_trusted and not self._application_trusted:
            raise ValueError("authorization decisions must be created by application authorization code")
        return self

    @classmethod
    def allow(
        cls, *, reason_code: str, evaluated_scope: ActorScope,
        policy_version: str, evaluated_at: datetime,
        target_reference_hash: str | None = None,
    ) -> "AuthorizationDecision":
        decision = cls.model_validate({
            "allowed": True, "reason_code": reason_code,
            "evaluated_scope": evaluated_scope, "policy_version": policy_version,
            "target_reference_hash": target_reference_hash, "evaluated_at": evaluated_at,
        }, context={"authorization_factory": _AUTHORIZATION_CONTEXT})
        object.__setattr__(decision, "_application_trusted", True)
        return decision

    @classmethod
    def deny(
        cls, *, reason_code: str, evaluated_scope: ActorScope,
        policy_version: str, evaluated_at: datetime,
        target_reference_hash: str | None = None,
    ) -> "AuthorizationDecision":
        decision = cls.model_validate({
            "allowed": False, "reason_code": reason_code,
            "evaluated_scope": evaluated_scope, "policy_version": policy_version,
            "target_reference_hash": target_reference_hash, "evaluated_at": evaluated_at,
        }, context={"authorization_factory": _AUTHORIZATION_CONTEXT})
        object.__setattr__(decision, "_application_trusted", True)
        return decision


def minimize_target_reference(raw_reference: str, *, salt: str) -> str:
    """Return a one-way trace reference; raw resource IDs never enter decisions."""
    import hashlib

    if not salt or len(salt) < 8:
        raise ValueError("an application-owned salt is required")
    return hashlib.sha256(f"{salt}:{raw_reference}".encode("utf-8")).hexdigest()[:32]
