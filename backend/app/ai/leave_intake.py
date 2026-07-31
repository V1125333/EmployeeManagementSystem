"""Deterministic slot extraction for conversational leave intake."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.ai.leave_intent import parse_leave_goal, resolve_eligibility_dates
from app.schemas.ai import LeaveIntakeCollectedFields


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


@dataclass(frozen=True)
class IntakeSlotUpdate:
    leave_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = None
    supporting_information: str | None = None
    duration_days: int | None = None
    skip_reason: bool = False
    start_over: bool = False
    ambiguous_dates: bool = False
    confidence: dict[str, str] = field(default_factory=dict)


def is_informal_leave_request(message: str) -> bool:
    text = " ".join(message.casefold().strip().split())
    patterns = (
        r"\b(?:apply|put|book|request)\b.*\b(?:leave|time off|days? off)\b",
        r"\b(?:i|we)\s+(?:need|want|would like)\b.*\b(?:leave|time off|days? off)\b",
        r"\bcan you\b.*\b(?:leave|time off|days? off)\b",
        r"\b(?:i am|i'm|im)\s+sick\b",
        r"\bfamily event\b.*\b(?:today|tomorrow|week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def is_intake_follow_up(message: str, today: date) -> bool:
    text = " ".join(message.casefold().strip().split())
    if re.search(r"\bstart over\b|\bno reason\b|\bskip (?:the )?reason\b", text):
        return True
    goal = parse_leave_goal(message, today=today)
    if goal.leave_type or goal.start_date or goal.end_date or goal.reason:
        return True
    if re.search(
        r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+days?\b",
        text,
    ):
        return True
    if re.search(
        r"\b(?:today|tomorrow|next week|this week|monday|tuesday|wednesday|"
        r"thursday|friday|saturday|sunday)\b",
        text,
    ):
        return True
    return bool(re.search(r"\b(?:reason|because|family event)\b", text))


def _duration(text: str) -> int | None:
    match = re.search(
        r"\b(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+days?\b",
        text,
    )
    if not match:
        return None
    raw = match.group(1)
    value = _NUMBER_WORDS.get(raw, int(raw) if raw.isdigit() else 0)
    return value if 1 <= value <= 31 else None


def _reason(text: str) -> str | None:
    match = re.search(
        r"\b(?:add|set|change)(?:\s+(?:the|my))?\s+reason"
        r"(?:\s+to)?\s+(.+)$"
        r"|\badd\s+(.+?)\s+as\s+(?:the\s+)?reason\b"
        r"|\bbecause\s+(.+)$",
        text,
    )
    if match:
        return next(
            (value.strip(" .") for value in match.groups() if value),
            None,
        )
    if re.search(r"\bfamily event\b", text):
        return "family event"
    return None


def _supporting_information(text: str) -> str | None:
    match = re.search(
        r"\b(?:supporting information|supporting document|attachment|evidence)"
        r"(?:\s+is|\s*:)?\s+(.+)$",
        text,
    )
    if not match:
        return None
    value = match.group(1).strip(" .")
    return value or None


def extract_intake_slots(
    message: str,
    *,
    today: date,
    current: LeaveIntakeCollectedFields | None = None,
) -> IntakeSlotUpdate:
    text = " ".join(message.casefold().strip().split())
    if re.search(r"\bstart over\b|\bcancel (?:this |the )?(?:intake|request)\b", text):
        return IntakeSlotUpdate(start_over=True)

    goal = parse_leave_goal(message, today=today)
    confidence: dict[str, str] = {}
    leave_type = goal.leave_type
    if leave_type:
        confidence["leave_type"] = "high"

    duration = _duration(text)
    start_date, end_date, ambiguous = resolve_eligibility_dates(text, today)
    if "next week" in text and not re.search(
        r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
    ):
        start_date = end_date = None
        ambiguous = True

    anchored_duration = re.search(
        r"\b(?:\d+|" + "|".join(_NUMBER_WORDS) + r")\s+days?\s+"
        r"(?:from|starting|beginning)\b",
        text,
    )
    if duration and start_date and anchored_duration:
        end_date = start_date + timedelta(days=duration - 1)
        ambiguous = False
    elif duration and current and current.start_date and not start_date:
        start_date = current.start_date
        end_date = start_date + timedelta(days=duration - 1)
        ambiguous = False
    if start_date and end_date:
        confidence["date_range"] = "high"

    reason = _reason(text)
    if reason:
        confidence["reason"] = "high"
    supporting_information = _supporting_information(text)
    if supporting_information:
        confidence["supporting_information"] = "high"
    skip_reason = bool(
        re.search(
            r"\b(?:no reason|skip (?:the )?reason|without (?:a )?reason)\b",
            text,
        )
    )
    return IntakeSlotUpdate(
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        supporting_information=supporting_information,
        duration_days=duration,
        skip_reason=skip_reason,
        ambiguous_dates=ambiguous,
        confidence=confidence,
    )
