"""Strict contracts for the read-only Orbit AI leave agent."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


LeaveIntent = Literal[
    "balance",
    "balance_comparison",
    "request_list",
    "request_status",
    "request_details",
    "decision_explanation",
    "eligibility",
    "working_days",
    "holiday_overlap",
    "request_overlap",
    "draft_prepare",
    "draft_get",
    "draft_update",
    "draft_discard",
    "draft_continue",
    "submission_request",
    "unsupported",
]
LeaveStatus = Literal[
    "draft",
    "submitted",
    "pending",
    "approved",
    "rejected",
    "cancelled",
    "withdrawn",
    "expired",
]


class LeaveGoal(StrictAIModel):
    intent: LeaveIntent
    leave_type: str | None = Field(default=None, max_length=50)
    statuses: list[LeaveStatus] = Field(default_factory=list, max_length=8)
    on_date: date | None = None
    latest: bool = False
    history: bool = False
    threshold: float | None = Field(default=None, ge=0, le=1000)
    comparison: Literal["at_least", "highest"] | None = None
    trusted_request_id: str | None = Field(default=None, max_length=36)
    start_date: date | None = None
    end_date: date | None = None
    eligibility_follow_up: Literal[
        "same", "extend_one_day", "move_next_week"
    ] | None = None
    draft_update: Literal[
        "change_leave_type",
        "change_dates",
        "extend_one_day",
        "move_next_week",
        "set_reason",
        "remove_reason",
    ] | None = None
    reason: str | None = Field(default=None, max_length=200)
    confidence: Literal["high", "medium", "low"] = "high"


class GetMyLeaveBalanceInput(StrictAIModel):
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)


class CompareMyLeaveBalanceInput(StrictAIModel):
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)
    comparison: Literal["at_least", "highest"]
    threshold: float | None = Field(default=None, ge=0, le=1000)


BalanceValue = float | Literal["On request"]
BalanceSource = Literal["stored_balance", "policy_default", "on_request"]


class LeaveBalanceToolItem(StrictAIModel):
    leave_type: str
    code: str
    total: float
    available: BalanceValue
    used: float
    pending: float
    source: BalanceSource


class GetMyLeaveBalanceOutput(StrictAIModel):
    tool: Literal["get_my_leave_balance"] = "get_my_leave_balance"
    as_of: datetime
    year: int
    balances: list[LeaveBalanceToolItem]


class CompareMyLeaveBalanceOutput(StrictAIModel):
    tool: Literal["compare_my_leave_balance"] = "compare_my_leave_balance"
    as_of: datetime
    comparison: Literal["at_least", "highest"]
    balances: list[LeaveBalanceToolItem]
    threshold: float | None = None
    meets_threshold: bool | None = None
    highest: LeaveBalanceToolItem | None = None


class GetMyRecentLeaveRequestsInput(StrictAIModel):
    statuses: list[LeaveStatus] = Field(default_factory=list, max_length=8)
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)
    on_date: date | None = None
    limit: int = Field(default=12, ge=1, le=25)


class GetMyLeaveRequestStatusInput(StrictAIModel):
    request_id: str | None = Field(default=None, min_length=1, max_length=36)
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)
    on_date: date | None = None
    status: LeaveStatus | None = None
    latest: bool = False


class GetMyLeaveRequestDetailsInput(GetMyLeaveRequestStatusInput):
    pass


class ExplainMyLeaveDecisionInput(GetMyLeaveRequestStatusInput):
    pass


class CheckMyLeaveEligibilityInput(StrictAIModel):
    leave_type: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date


class LeaveRequestToolItem(StrictAIModel):
    request_id: str
    leave_type: str
    start_date: date
    end_date: date
    total_days: float
    status: str
    reason: str | None
    submitted_at: datetime
    approver: str | None
    pending_duration_days: int | None
    decided_by: str | None
    decided_at: datetime | None
    decision_reason: str | None


class MyLeaveRequestListOutput(StrictAIModel):
    tool: Literal["get_my_recent_leave_requests"] = "get_my_recent_leave_requests"
    as_of: datetime
    requests: list[LeaveRequestToolItem]
    total_matches: int


class MyLeaveRequestStatusOutput(StrictAIModel):
    tool: Literal["get_my_leave_request_status"] = "get_my_leave_request_status"
    as_of: datetime
    request: LeaveRequestToolItem


class MyLeaveRequestDetailsOutput(StrictAIModel):
    tool: Literal["get_my_leave_request_details"] = "get_my_leave_request_details"
    as_of: datetime
    request: LeaveRequestToolItem


class ExplainMyLeaveDecisionOutput(StrictAIModel):
    tool: Literal["explain_my_leave_decision"] = "explain_my_leave_decision"
    as_of: datetime
    request: LeaveRequestToolItem
    explanation: str
    reason_recorded: bool


class ExcludedEligibilityDate(StrictAIModel):
    date: date
    reason: Literal["weekend", "non_working_day", "company_holiday"]
    label: str | None = None


class LeaveOverlapToolItem(StrictAIModel):
    request_id: str
    leave_type: str
    start_date: date
    end_date: date
    status: str


class LeavePolicyCheckItem(StrictAIModel):
    code: str
    passed: bool


class LeaveEligibilityIssue(StrictAIModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CheckMyLeaveEligibilityOutput(StrictAIModel):
    tool: Literal["check_my_leave_eligibility"] = "check_my_leave_eligibility"
    leave_type: str
    leave_type_code: str
    start_date: date
    end_date: date
    calendar_day_count: int
    working_day_count: float
    weekend_dates_excluded: list[ExcludedEligibilityDate]
    company_holidays_excluded: list[ExcludedEligibilityDate]
    optional_holiday_treatment: Literal[
        "not_applicable", "selected_automatically", "selection_required"
    ]
    required_leave_units: float
    available_leave_balance: BalanceValue
    balance_source: BalanceSource
    existing_overlaps: list[LeaveOverlapToolItem]
    policy_checks_performed: list[LeavePolicyCheckItem]
    blocking_reasons: list[LeaveEligibilityIssue]
    warnings: list[LeaveEligibilityIssue]
    eligibility_status: Literal[
        "eligible",
        "eligible_with_warnings",
        "not_eligible",
        "requires_information",
    ]
    current_approver: str | None
    evaluated_at: datetime
    timezone: str


DraftStatus = Literal[
    "draft",
    "requires_information",
    "not_eligible",
    "ready_for_review",
    "ready_for_confirmation",
    "discarded",
    "expired",
]


class PrepareMyLeaveRequestInput(StrictAIModel):
    leave_type: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=200)


class GetMyLeaveRequestDraftInput(StrictAIModel):
    pass


class UpdateMyLeaveRequestDraftInput(StrictAIModel):
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(default=None, max_length=200)
    remove_reason: bool = False
    continue_to_confirmation: bool = False
    expected_version: int = Field(..., ge=1)


class DiscardMyLeaveRequestDraftInput(StrictAIModel):
    expected_version: int = Field(..., ge=1)


class LeaveRequestDraftOutput(StrictAIModel):
    tool: Literal[
        "prepare_my_leave_request",
        "get_my_leave_request_draft",
        "update_my_leave_request_draft",
        "discard_my_leave_request_draft",
    ]
    draft_id: str
    capability: Literal["leave_request"] = "leave_request"
    status: DraftStatus
    leave_type: str
    leave_type_code: str
    start_date: date
    end_date: date
    calendar_day_count: int
    working_day_count: float
    reason: str | None
    eligibility_status: Literal[
        "eligible",
        "eligible_with_warnings",
        "not_eligible",
        "requires_information",
    ]
    required_leave_units: float
    available_leave_balance: BalanceValue
    balance_source: BalanceSource
    approver: str | None
    approver_resolution: Literal["resolved", "missing"]
    blocking_reasons: list[LeaveEligibilityIssue]
    warnings: list[LeaveEligibilityIssue]
    expires_at: datetime
    version: int
    correlation_id: str


class AIToolError(StrictAIModel):
    code: Literal[
        "UNSUPPORTED_LEAVE_TYPE",
        "LEAVE_TYPE_NOT_APPLICABLE",
        "MISSING_POLICY_CONFIGURATION",
        "MISSING_BALANCE_RECORD",
        "LEAVE_REQUEST_NOT_FOUND",
        "AMBIGUOUS_LEAVE_REQUEST",
        "INVALID_TOOL_INPUT",
        "PERMISSION_DENIED",
        "TOOL_UNAVAILABLE",
        "INVALID_DATE_RANGE",
        "AMBIGUOUS_DATE",
        "MISSING_LEAVE_TYPE",
        "MISSING_DATE_RANGE",
        "DRAFT_NOT_FOUND",
        "DRAFT_EXPIRED",
        "DRAFT_VERSION_CONFLICT",
        "INVALID_REASON",
        "APPROVER_NOT_FOUND",
        "INTAKE_EXPIRED",
        "SUBMISSION_NOT_AVAILABLE_IN_PHASE_3",
    ]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AIChatRequest(StrictAIModel):
    message: str = Field(..., min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)


class AIConversationCreate(StrictAIModel):
    """No ownership input is accepted; ownership comes from the principal."""


class AIConversationMessageOutput(StrictAIModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    response_status: str | None = None
    result_type: str | None = None
    correlation_id: str | None = None
    created_at: datetime
    historical: Literal[True] = True


class AIConversationWorkflowState(StrictAIModel):
    kind: Literal["leave_request_draft", "leave_request"]
    status: str
    display_status: Literal[
        "active", "expired", "discarded", "completed", "cancelled", "unknown"
    ]
    message: str
    refreshed_at: datetime


class AIConversationSummary(StrictAIModel):
    id: str
    title: str
    domain: str
    capability: str | None = None
    status: Literal["active", "closed", "archived"]
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    message_count: int
    workflow_status: str | None = None


class AIConversationListResponse(StrictAIModel):
    conversations: list[AIConversationSummary]


class AIConversationDetail(StrictAIModel):
    conversation: AIConversationSummary
    messages: list[AIConversationMessageOutput]
    workflow: AIConversationWorkflowState | None = None
    facts_require_refresh: bool = True
    notice: str = (
        "Historical messages are restored for context. Orbit AI rechecks current "
        "business facts before giving a new answer."
    )


class AIMessage(StrictAIModel):
    role: Literal["assistant"] = "assistant"
    content: str


class LeaveBalanceResultCard(StrictAIModel):
    type: Literal["leave_balance"] = "leave_balance"
    title: str
    as_of: datetime
    balances: list[LeaveBalanceToolItem]


class LeaveBalanceComparisonCard(StrictAIModel):
    type: Literal["leave_balance_comparison"] = "leave_balance_comparison"
    title: str
    as_of: datetime
    comparison: Literal["at_least", "highest"]
    balances: list[LeaveBalanceToolItem]
    threshold: float | None = None
    meets_threshold: bool | None = None
    highest: LeaveBalanceToolItem | None = None


class LeaveRequestListCard(StrictAIModel):
    type: Literal["leave_request_list"] = "leave_request_list"
    title: str
    as_of: datetime
    requests: list[LeaveRequestToolItem]
    total_matches: int


class LeaveRequestStatusCard(StrictAIModel):
    type: Literal["leave_request_status"] = "leave_request_status"
    title: str
    as_of: datetime
    request: LeaveRequestToolItem


class RejectionExplanationCard(StrictAIModel):
    type: Literal["rejection_explanation"] = "rejection_explanation"
    title: str
    as_of: datetime
    request: LeaveRequestToolItem
    explanation: str
    reason_recorded: bool


class AmbiguousLeaveRequestCard(StrictAIModel):
    type: Literal["ambiguous_leave_request"] = "ambiguous_leave_request"
    title: str = "Which leave request did you mean?"
    candidates: list[LeaveRequestToolItem]


class LeaveEligibilityResultCard(StrictAIModel):
    type: Literal["leave_eligibility"] = "leave_eligibility"
    title: str = "Leave eligibility"
    eligibility: CheckMyLeaveEligibilityOutput


class LeaveEligibilityClarificationCard(StrictAIModel):
    type: Literal["leave_eligibility_clarification"] = (
        "leave_eligibility_clarification"
    )
    title: str = "I need one more detail"
    missing_fields: list[Literal["leave_type", "date_range"]]
    prompt: str


class LeaveRequestDraftCard(StrictAIModel):
    type: Literal["leave_request_draft"] = "leave_request_draft"
    title: str = "Leave request draft"
    draft: LeaveRequestDraftOutput


class LeaveIntakeCollectedFields(StrictAIModel):
    leave_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = None
    supporting_information: str | None = Field(default=None, max_length=500)
    duration_days: int | None = Field(default=None, ge=1, le=31)
    reason_skipped: bool = False
    reason_prompted: bool = False


class LeaveIntakeStateOutput(StrictAIModel):
    goal: Literal["prepare_leave_request"] = "prepare_leave_request"
    collected_fields: LeaveIntakeCollectedFields
    missing_required_fields: list[
        Literal[
            "leave_type",
            "date_range",
            "reason",
            "supporting_information",
        ]
    ]
    optional_fields: list[Literal["reason", "supporting_information"]]
    source_confidence: dict[str, Literal["high", "medium", "low"]]
    conversation_id: str
    created_at: datetime
    expires_at: datetime


class LeaveIntakeQuestionCard(StrictAIModel):
    type: Literal["leave_intake_question"] = "leave_intake_question"
    title: str = "Let’s finish your leave request"
    field: Literal[
        "leave_type",
        "date_range",
        "reason",
        "supporting_information",
    ]
    prompt: str
    intake: LeaveIntakeStateOutput


class LeaveIntakeSummaryCard(StrictAIModel):
    type: Literal["leave_intake_summary"] = "leave_intake_summary"
    title: str = "Leave request details collected"
    intake: LeaveIntakeStateOutput


class LeaveIntakeCancelledCard(StrictAIModel):
    type: Literal["leave_intake_cancelled"] = "leave_intake_cancelled"
    title: str = "Leave intake cleared"
    message: str


AIResultCard = (
    LeaveBalanceResultCard
    | LeaveBalanceComparisonCard
    | LeaveRequestListCard
    | LeaveRequestStatusCard
    | RejectionExplanationCard
    | AmbiguousLeaveRequestCard
    | LeaveEligibilityResultCard
    | LeaveEligibilityClarificationCard
    | LeaveRequestDraftCard
    | LeaveIntakeQuestionCard
    | LeaveIntakeSummaryCard
    | LeaveIntakeCancelledCard
)
AIToolName = Literal[
    "get_my_leave_balance",
    "compare_my_leave_balance",
    "get_my_recent_leave_requests",
    "get_my_leave_request_status",
    "get_my_leave_request_details",
    "explain_my_leave_decision",
    "check_my_leave_eligibility",
    "prepare_my_leave_request",
    "get_my_leave_request_draft",
    "update_my_leave_request_draft",
    "discard_my_leave_request_draft",
]


class AIChatResponse(StrictAIModel):
    conversation_id: str
    status: Literal["completed", "needs_clarification", "unsupported", "failed"]
    message: AIMessage
    result: AIResultCard | None = None
    error: AIToolError | None = None
    tool_used: AIToolName | None = None
    correlation_id: str
