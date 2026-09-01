from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.authentication import ATTENDANCE_SELF_PERMISSION, AuthenticatedActor
from app.services.attendance_service import (
    AttendanceSnapshot,
    get_my_attendance_on_date,
    get_my_attendance_today,
    list_my_attendance_history,
)
from app.services.audit_service import log_audit
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage


class OrbitAttendanceOperation(str, Enum):
    ATTENDANCE_TODAY = "attendance_today"
    ATTENDANCE_DATE = "attendance_date"
    ATTENDANCE_RECENT = "attendance_recent"
    ATTENDANCE_SUMMARY = "attendance_summary"
    ATTENDANCE_PRESENT_COUNT = "attendance_present_count"
    ATTENDANCE_ABSENT_COUNT = "attendance_absent_count"
    UNKNOWN_ATTENDANCE_QUERY = "unknown_attendance_query"
    WRITE_REQUEST = "write_request"


@dataclass(frozen=True)
class OrbitAttendanceResult:
    operation: OrbitAttendanceOperation
    message: str


_WRITE_PATTERNS = (
    r"\bcheck me in\b",
    r"\bcheck me out\b",
    r"\bcheck in\b",
    r"\bcheck out\b",
    r"\bclock in\b",
    r"\bclock out\b",
    r"\bmark me present\b",
    r"\bmark attendance\b",
    r"\bfix\b.*\battendance\b",
    r"\bchange\b.*\bcheckout\b",
    r"\bchange\b.*\bcheck out\b",
    r"\bcorrect\b.*\battendance\b",
    r"\bregulari[sz]e\b",
    r"\boverride\b.*\battendance\b",
)
_FOLLOWUP_PREFIXES = (
    "what about",
    "and ",
    "how about",
    "was i",
    "am i",
)
_WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_PRESENT_STATUSES = {"present", "late", "wfh"}


def _normalize(value: str) -> str:
    return " ".join(
        re.sub(r"[^\w\s'-]", " ", value.strip().lower())
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


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


def _looks_like_attendance_write(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _WRITE_PATTERNS)


def _weekday_date(name: str, today: date) -> date:
    target = _WEEKDAY_NAMES[name]
    current_week_start = today - timedelta(days=today.weekday())
    candidate = current_week_start + timedelta(days=target)
    return candidate if candidate <= today else candidate - timedelta(days=7)


def _extract_target_date(text: str, today: date) -> date | None:
    if "today" in text:
        return today
    if "yesterday" in text:
        return today - timedelta(days=1)
    for weekday_name in _WEEKDAY_NAMES:
        if re.search(rf"\b{weekday_name}\b", text):
            return _weekday_date(weekday_name, today)
    return None


def _current_week_range(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, today


def _current_month_range(today: date) -> tuple[date, date]:
    start = today.replace(day=1)
    return start, today


def _format_time(value) -> str:
    if value is None:
        return "not recorded"
    return value.strftime("%I:%M %p").lstrip("0")


def _format_hours(value: float | None) -> str:
    if value is None:
        return "not recorded"
    return f"{float(value):g} hour(s)"


def _format_short_date(value: date) -> str:
    return f"{value.strftime('%A, %b')} {value.day}, {value.year}"


def _format_snapshot(snapshot: AttendanceSnapshot) -> str:
    base = f"Your attendance for {_format_short_date(snapshot.date)} is {snapshot.status.replace('_', ' ')}."
    if snapshot.status == "not_checked_in":
        return base
    base += f" Check-in: {_format_time(snapshot.check_in)}."
    if snapshot.check_out:
        base += f" Check-out: {_format_time(snapshot.check_out)}."
    if snapshot.total_hours is not None:
        base += f" Worked: {_format_hours(snapshot.total_hours)}."
    return base


def _resolve_operation_from_text(text: str) -> OrbitAttendanceOperation:
    if _looks_like_attendance_write(text):
        return OrbitAttendanceOperation.WRITE_REQUEST
    if "attendance today" in text or "my attendance today" in text or text == "attendance today":
        return OrbitAttendanceOperation.ATTENDANCE_TODAY
    if "attendance" in text and ("today" in text or "current status" in text):
        return OrbitAttendanceOperation.ATTENDANCE_TODAY
    if any(token in text for token in ("recent attendance", "attendance history", "my attendance history")):
        return OrbitAttendanceOperation.ATTENDANCE_RECENT
    if "how many" in text and "present" in text:
        return OrbitAttendanceOperation.ATTENDANCE_PRESENT_COUNT
    if "how many" in text and "absent" in text:
        return OrbitAttendanceOperation.ATTENDANCE_ABSENT_COUNT
    if any(token in text for token in ("this week", "this month")) and "attendance" in text:
        return OrbitAttendanceOperation.ATTENDANCE_SUMMARY
    if _extract_target_date(text, date.today()) is not None and any(token in text for token in ("attendance", "present", "absent", "late", "wfh", "checked in", "check in")):
        return OrbitAttendanceOperation.ATTENDANCE_DATE
    return OrbitAttendanceOperation.UNKNOWN_ATTENDANCE_QUERY


def _resolve_operation(text: str, recent_context: list[OrbitContextMessage] | None) -> OrbitAttendanceOperation:
    direct = _resolve_operation_from_text(text)
    if direct is not OrbitAttendanceOperation.UNKNOWN_ATTENDANCE_QUERY:
        return direct
    if not _is_followup(text):
        return direct
    for prior in reversed(_recent_user_messages(recent_context)):
        prior_operation = _resolve_operation_from_text(prior)
        if prior_operation is not OrbitAttendanceOperation.UNKNOWN_ATTENDANCE_QUERY:
            if prior_operation in {
                OrbitAttendanceOperation.ATTENDANCE_DATE,
                OrbitAttendanceOperation.ATTENDANCE_TODAY,
                OrbitAttendanceOperation.ATTENDANCE_SUMMARY,
                OrbitAttendanceOperation.ATTENDANCE_PRESENT_COUNT,
                OrbitAttendanceOperation.ATTENDANCE_ABSENT_COUNT,
            }:
                return prior_operation
    return direct


def _resolve_range(text: str, today: date) -> tuple[date, date] | None:
    if "this week" in text:
        return _current_week_range(today)
    if "this month" in text:
        return _current_month_range(today)
    return None


def _log_attendance_audit(
    db: Session,
    actor: AuthenticatedActor,
    *,
    operation: OrbitAttendanceOperation,
    message: str,
    request: Request | None,
    success: bool,
) -> None:
    log_audit(
        db,
        actor.employee,
        action="orbit.attendance.read",
        entity_type="orbit_attendance_query",
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


def _count_matching_statuses(records: list[AttendanceSnapshot], *, include: set[str]) -> int:
    return sum(1 for record in records if record.status in include)


async def execute_attendance_read(
    *,
    db: Session,
    actor: AuthenticatedActor,
    query: str,
    recent_context: list[OrbitContextMessage] | None = None,
    request: Request | None = None,
) -> OrbitAttendanceResult:
    normalized = _normalize(query)
    today = date.today()
    operation = _resolve_operation(normalized, recent_context)
    target_date = _extract_target_date(normalized, today)
    if operation is OrbitAttendanceOperation.ATTENDANCE_TODAY and target_date not in {None, today}:
        operation = OrbitAttendanceOperation.ATTENDANCE_DATE

    if not actor.principal.has_permission(ATTENDANCE_SELF_PERMISSION):
        result = OrbitAttendanceResult(
            operation=operation,
            message="You do not have permission to view attendance information.",
        )
        _log_attendance_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    if operation is OrbitAttendanceOperation.WRITE_REQUEST:
        result = OrbitAttendanceResult(
            operation=operation,
            message="Orbit can currently read your attendance information, but it can't check you in, check you out, or change attendance records yet.",
        )
        _log_attendance_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    try:
        if operation is OrbitAttendanceOperation.ATTENDANCE_TODAY:
            snapshot = get_my_attendance_today(db, actor.employee, today=today)
            result = OrbitAttendanceResult(operation=operation, message=_format_snapshot(snapshot))
        elif operation is OrbitAttendanceOperation.ATTENDANCE_DATE:
            if target_date is None:
                result = OrbitAttendanceResult(
                    operation=OrbitAttendanceOperation.UNKNOWN_ATTENDANCE_QUERY,
                    message="I can currently help with today's attendance, a specific recent day, recent attendance, and week or month summaries.",
                )
            else:
                snapshot = get_my_attendance_on_date(db, actor.employee, target_date)
                result = OrbitAttendanceResult(operation=operation, message=_format_snapshot(snapshot))
        elif operation is OrbitAttendanceOperation.ATTENDANCE_RECENT:
            records = list_my_attendance_history(db, actor.employee, today=today)
            if not records:
                result = OrbitAttendanceResult(operation=operation, message="You don't have any attendance records in the selected range.")
            else:
                summary = "; ".join(
                    f"{record.date.isoformat()}: {record.status.replace('_', ' ')}"
                    for record in records[:5]
                )
                result = OrbitAttendanceResult(operation=operation, message=f"Your recent attendance: {summary}.")
        elif operation in {
            OrbitAttendanceOperation.ATTENDANCE_SUMMARY,
            OrbitAttendanceOperation.ATTENDANCE_PRESENT_COUNT,
            OrbitAttendanceOperation.ATTENDANCE_ABSENT_COUNT,
        }:
            date_range = _resolve_range(normalized, today)
            if date_range is None:
                result = OrbitAttendanceResult(
                    operation=OrbitAttendanceOperation.UNKNOWN_ATTENDANCE_QUERY,
                    message="Please mention a supported range like this week or this month for attendance summaries.",
                )
            else:
                start, end = date_range
                records = list_my_attendance_history(
                    db,
                    actor.employee,
                    date_from=max(start, actor.employee.date_of_joining or actor.employee.joining_date),
                    date_to=end,
                    today=today,
                )
                label = "this week" if "this week" in normalized else "this month"
                if operation is OrbitAttendanceOperation.ATTENDANCE_SUMMARY:
                    if not records:
                        result = OrbitAttendanceResult(operation=operation, message=f"I couldn't find attendance records for {label}.")
                    else:
                        present = _count_matching_statuses(records, include=_PRESENT_STATUSES)
                        absent = _count_matching_statuses(records, include={"absent"})
                        late = _count_matching_statuses(records, include={"late"})
                        result = OrbitAttendanceResult(
                            operation=operation,
                            message=(
                                f"Your attendance summary for {label}: {present} present or working-from-home day(s), "
                                f"{absent} absent day(s), and {late} late day(s), based on {len(records)} recorded day(s)."
                            ),
                        )
                elif operation is OrbitAttendanceOperation.ATTENDANCE_PRESENT_COUNT:
                    present = _count_matching_statuses(records, include=_PRESENT_STATUSES)
                    result = OrbitAttendanceResult(
                        operation=operation,
                        message=f"You were present or working from home for {present} recorded day(s) in {label}.",
                    )
                else:
                    absent = _count_matching_statuses(records, include={"absent"})
                    result = OrbitAttendanceResult(
                        operation=operation,
                        message=f"You were absent for {absent} recorded day(s) in {label}.",
                    )
        else:
            result = OrbitAttendanceResult(
                operation=OrbitAttendanceOperation.UNKNOWN_ATTENDANCE_QUERY,
                message="I can currently help with today's attendance, a recent day, recent attendance, and attendance summaries for this week or this month.",
            )
        _log_attendance_audit(db, actor, operation=result.operation, message=query, request=request, success=True)
        return result
    except ValueError as exc:
        result = OrbitAttendanceResult(
            operation=operation,
            message=str(exc),
        )
        _log_attendance_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result
    except Exception:
        result = OrbitAttendanceResult(
            operation=operation,
            message="Your attendance information is temporarily unavailable.",
        )
        _log_attendance_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result
