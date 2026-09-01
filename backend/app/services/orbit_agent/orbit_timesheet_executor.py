from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from fastapi import Request
from sqlalchemy.orm import Session

from app.api import timesheets as timesheet_api
from app.core.authentication import TIMESHEET_SELF_PERMISSION, AuthenticatedActor
from app.services.audit_service import log_audit
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage


class OrbitTimesheetOperation(str, Enum):
    TIMESHEET_TODAY = "timesheet_today"
    TIMESHEET_WEEK = "timesheet_week"
    TIMESHEET_RECENT = "timesheet_recent"
    TIMESHEET_TOTAL_HOURS = "timesheet_total_hours"
    TIMESHEET_STATUS = "timesheet_status"
    TIMESHEET_DAY = "timesheet_day"
    UNKNOWN_TIMESHEET_QUERY = "unknown_timesheet_query"
    WRITE_REQUEST = "write_request"


@dataclass(frozen=True)
class OrbitTimesheetResult:
    operation: OrbitTimesheetOperation
    message: str


_WRITE_PATTERNS = (
    r"\bsubmit\b",
    r"\badd\b",
    r"\bchange\b",
    r"\bedit\b",
    r"\bmodify\b",
    r"\bdelete\b",
    r"\bremove\b",
    r"\bapprove\b",
    r"\breject\b",
    r"\block\b",
    r"\bunlock\b",
)
_THIRD_PARTY_PATTERNS = (
    r"\banother employee\b",
    r"\bsomeone else\b",
    r"\bsomebody else\b",
    r"\bhis timesheet\b",
    r"\bher timesheet\b",
    r"\btheir timesheet\b",
    r"\bshow [a-z][a-z\s]+(?:'s| s) timesheet\b",
    r"\bhow many hours did [a-z][a-z\s]+ log\b",
)
_FOLLOWUP_PREFIXES = (
    "what about",
    "and ",
    "was it",
    "did i",
    "status",
)
_WEEKDAY_NAMES = {
    "sunday": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
}


def _normalize(value: str) -> str:
    return " ".join(
        re.sub(r"[^\w\s'-]", " ", value.strip().lower())
        .replace("_", " ")
        .split()
    )


def _current_week_start(today: date) -> date:
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _week_start_for_day(target_date: date) -> date:
    return target_date - timedelta(days=(target_date.weekday() + 1) % 7)


def _recent_user_messages(recent_context: list[OrbitContextMessage] | None) -> list[str]:
    if not recent_context:
        return []
    return [
        _normalize(item.content)
        for item in recent_context
        if item.role == "user" and item.content.strip()
    ]


def _is_followup(text: str) -> bool:
    return text.startswith(_FOLLOWUP_PREFIXES)


def _extract_target_date(text: str, today: date) -> date | None:
    if "today" in text:
        return today
    if "yesterday" in text:
        return today - timedelta(days=1)
    for weekday_name, weekday_index in _WEEKDAY_NAMES.items():
        if re.search(rf"\b{weekday_name}\b", text):
            current_week_start = today - timedelta(days=today.weekday())
            candidate = current_week_start + timedelta(days=weekday_index)
            return candidate if candidate <= today else candidate - timedelta(days=7)
    return None


def _resolve_operation_from_text(text: str) -> OrbitTimesheetOperation:
    if any(token in text for token in ("recent timesheets", "timesheet history", "my timesheets", "recent weeks")):
        return OrbitTimesheetOperation.TIMESHEET_RECENT
    if "status of my timesheet" in text or "did i submit my timesheet" in text or "was it submitted" in text:
        return OrbitTimesheetOperation.TIMESHEET_STATUS
    if any(re.search(pattern, text) for pattern in _WRITE_PATTERNS):
        return OrbitTimesheetOperation.WRITE_REQUEST
    if "show my timesheet" in text or ("timesheet" in text and any(token in text for token in ("this week", "last week"))):
        return OrbitTimesheetOperation.TIMESHEET_WEEK
    if "how many hours did i log" in text and "today" in text:
        return OrbitTimesheetOperation.TIMESHEET_TODAY
    if any(token in text for token in ("how many hours did i log", "logged hours", "hours did i log")) and any(
        token in text for token in ("this week", "last week", "today", "yesterday")
    ):
        if "this week" in text or "last week" in text:
            return OrbitTimesheetOperation.TIMESHEET_TOTAL_HOURS
        return OrbitTimesheetOperation.TIMESHEET_DAY
    if _extract_target_date(text, date.today()) is not None and any(token in text for token in ("timesheet", "logged", "hours")):
        return OrbitTimesheetOperation.TIMESHEET_DAY
    return OrbitTimesheetOperation.UNKNOWN_TIMESHEET_QUERY


def _resolve_operation(
    text: str,
    recent_context: list[OrbitContextMessage] | None,
) -> OrbitTimesheetOperation:
    direct = _resolve_operation_from_text(text)
    if direct is not OrbitTimesheetOperation.UNKNOWN_TIMESHEET_QUERY:
        return direct
    if not _is_followup(text):
        return direct
    for prior in reversed(_recent_user_messages(recent_context)):
        prior_operation = _resolve_operation_from_text(prior)
        if prior_operation is not OrbitTimesheetOperation.UNKNOWN_TIMESHEET_QUERY:
            return prior_operation
    return direct


def _resolve_week_start(
    text: str,
    *,
    today: date,
    recent_context: list[OrbitContextMessage] | None,
) -> date | None:
    if "this week" in text:
        return _current_week_start(today)
    if "last week" in text:
        return _current_week_start(today) - timedelta(days=7)
    target_date = _extract_target_date(text, today)
    if target_date is not None:
        return _week_start_for_day(target_date)
    if not _is_followup(text):
        return None
    for prior in reversed(_recent_user_messages(recent_context)):
        resolved = _resolve_week_start(prior, today=today, recent_context=None)
        if resolved is not None:
            if "last week" in text:
                return _current_week_start(today) - timedelta(days=7)
            return resolved
    return None


def _format_hours(value: float) -> str:
    return f"{float(value):g}"


def _group_hours_by_day(week) -> list[tuple[date, float]]:
    totals: dict[date, float] = {}
    for entry in week.entries:
        totals[entry.work_date] = round(totals.get(entry.work_date, 0.0) + float(entry.hours), 2)
    return sorted(totals.items(), key=lambda item: item[0])


def _format_week_message(week) -> str:
    day_lines = [
        f"- {work_date.strftime('%A')}: {_format_hours(hours)} hour(s)"
        for work_date, hours in _group_hours_by_day(week)
    ]
    details = "\n".join(day_lines) if day_lines else "- No entries recorded"
    return (
        f"Your timesheet for {week.week_start.isoformat()} to {week.week_end.isoformat()}:\n"
        f"{details}\n"
        f"Total: {_format_hours(week.total_hours)} hour(s). Status: {week.status}."
    )


def _format_recent_message(weeks) -> str:
    if not weeks:
        return "I couldn't find timesheet records for the recent period."
    lines = [
        f"- {week.week_start.isoformat()} to {week.week_end.isoformat()}: {_format_hours(week.total_hours)} hour(s) ({week.status})"
        for week in weeks[:4]
    ]
    return "Your recent timesheets:\n" + "\n".join(lines)


def _has_third_party_reference(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _THIRD_PARTY_PATTERNS)


def _log_timesheet_audit(
    db: Session,
    actor: AuthenticatedActor,
    *,
    operation: OrbitTimesheetOperation,
    message: str,
    request: Request | None,
    success: bool,
) -> None:
    log_audit(
        db,
        actor.employee,
        action="orbit.timesheet.read",
        entity_type="orbit_timesheet_query",
        entity_id=actor.employee.id,
        reason=f"Orbit handled {operation.value}.",
        metadata={
            "operation": operation.value,
            "success": success,
            "message_length": len(message.strip()),
        },
        source="orbit",
        request=request,
    )


async def execute_timesheet_read(
    *,
    db: Session,
    actor: AuthenticatedActor,
    query: str,
    recent_context: list[OrbitContextMessage] | None = None,
    request: Request | None = None,
) -> OrbitTimesheetResult:
    normalized = _normalize(query)
    today = date.today()
    operation = _resolve_operation(normalized, recent_context)

    if not actor.principal.has_permission(TIMESHEET_SELF_PERMISSION):
        result = OrbitTimesheetResult(
            operation=operation,
            message="You do not have permission to view timesheet information.",
        )
        _log_timesheet_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    if _has_third_party_reference(normalized):
        result = OrbitTimesheetResult(
            operation=OrbitTimesheetOperation.UNKNOWN_TIMESHEET_QUERY,
            message="Orbit can currently access only your own timesheet information.",
        )
        _log_timesheet_audit(db, actor, operation=result.operation, message=query, request=request, success=False)
        return result

    if operation is OrbitTimesheetOperation.WRITE_REQUEST:
        result = OrbitTimesheetResult(
            operation=operation,
            message="I can currently view your timesheet information, but adding, changing, or submitting timesheets through Orbit isn't enabled yet.",
        )
        _log_timesheet_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    try:
        if operation is OrbitTimesheetOperation.TIMESHEET_RECENT:
            weeks = await timesheet_api.my_timesheet_history(db=db, actor=actor)
            result = OrbitTimesheetResult(operation=operation, message=_format_recent_message(weeks))
            _log_timesheet_audit(db, actor, operation=operation, message=query, request=request, success=bool(weeks))
            return result

        target_date = _extract_target_date(normalized, today)
        target_week_start = _resolve_week_start(normalized, today=today, recent_context=recent_context) or _current_week_start(today)
        entries = timesheet_api.load_week_entries(db, actor.employee.id, target_week_start)

        if operation in {OrbitTimesheetOperation.TIMESHEET_DAY, OrbitTimesheetOperation.TIMESHEET_TODAY}:
            target_date = target_date or today
            matching = [entry for entry in entries if entry.work_date == target_date]
            if not matching:
                day_label = "today" if target_date == today else target_date.isoformat()
                result = OrbitTimesheetResult(
                    operation=operation,
                    message=f"I don't see a timesheet entry for {day_label}.",
                )
                _log_timesheet_audit(db, actor, operation=operation, message=query, request=request, success=False)
                return result
            total_hours = round(sum(float(entry.hours) for entry in matching), 2)
            if target_date == today:
                message = f"You've logged {_format_hours(total_hours)} hour(s) today."
            else:
                message = f"You logged {_format_hours(total_hours)} hour(s) on {target_date.strftime('%A, %b')} {target_date.day}, {target_date.year}."
            result = OrbitTimesheetResult(operation=operation, message=message)
            _log_timesheet_audit(db, actor, operation=operation, message=query, request=request, success=True)
            return result

        if not entries:
            period_label = "this week" if target_week_start == _current_week_start(today) else f"the week of {target_week_start.isoformat()}"
            result = OrbitTimesheetResult(
                operation=operation,
                message=f"I couldn't find timesheet records for {period_label}.",
            )
            _log_timesheet_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result

        week = timesheet_api.serialize_employee_week(db, actor.employee, target_week_start, entries)

        if operation is OrbitTimesheetOperation.TIMESHEET_TOTAL_HOURS:
            label = "this week" if target_week_start == _current_week_start(today) else "last week"
            result = OrbitTimesheetResult(
                operation=operation,
                message=f"You've logged {_format_hours(week.total_hours)} hour(s) {label}.",
            )
        elif operation is OrbitTimesheetOperation.TIMESHEET_STATUS:
            result = OrbitTimesheetResult(
                operation=operation,
                message=f"Your timesheet for {week.week_start.isoformat()} to {week.week_end.isoformat()} is {week.status}.",
            )
        elif operation is OrbitTimesheetOperation.TIMESHEET_WEEK:
            result = OrbitTimesheetResult(
                operation=operation,
                message=_format_week_message(week),
            )
        else:
            result = OrbitTimesheetResult(
                operation=OrbitTimesheetOperation.UNKNOWN_TIMESHEET_QUERY,
                message="I can currently help with today's timesheet hours, week totals, week status, and recent timesheets.",
            )
        _log_timesheet_audit(db, actor, operation=result.operation, message=query, request=request, success=True)
        return result
    except Exception:
        result = OrbitTimesheetResult(
            operation=operation,
            message="I couldn't retrieve your timesheet information right now.",
        )
        _log_timesheet_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result
