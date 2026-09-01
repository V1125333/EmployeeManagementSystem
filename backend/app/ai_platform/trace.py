"""Bounded, in-memory trace contracts; no persistence or business payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field, field_validator, model_validator

from app.ai_platform.contracts import PlatformContract, require_timezone_aware


class TraceOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class TraceStage(str, Enum):
    REQUEST = "request"
    CAPABILITY_RESOLUTION = "capability_resolution"
    INTERPRETATION = "interpretation"
    CANDIDATE_PLAN = "candidate_plan"
    PLAN_VALIDATION = "plan_validation"
    PRELIMINARY_AUTHORIZATION = "preliminary_authorization"
    AUTHORIZATION = "authorization"
    FINAL_AUTHORIZATION = "final_authorization"
    CAPABILITY_EXECUTION = "capability_execution"
    RESULT_VALIDATION = "result_validation"
    CLAIM_EXTRACTION = "claim_extraction"
    GROUNDING_VALIDATION = "grounding_validation"
    COMPOSITION = "composition"
    REQUEST_COMPLETION = "request_completion"


class TraceEvent(PlatformContract):
    stage: TraceStage
    started_at: datetime
    completed_at: datetime
    latency_ms: int = Field(ge=0, le=3_600_000)
    outcome: TraceOutcome
    safe_error_category: str | None = Field(default=None, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    capability_id: str | None = Field(default=None, max_length=120, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    capability_version: int | None = Field(default=None, gt=0, le=999)
    provider_model: str | None = Field(default=None, max_length=120, pattern=r"^[A-Za-z0-9._:-]+$")
    input_tokens: int | None = Field(default=None, ge=0, le=10_000_000)
    output_tokens: int | None = Field(default=None, ge=0, le=10_000_000)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=6)
    result_reference_id: str | None = Field(
        default=None,
        min_length=20,
        max_length=80,
        pattern=r"^res_[A-Za-z0-9_-]{16,76}$",
    )

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware_times(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)

    @model_validator(mode="after")
    def valid_timing_and_outcome(self) -> "TraceEvent":
        if self.completed_at < self.started_at:
            raise ValueError("trace completion cannot precede start")
        actual_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        if abs(actual_ms - self.latency_ms) > 5:
            raise ValueError("trace latency does not match timestamps")
        if self.outcome is TraceOutcome.SUCCEEDED and self.safe_error_category:
            raise ValueError("successful trace events cannot contain an error category")
        if self.outcome in {TraceOutcome.FAILED, TraceOutcome.DENIED, TraceOutcome.TIMED_OUT} and not self.safe_error_category:
            raise ValueError("failed trace outcomes require a safe error category")
        if (self.capability_id is None) != (self.capability_version is None):
            raise ValueError("capability ID and version must be recorded together")
        return self


class AIRequestTrace(PlatformContract):
    request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    conversation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    actor_reference: str = Field(min_length=16, max_length=64, pattern=r"^[a-f0-9]+$")
    plan_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    events: tuple[TraceEvent, ...] = Field(default=(), max_length=32)
    final_outcome: TraceOutcome

    @model_validator(mode="after")
    def complete_hierarchy(self) -> "AIRequestTrace":
        if not self.events:
            raise ValueError("request traces require at least one event")
        if self.events[0].stage is not TraceStage.REQUEST:
            raise ValueError("request trace must begin with a request event")
        return self
