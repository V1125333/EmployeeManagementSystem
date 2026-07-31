from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LeaveRequestInput(StrictModel):
    leave_type_id: str = Field(..., min_length=1, max_length=36)
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=1, max_length=200)
    action: Literal["draft", "submit"] = "submit"
    holiday_id: str | None = Field(default=None, max_length=36)


class LeaveAssessmentInput(StrictModel):
    leave_type_id: str = Field(..., min_length=1, max_length=36)
    start_date: date
    end_date: date
    holiday_id: str | None = Field(default=None, max_length=36)


class LeaveSubmissionInput(StrictModel):
    leave_type_id: str = Field(..., min_length=1, max_length=36)
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=1, max_length=200)
    holiday_id: str | None = Field(default=None, max_length=36)


class LeaveDecisionInput(StrictModel):
    decision: Literal["approve", "reject"]
    reviewer_notes: str | None = Field(default=None, max_length=300)


class ConfiguredLeavePolicy(StrictModel):
    leave_type_id: str
    name: str
    code: str
    is_paid: bool
    is_carry_forward: bool
    max_carry_forward_days: float
    allow_future_dates: bool
    past_date_limit_days: int | None
    future_date_warning: str | None
    max_advance_days: int = 90
    past_dates_currently_allowed: bool = False


class LeaveBalanceResponse(StrictModel):
    leave_type_id: str
    type: str
    code: str
    date_policy: ConfiguredLeavePolicy
    total: float
    available: float | Literal["On request"]
    effective_available: float | Literal["On request"]
    used: float
    pending: float
    is_paid: bool
    is_carry_forward: bool
    max_carry_forward_days: float
    expiry_label: str
    initialized: bool
    source: Literal["stored_balance", "policy_default", "on_request"]


class LeaveBalancesSnapshot(StrictModel):
    as_of: datetime
    year: int
    balances: list[LeaveBalanceResponse]


class LeaveRequestResponse(StrictModel):
    id: str
    employee_id: str
    employee_name: str
    leave_type_id: str
    leave_type: str
    start_date: date
    end_date: date
    total_days: float
    holiday_id: str | None
    reason: str | None
    status: str
    reporting_manager: str | None
    pending_with: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    reviewer_notes: str | None
    created_at: datetime
    updated_at: datetime


class LeaveContextResponse(StrictModel):
    as_of: datetime
    reporting_manager: str | None
    joining_date: date | None
    min_request_date: date
    balances: list[LeaveBalanceResponse]
    requests: list[LeaveRequestResponse]


class LeaveBlockingReason(StrictModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class LeaveWarning(StrictModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExcludedLeaveDate(StrictModel):
    date: date
    reason: Literal["weekend", "non_working_day", "company_holiday"]
    label: str | None = None


class LeaveEligibilityResponse(StrictModel):
    as_of: datetime
    eligible: bool
    leave_type_id: str
    start_date: date
    end_date: date
    payable_working_days: float
    effective_balance_before: float | Literal["On request"]
    effective_balance_after: float | Literal["On request"]
    excluded_weekends: list[ExcludedLeaveDate]
    excluded_holidays: list[ExcludedLeaveDate]
    warnings: list[LeaveWarning]
    blocking_reasons: list[LeaveBlockingReason]
    policy: ConfiguredLeavePolicy


class LeaveOverlapSummary(StrictModel):
    request_id: str
    leave_type: str
    start_date: date
    end_date: date
    status: str


class LeavePolicyCheck(StrictModel):
    code: str
    passed: bool


class MyLeaveEligibilityResult(StrictModel):
    leave_type: str
    leave_type_code: str
    start_date: date
    end_date: date
    calendar_day_count: int
    working_day_count: float
    weekend_dates_excluded: list[ExcludedLeaveDate]
    company_holidays_excluded: list[ExcludedLeaveDate]
    optional_holiday_treatment: Literal[
        "not_applicable", "selected_automatically", "selection_required"
    ]
    required_leave_units: float
    available_leave_balance: float | Literal["On request"]
    balance_source: Literal["stored_balance", "policy_default", "on_request"]
    existing_overlaps: list[LeaveOverlapSummary]
    policy_checks_performed: list[LeavePolicyCheck]
    blocking_reasons: list[LeaveBlockingReason]
    warnings: list[LeaveWarning]
    eligibility_status: Literal[
        "eligible",
        "eligible_with_warnings",
        "not_eligible",
        "requires_information",
    ]
    current_approver: str | None
    evaluated_at: datetime
    timezone: str


class SubmittedLeaveResult(StrictModel):
    request_id: str
    request: LeaveRequestResponse
    authoritative_initial_status: Literal["pending"]
    submitted_at: datetime
    pending_approval_owner: str | None
    correlation_id: str | None = None


class OwnerScopedLeaveRequestStatus(StrictModel):
    request_id: str
    status: str
    request: LeaveRequestResponse
    as_of: datetime


class MyLeaveRequestQuery(StrictModel):
    statuses: list[
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
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)
    on_date: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    limit: int = Field(default=12, ge=1, le=25)


class MyLeaveRequestList(StrictModel):
    as_of: datetime
    requests: list[LeaveRequestResponse]
    total_matches: int


class StructuredErrorDetail(StrictModel):
    code: str
    message: str
    field: str | None = None
    correlation_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class StructuredErrorResponse(StrictModel):
    detail: StructuredErrorDetail
