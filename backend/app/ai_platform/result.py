"""Typed capability result and provenance contracts."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from app.ai_platform.contracts import DataClassification, PlatformContract, require_timezone_aware

OutputT = TypeVar("OutputT", bound=BaseModel)


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class ResultAvailability(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


class ResultValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class CapabilityResultReference(PlatformContract):
    result_reference_id: str = Field(
        min_length=20, max_length=80, pattern=r"^res_[A-Za-z0-9_-]{16,76}$"
    )
    capability_id: str = Field(min_length=5, max_length=120, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    capability_version: int = Field(gt=0, le=999)
    retrieved_at: datetime
    freshness: Freshness
    source_service: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.]+$")
    data_classification: DataClassification
    validation_status: ResultValidationStatus

    @field_validator("retrieved_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)

    @model_validator(mode="after")
    def valid_reference(self) -> "CapabilityResultReference":
        if self.validation_status is not ResultValidationStatus.VALID:
            raise ValueError("invalid results cannot receive a trusted result reference")
        return self


class ValidatedCapabilityResult(PlatformContract, Generic[OutputT]):
    reference: CapabilityResultReference
    availability: ResultAvailability
    output: OutputT | None = None
    permitted_field_paths: tuple[str, ...] = Field(default=(), max_length=64)
    validation_outcome: str = Field(default="valid", pattern=r"^valid$")
    safe_warnings: tuple[str, ...] = Field(default=(), max_length=8)

    @field_validator("permitted_field_paths")
    @classmethod
    def valid_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("permitted field paths must be unique")
        if any(not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*|\.\*)*", item) or len(item) > 120 for item in values):
            raise ValueError("invalid permitted field path")
        return values

    @field_validator("safe_warnings")
    @classmethod
    def bounded_warnings(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value or len(value) > 160 for value in values):
            raise ValueError("warnings must be bounded")
        return values

    @model_validator(mode="after")
    def output_matches_availability(self) -> "ValidatedCapabilityResult[OutputT]":
        if self.availability is ResultAvailability.AVAILABLE and self.output is None:
            raise ValueError("available results require typed output")
        if self.availability is not ResultAvailability.AVAILABLE and self.output is not None:
            raise ValueError("missing or unavailable results cannot carry output")
        return self
