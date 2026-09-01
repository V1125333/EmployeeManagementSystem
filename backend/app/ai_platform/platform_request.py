"""Trusted internal request contract for the isolated Platform 1D flow."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.ai_platform.contracts import PlatformContract, require_timezone_aware
from app.ai_platform.execution import ExecutionPrincipal


class ConversationContextItem(PlatformContract):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=500)


class PlatformRequest(PlatformContract):
    request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    correlation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    conversation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    principal: ExecutionPrincipal
    message: str = Field(min_length=1, max_length=2_000)
    locale: str = Field(default="en-US", min_length=2, max_length=20, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    timezone: str = Field(default="UTC", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_+./:-]+$")
    received_at: datetime
    deadline_at: datetime
    conversation_context: tuple[ConversationContextItem, ...] = Field(default=(), max_length=6)

    @field_validator("received_at", "deadline_at")
    @classmethod
    def aware_times(cls, value: datetime) -> datetime:
        return require_timezone_aware(value)

    @model_validator(mode="after")
    def trusted_and_bounded(self) -> "PlatformRequest":
        if not self.principal.is_application_trusted:
            raise ValueError("Platform requests require a server-authenticated principal")
        if self.deadline_at <= self.received_at:
            raise ValueError("deadline must follow request receipt")
        if (self.deadline_at - self.received_at).total_seconds() > 30:
            raise ValueError("Platform request deadline cannot exceed thirty seconds")
        return self
