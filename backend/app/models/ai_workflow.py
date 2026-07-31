"""Durable AI workflow state that is explicitly not an official HR record."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AILeaveRequestDraft(Base):
    __tablename__ = "ai_leave_request_drafts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    capability: Mapped[str] = mapped_column(
        String(40), nullable=False, default="leave_request"
    )
    leave_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_types.id"), nullable=False
    )
    leave_type_code: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    eligibility_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    working_day_count: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    balance_source: Mapped[str] = mapped_column(String(30), nullable=False)
    approver_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=True
    )
    blocking_reasons: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AILeaveIntakeState(Base):
    """Short-lived conversational slots; never an official HR record."""

    __tablename__ = "ai_leave_intake_states"
    __table_args__ = (
        UniqueConstraint(
            "owner_employee_id",
            "conversation_id",
            name="uq_ai_leave_intake_owner_conversation",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    goal: Mapped[str] = mapped_column(
        String(40), nullable=False, default="prepare_leave_request"
    )
    collected_fields: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
    missing_required_fields: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    optional_fields: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    source_confidence: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AIConversation(Base):
    """Principal-owned Orbit AI conversation metadata.

    Business facts are deliberately not stored here. Optional workflow
    references are re-authorized and refreshed from their canonical tables.
    """

    __tablename__ = "ai_conversations"
    __table_args__ = (
        Index(
            "ix_ai_conversations_owner_updated",
            "owner_employee_id",
            "updated_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(
        String(160), nullable=False, default="Orbit AI Conversation"
    )
    domain: Mapped[str] = mapped_column(String(40), nullable=False, default="leave")
    capability: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True
    )
    workflow_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    workflow_reference_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    workflow_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )


class AIConversationMessage(Base):
    """A bounded user/assistant transcript entry without credentials or secrets."""

    __tablename__ = "ai_conversation_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )


class AIContextualShadowEvaluation(Base):
    """Safe Phase A metadata; never a prompt, tool result, or workflow record."""

    __tablename__ = "ai_contextual_shadow_evaluations"
    __table_args__ = (
        Index(
            "ix_ai_shadow_owner_created",
            "actor_employee_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    actor_employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_conversations.id"), nullable=False, index=True
    )
    correlation_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    active_workflow_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="none"
    )
    deterministic_goal: Mapped[str] = mapped_column(String(60), nullable=False)
    deterministic_capability: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    deterministic_result_category: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    llm_domain: Mapped[str | None] = mapped_column(String(30), nullable=True)
    llm_goal: Mapped[str | None] = mapped_column(String(60), nullable=True)
    llm_workflow_action: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    proposed_capabilities: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    extracted_field_categories: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    ambiguity: Mapped[str | None] = mapped_column(String(8), nullable=True)
    comparison_outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    segment: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_validation_status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(240), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_http_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    provider_request_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    error_retryable: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
