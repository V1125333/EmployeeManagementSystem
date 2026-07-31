"""Strict, non-executable contracts for contextual LLM shadow interpretation."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Domain = Literal["leave", "general", "unknown"]
Goal = Literal[
    "prepare_leave_request",
    "review_leave_draft",
    "discard_leave_draft",
    "submit_leave_request",
    "check_leave_balance",
    "compare_leave_balance",
    "list_leave_requests",
    "check_leave_request_status",
    "explain_leave_decision",
    "check_leave_eligibility",
    "unknown",
]
WorkflowAction = Literal[
    "start",
    "continue",
    "modify",
    "cancel",
    "pause",
    "switch_goal",
    "resume",
    "new_goal",
    "clarify",
    "none",
]
ResponseIntent = Literal[
    "ask_clarification",
    "acknowledge_update",
    "show_result",
    "show_review",
    "request_confirmation",
    "decline_unsupported",
]
CapabilityId = Literal[
    "start_leave_intake",
    "continue_leave_intake",
    "update_leave_intake_dates",
    "update_leave_intake_type",
    "resume_leave_intake",
    "request_leave_submission",
    "leave.balance.read_self",
    "leave.balance.compare_self",
    "leave.requests.list_self",
    "leave.request.status_self",
    "leave.request.details_self",
    "leave.request.decision_explain_self",
    "leave.eligibility.check_self",
    "leave.draft.prepare_self",
    "leave.draft.read_self",
    "leave.draft.update_self",
    "leave.draft.discard_self",
    # Observation only in Phase A; never executable.
    "leave.request.submit_confirmed_self",
]

_UNSAFE_TEXT = re.compile(
    r"(?:https?://|/api/|\b(?:select|insert|update|delete|drop|alter)\b"
    r".*\b(?:from|into|table|where)\b|\b(?:employee|manager|approver|user)"
    r"[_ -]?id\b|\bpermissions?\b|\btool[_ -]?name\b)",
    re.IGNORECASE,
)


def _reject_unsafe_text(value: str | None) -> str | None:
    if value and _UNSAFE_TEXT.search(value):
        raise ValueError("Unsafe structured interpretation content.")
    return value


class ExtractedLeaveFields(StrictContextModel):
    leave_type: str | None = Field(default=None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    start_date_expression: str | None = Field(default=None, max_length=80)
    end_date_expression: str | None = Field(default=None, max_length=80)
    date_expression: str | None = Field(default=None, max_length=80)
    preserve_existing_dates: bool | None = None
    duration_days: int | None = Field(default=None, ge=1, le=31)
    reason: str | None = Field(default=None, max_length=200)
    reason_skipped: bool | None = None
    status_filters: list[
        Literal[
            "draft",
            "submitted",
            "pending",
            "approved",
            "rejected",
            "cancelled",
            "withdrawn",
            "expired",
        ]
    ] = Field(default_factory=list, max_length=8)
    latest: bool = False
    history: bool = False
    threshold: float | None = Field(default=None, ge=0, le=1000)
    request_reference: Literal[
        "active_workflow",
        "latest_owned_request",
        "previous_result",
        "unspecified",
    ] | None = None

    @model_validator(mode="after")
    def validate_text(self):
        _reject_unsafe_text(self.leave_type)
        _reject_unsafe_text(self.reason)
        _reject_unsafe_text(self.start_date_expression)
        _reject_unsafe_text(self.end_date_expression)
        _reject_unsafe_text(self.date_expression)
        return self


class FieldConfidence(StrictContextModel):
    field: Literal[
        "leave_type",
        "start_date",
        "end_date",
        "start_date_expression",
        "end_date_expression",
        "date_expression",
        "preserve_existing_dates",
        "duration_days",
        "reason",
        "reason_skipped",
        "status_filter",
        "date_scope",
        "threshold",
        "request_reference",
    ]
    confidence: Literal["high", "medium", "low"]
    source: Literal[
        "explicit",
        "date_phrase",
        "leave_alias",
        "active_workflow",
        "recent_conversation",
        "inferred",
    ]
    inferred: bool = False


class InterpretationAmbiguity(StrictContextModel):
    is_ambiguous: bool
    fields: list[
        Literal[
            "goal",
            "leave_type",
            "date_range",
            "reason",
            "request_reference",
            "workflow_action",
        ]
    ] = Field(default_factory=list, max_length=6)
    safe_options: list[str] = Field(default_factory=list, max_length=5)
    explanation: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def validate_text(self):
        _reject_unsafe_text(self.explanation)
        for option in self.safe_options:
            _reject_unsafe_text(option)
        return self


class ClarificationRequirement(StrictContextModel):
    required: bool
    field: Literal[
        "goal",
        "leave_type",
        "date_range",
        "reason",
        "request_reference",
        "workflow_action",
    ] | None = None
    question: str | None = Field(default=None, max_length=240)
    missing_fields: list[
        Literal[
            "leave_type",
            "date_range",
            "specific_date_range",
            "reason",
            "supporting_information",
            "request_reference",
            "workflow_action",
        ]
    ] = Field(default_factory=list, max_length=7)
    question_intent: Literal[
        "ask_for_dates",
        "ask_for_leave_type",
        "ask_for_reason",
        "clarify_next_week_scope",
        "resume_and_collect_missing_information",
        "clarify_request_reference",
        "clarify_workflow_action",
    ] | None = None

    @model_validator(mode="after")
    def validate_text(self):
        _reject_unsafe_text(self.question)
        if self.required and not self.question:
            raise ValueError("A clarification question is required.")
        return self


class ConfirmationRequirement(StrictContextModel):
    required: bool
    reason: Literal[
        "none",
        "business_write",
        "external_side_effect",
        "ambiguous_scope",
    ] = "none"


class ContextualInterpretation(StrictContextModel):
    schema_version: Literal["1.0"] = "1.0"
    domain: Domain
    goal: Goal
    workflow_action: WorkflowAction
    extracted_fields: ExtractedLeaveFields = Field(
        default_factory=ExtractedLeaveFields
    )
    field_confidence: list[FieldConfidence] = Field(
        default_factory=list, max_length=12
    )
    ambiguity: InterpretationAmbiguity
    clarification_requirement: ClarificationRequirement
    proposed_capabilities: list[CapabilityId] = Field(
        default_factory=list, max_length=3
    )
    confirmation_requirement: ConfirmationRequirement
    response_intent: ResponseIntent


class ContextMessage(StrictContextModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class SafeCollectedFields(StrictContextModel):
    leave_type: str | None = Field(default=None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1, le=31)
    reason_present: bool = False
    reason_skipped: bool = False
    supporting_information_present: bool = False


class ActiveWorkflowContext(StrictContextModel):
    workflow_type: Literal["none", "leave_intake", "leave_draft", "confirmation"]
    stage: str = Field(max_length=40)
    collected_fields: SafeCollectedFields | None = None
    missing_fields: list[str] = Field(default_factory=list, max_length=8)
    optional_fields: list[str] = Field(default_factory=list, max_length=8)
    version: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None


class CapabilityDescription(StrictContextModel):
    capability_id: CapabilityId
    description: str = Field(max_length=160)
    risk: Literal["read", "prepare", "confirmation_only"]


class ContextPackage(StrictContextModel):
    prompt_version: str = Field(max_length=40)
    active_workflow: ActiveWorkflowContext
    recent_messages: list[ContextMessage] = Field(max_length=8)
    trusted_date: date
    timezone: str = Field(max_length=64)
    approved_capabilities: list[CapabilityDescription] = Field(max_length=24)


class ContextualFewShotExample(StrictContextModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$", max_length=60)
    active_workflow: ActiveWorkflowContext
    user_message: str = Field(min_length=1, max_length=300)
    expected_interpretation: ContextualInterpretation


class ContextualPromptTemplate(StrictContextModel):
    version: str = Field(pattern=r"^[a-z0-9_-]+$", max_length=60)
    examples: list[ContextualFewShotExample] = Field(min_length=6, max_length=10)


class LLMProviderRequest(StrictContextModel):
    system_prompt: str = Field(min_length=1, max_length=12000)
    current_message: str = Field(min_length=1, max_length=1000)
    context: ContextPackage
    max_input_tokens: int = Field(ge=256, le=16000)
    max_output_tokens: int = Field(ge=128, le=4000)
    temperature: float = Field(ge=0, le=2)


class TokenUsage(StrictContextModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class LLMProviderResponse(StrictContextModel):
    interpretation: ContextualInterpretation
    provider: str = Field(max_length=40)
    model: str = Field(max_length=120)
    latency_ms: int = Field(ge=0)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    request_id: str | None = Field(default=None, max_length=120)


class DeterministicObservation(StrictContextModel):
    response_status: str = Field(max_length=32)
    result_type: str | None = Field(default=None, max_length=64)
    goal: Goal
    capability_id: CapabilityId | None = None
    continued_active_workflow: bool = False
    extracted_field_categories: list[str] = Field(default_factory=list, max_length=12)


class ShadowEvaluationSummary(StrictContextModel):
    comparison_outcome: Literal[
        "exact_agreement",
        "compatible_agreement",
        "llm_identifies_workflow_continuation",
        "deterministic_identifies_workflow_continuation",
        "routing_disagreement",
        "extraction_disagreement",
        "unsafe_llm_proposal",
        "invalid_structured_output",
        "timeout",
        "provider_failure",
    ]
    segment: Literal[
        "standalone",
        "active_workflow_follow_up",
        "topic_switch",
        "security_adversarial",
    ]
    schema_validation_status: Literal["valid", "invalid", "not_run"]
    extracted_field_categories: list[str] = Field(default_factory=list)


class ShadowDiagnosticItem(StrictContextModel):
    id: str
    conversation_id: str
    correlation_id: str
    active_workflow_type: str
    deterministic_goal: str
    deterministic_capability: str | None
    llm_domain: str | None
    llm_goal: str | None
    llm_workflow_action: str | None
    proposed_capabilities: list[str]
    extracted_field_categories: list[str]
    ambiguity: bool | None
    comparison_outcome: str
    segment: str
    schema_validation_status: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    error_category: str | None
    error_message: str | None
    error_code: str | None
    error_http_status: int | None
    provider_request_id: str | None
    error_retryable: bool | None
    prompt_version: str
    created_at: datetime


class ShadowDiagnosticsResponse(StrictContextModel):
    evaluations: list[ShadowDiagnosticItem]
    metrics: dict[str, float | int | dict[str, dict[str, float | int]]]


class ContextualProviderStatusResponse(StrictContextModel):
    enabled: bool
    shadow_mode: bool
    provider: str
    model: str
    credential_configured: bool
    configuration_valid: bool
    configuration_errors: list[str]
    prompt_version: str
    prompt_examples: int
    recent_evaluations: int
    last_outcome: str | None = None
    last_error_category: str | None = None
    last_error_message: str | None = None
    last_error_code: str | None = None
    last_error_http_status: int | None = None
    last_provider_request_id: str | None = None
    last_error_retryable: bool | None = None
    can_affect_production: Literal[False] = False
