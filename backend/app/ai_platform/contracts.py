"""Shared strict and serializable Platform 1A contract primitives."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
SAFE_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

BoundedString = Annotated[str, Field(min_length=1, max_length=240)]
ShortIdentifier = Annotated[
    str, Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
]


class PlatformContract(BaseModel):
    """Base for externally representable contracts; unknown fields fail closed."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        use_enum_values=False,
        validate_default=True,
    )


class OperationClass(str, Enum):
    READ = "read"
    PREPARE = "prepare"
    WRITE = "write"


class RiskClass(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class Availability(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    SHADOW_ONLY = "shadow_only"


class ActorScope(str, Enum):
    SELF = "self"
    MANAGER = "manager"
    PROJECT = "project"
    WORKFLOW = "workflow"
    ADMINISTRATIVE = "administrative"


class DataClassification(str, Enum):
    """PUBLIC is unrestricted; INTERNAL is workforce-only.

    CONFIDENTIAL covers ordinary employee/business records. RESTRICTED covers
    highly sensitive records requiring narrow policy and trace handling.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class RetryPolicy(str, Enum):
    NONE = "none"
    BOUNDED_READ = "bounded_read"


class ConfirmationRequirement(str, Enum):
    NONE = "none"
    EXPLICIT = "explicit_confirmation"
    ADDITIONAL_APPROVAL = "additional_approval"


class IdempotencyPolicy(str, Enum):
    NONE = "none"
    EXPLICIT_KEY = "explicit_key"


class AuditPolicy(str, Enum):
    STANDARD = "standard"
    SENSITIVE = "sensitive"


class FailurePolicy(str, Enum):
    STOP = "stop"
    CONTINUE_INDEPENDENT = "continue_independent"


class PlanSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_SHADOW = "llm_shadow"
    TEST = "test"


class PlanSafetyFlag(str, Enum):
    PROMPT_CAPABILITY_OVERRIDE = "prompt_capability_override"
    PROMPT_IDENTITY_OVERRIDE = "prompt_identity_override"
    PROMPT_EXECUTION_OVERRIDE = "prompt_execution_override"
    UNSAFE_INSTRUCTION = "unsafe_instruction"


class TraceMetadataItem(PlatformContract):
    key: ShortIdentifier
    value: Annotated[str, Field(min_length=1, max_length=120)]


def require_timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


class TimeBoundContract(PlatformContract):
    """Reusable validation helper for contracts containing a single timestamp."""

    occurred_at: datetime

    _aware = field_validator("occurred_at")(require_timezone_aware)
