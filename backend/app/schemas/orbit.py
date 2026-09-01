from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrbitChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message cannot be blank.")
        return stripped


class OrbitChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    conversation_id: str
