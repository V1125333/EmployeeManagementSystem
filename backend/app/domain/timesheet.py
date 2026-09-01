"""Framework-independent timesheet aggregate states and future transitions."""

from enum import StrEnum


class TimesheetWeekState(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    MIXED_LEGACY = "mixed_legacy"


class TimesheetReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class TimesheetIdempotencyStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


# Documentation-level transition map for Task 8C-8F. Current routes do not use it.
ALLOWED_FUTURE_TRANSITIONS: dict[TimesheetWeekState, frozenset[TimesheetWeekState]] = {
    TimesheetWeekState.DRAFT: frozenset({TimesheetWeekState.SUBMITTED}),
    TimesheetWeekState.SUBMITTED: frozenset({
        TimesheetWeekState.DRAFT,
        TimesheetWeekState.APPROVED,
        TimesheetWeekState.REJECTED,
    }),
    TimesheetWeekState.REJECTED: frozenset({TimesheetWeekState.DRAFT}),
    TimesheetWeekState.APPROVED: frozenset(),
    TimesheetWeekState.MIXED_LEGACY: frozenset(),
}
