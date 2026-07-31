"""Deterministic semantic parsing into a narrow, typed Phase 1 leave goal."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from app.schemas.ai import LeaveGoal


_TYPE_ALIASES = {
    "casual leave": "Casual Leave",
    "casual": "Casual Leave",
    "sick leave": "Sick Leave",
    "sick": "Sick Leave",
    "earned leave": "Earned Leave",
    "earned": "Earned Leave",
    "maternity leave": "Maternity Leave",
    "maternity": "Maternity Leave",
    "paternity leave": "Paternity Leave",
    "paternity": "Paternity Leave",
    "compensatory off": "Compensatory Off",
    "comp off": "Compensatory Off",
    "loss of pay": "Loss of Pay",
    "bereavement leave": "Bereavement Leave",
    "bereavement": "Bereavement Leave",
    "floating holiday": "Floating Holiday",
    "optional holiday": "Optional Holiday",
    "cl": "Casual Leave",
    "sl": "Sick Leave",
    "el": "Earned Leave",
}
_STATUSES = (
    "draft",
    "submitted",
    "pending",
    "approved",
    "rejected",
    "cancelled",
    "withdrawn",
    "expired",
)
_NUMBER_WORDS = {
    "zero": 0,
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
    "eleven": 11,
    "twelve": 12,
}
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_MONTHS = {
    name.lower(): index for index, name in enumerate(calendar.month_name) if name
}
_MONTHS.update({
    name.lower(): index for index, name in enumerate(calendar.month_abbr) if name
})


def _leave_type(text: str) -> str | None:
    if re.search(r"\b(all|every)\s+(of\s+)?my\s+leave\b", text):
        return None
    for alias in sorted(_TYPE_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return _TYPE_ALIASES[alias]
    generic = re.search(
        r"\b(?:my\s+)?([a-z][a-z -]{1,30}?)\s+leave\s+"
        r"(?:balance|balances|days|available|remaining)\b",
        text,
    )
    if generic:
        candidate = generic.group(1).strip()
        if candidate not in {
            "all",
            "all my",
            "show all my",
            "available",
            "remaining",
        }:
            return candidate
    return None


def _date_reference(text: str, today: date) -> date | None:
    if re.search(r"\btoday\b", text):
        return today
    if re.search(r"\btomorrow\b", text):
        return today + timedelta(days=1)
    weekday = re.search(
        r"\b(?:(next|this)\s+)?(" + "|".join(_WEEKDAYS) + r")\b", text
    )
    if weekday:
        qualifier, name = weekday.groups()
        ahead = (_WEEKDAYS[name] - today.weekday()) % 7
        if qualifier == "next" and ahead == 0:
            ahead = 7
        return today + timedelta(days=ahead)
    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso:
        try:
            return date(*(int(value) for value in iso.groups()))
        except ValueError:
            return None
    return None


def _next_week(today: date) -> tuple[date, date]:
    monday = today + timedelta(days=(7 - today.weekday()))
    return monday, monday + timedelta(days=4)


def _month_day(value: str, today: date) -> date | None:
    match = re.fullmatch(
        r"(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\s+(\d{1,2})",
        value.strip().lower(),
    )
    if not match:
        return None
    month, day = _MONTHS[match.group(1)], int(match.group(2))
    year = today.year
    try:
        candidate = date(year, month, day)
        if candidate < today:
            candidate = date(year + 1, month, day)
        return candidate
    except ValueError:
        return None


def resolve_eligibility_dates(
    text: str, today: date
) -> tuple[date | None, date | None, bool]:
    """Resolve only explicit, deterministic date forms.

    The final boolean indicates that date language was present but unsafe or
    impossible to resolve.
    """
    normalized = " ".join(text.lower().strip().split())
    if "next week" in normalized:
        if re.search(
            r"\b(?:one|two|three|four|\d+)\s+(?:\w+\s+){0,3}(?:leave\s+)?days?\b",
            normalized,
        ):
            return None, None, True
        return (*_next_week(today), False)
    if "this weekend" in normalized:
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        return saturday, saturday + timedelta(days=1), False
    pair = re.search(
        r"\b(next|this)?\s*(" + "|".join(_WEEKDAYS) + r")\s+and\s+"
        r"(next|this)?\s*(" + "|".join(_WEEKDAYS) + r")\b",
        normalized,
    )
    if pair:
        first = _date_reference(
            f"{pair.group(1) or ''} {pair.group(2)}".strip(), today
        )
        second = _date_reference(
            f"{pair.group(3) or ''} {pair.group(4)}".strip(), today
        )
        if first and second and second < first:
            second += timedelta(days=7)
        return first, second, not bool(first and second)
    iso_range = re.search(
        r"\b(20\d{2}-\d{1,2}-\d{1,2})\s+(?:to|through|-)\s+"
        r"(20\d{2}-\d{1,2}-\d{1,2})\b",
        normalized,
    )
    if iso_range:
        try:
            start = date.fromisoformat(iso_range.group(1))
            end = date.fromisoformat(iso_range.group(2))
            return start, end, False
        except ValueError:
            return None, None, True
    month_pattern = "|".join(sorted(_MONTHS, key=len, reverse=True))
    month_range = re.search(
        rf"\b({month_pattern})\s+(\d{{1,2}})\s+(?:to|through|-)\s+"
        rf"(?:(?:({month_pattern})\s+)?(\d{{1,2}}))\b",
        normalized,
    )
    if month_range:
        start = _month_day(f"{month_range.group(1)} {month_range.group(2)}", today)
        end_month = month_range.group(3) or month_range.group(1)
        end = _month_day(f"{end_month} {month_range.group(4)}", today)
        if start and end and end < start and month_range.group(3):
            end = end.replace(year=end.year + 1)
        return start, end, not bool(start and end)
    month_single = re.search(rf"\b({month_pattern})\s+(\d{{1,2}})\b", normalized)
    if month_single:
        day = _month_day(month_single.group(0), today)
        return day, day, day is None
    single = _date_reference(normalized, today)
    if single:
        return single, single, False
    has_date_language = bool(
        re.search(
            r"\b(today|tomorrow|week|weekend|monday|tuesday|wednesday|"
            r"thursday|friday|saturday|sunday|20\d{2}-|\w+\s+\d{1,2})\b",
            normalized,
        )
    )
    return None, None, has_date_language


def _threshold(text: str) -> float | None:
    match = re.search(
        r"\b(?:at\s+least|minimum(?:\s+of)?|enough\s+for)\s+"
        r"(\d+(?:\.\d+)?|" + "|".join(_NUMBER_WORDS) + r")\b",
        text,
    )
    if not match:
        return None
    value = match.group(1)
    return float(_NUMBER_WORDS.get(value, value))


def _draft_reason(text: str) -> str | None:
    match = re.search(
        r"\b(?:add|set|change)(?:\s+(?:the|my))?\s+reason(?:\s+to)?\s+(.+)$"
        r"|\badd\s+(.+?)\s+as\s+(?:the\s+)?reason\b",
        text,
    )
    if not match:
        return None
    return next((value.strip(" .") for value in match.groups() if value), None)


def parse_leave_goal(
    message: str,
    *,
    trusted_request_id: str | None = None,
    today: date | None = None,
) -> LeaveGoal:
    text = " ".join(message.lower().strip().split())
    current = today or date.today()
    leave_type = _leave_type(text)
    statuses = [status for status in _STATUSES if re.search(rf"\b{status}\b", text)]
    on_date = _date_reference(text, current)
    latest = bool(re.search(r"\b(latest|most recent|last)\b", text))
    if latest and re.search(r"\b(was|is)\b", text):
        # In "Was my latest leave approved?", approved is the expected state,
        # not a query filter.
        statuses = []
    history = bool(re.search(r"\b(history|historical|past leaves?)\b", text))
    reference = trusted_request_id if re.search(r"\b(that|it|this)\s+(leave|request)\b|\bsend it\b", text) else None
    start_date, end_date, ambiguous_date = resolve_eligibility_dates(text, current)
    follow_up = (
        "extend_one_day"
        if re.search(r"\bextend\s+(?:it|that|the leave)\s+by\s+one\s+day\b", text)
        else "move_next_week"
        if re.search(r"\bmove\s+(?:it|that|the leave)\s+(?:to\s+)?next\s+week\b", text)
        else "same"
        if re.search(r"\b(?:same leave|check eligibility for (?:it|that|the same leave))\b", text)
        else None
    )
    reason = _draft_reason(text)
    draft_update = (
        "remove_reason"
        if re.search(r"\b(?:remove|clear|delete)(?:\s+(?:the|my))?\s+reason\b", text)
        else "set_reason"
        if reason is not None
        else "change_leave_type"
        if re.search(r"\bchange\s+(?:it|that|the draft)\s+to\s+.+(?:leave|holiday|off)\b", text)
        else "change_dates"
        if re.search(r"\b(?:change|move)\s+(?:it|that|the draft)\s+to\b", text)
        else None
    )
    if follow_up in {"extend_one_day", "move_next_week"}:
        draft_update = None

    if re.search(
        r"\bsubmit\s+(?:it|that|this|the draft|my leave|this leave|"
        r"this leave request|a leave request|the leave request|the request)\b"
        r"|\bsend\s+(?:it|that|this|the draft|the leave request|the request)"
        r"\s+(?:for\s+)?approval\b",
        text,
    ):
        intent = "submission_request"
    elif re.search(r"\b(?:discard|delete|remove)\s+(?:it|that|this|the)?\s*draft\b|\bdiscard\s+(?:it|that)\b", text):
        intent = "draft_discard"
    elif re.search(r"\b(?:show|get|view)\s+(?:me\s+)?(?:my|the|this)?\s*(?:leave\s+)?draft\b", text):
        intent = "draft_get"
    elif re.search(r"\bcontinue(?:\s+with)?\s+(?:it|that|this|the draft)\b|\bready\s+for\s+confirmation\b", text):
        intent = "draft_continue"
    elif draft_update:
        intent = "draft_update"
    elif re.search(
        r"\b(?:prepare|create)\b.*\b(?:leave|draft)\b"
        r"|\bi\s+(?:want|need)\s+.+\b(?:leave|holiday|off)\b"
        r"|\b(?:prepare|use)\s+(?:the\s+)?(?:same leave|dates we (?:just )?checked)\b"
        r"|\b(?:apply|put|book|request)\b.*\b(?:leave|time off|days? off)\b"
        r"|\b(?:i|we)\s+(?:need|want|would like)\b.*\b(?:leave|time off|days? off)\b"
        r"|\bcan you\b.*\b(?:book|put|prepare)\b.*\b(?:leave|time off|days? off)\b"
        r"|\b(?:i am|i.?m|im)\s+sick\b"
        r"|\bfamily event\b.*\b(?:today|tomorrow|week|monday|tuesday|wednesday|"
        r"thursday|friday|saturday|sunday)\b",
        text,
    ):
        intent = "draft_prepare"
    elif re.search(r"\b(apply|submit|book|request)\b", text) and not re.search(
        r"\b(?:eligib|can i|am i|check|overlap|working days?|enough)\b", text
    ):
        intent = "unsupported"
    elif (
        re.search(r"\bwhy\s+(?:am i|i am|i'm)\s+not\s+eligible\b", text)
        or follow_up
    ):
        intent = "eligibility"
    elif re.search(r"\bworking days?\b", text):
        intent = "working_days"
    elif re.search(r"\b(company )?holidays?|include a weekend\b", text) and (
        "leave" in text or start_date
    ):
        intent = "holiday_overlap"
    elif re.search(r"\b(overlap|another leave request|already have)\b", text) and (
        "leave" in text or "request" in text
    ):
        intent = "request_overlap"
    elif re.search(r"\b(can i take|am i eligible|check eligibility|eligible for)\b", text):
        intent = "eligibility"
    elif re.search(r"\b(why|reason|explain)\b", text) and (
        "leave" in text or "request" in text or reference
    ):
        intent = "decision_explanation"
    elif re.search(r"\b(details?|show me more)\b", text) and (
        "leave" in text or "request" in text or reference
    ):
        intent = "request_details"
    elif (
        reference
        or latest
        or re.search(r"\b(status|where is|was .* (approved|rejected))\b", text)
    ) and ("leave" in text or "request" in text or reference):
        intent = "request_status"
    elif history or (
        ("leave" in text or "request" in text)
        and (
            re.search(r"\b(show|list|find|display)\b", text)
            or bool(statuses)
            or re.search(r"\brecent\b", text)
        )
        and not re.search(r"\bbalance|available|remaining\b", text)
    ):
        intent = "request_list"
    elif re.search(r"\b(highest|most leave|largest balance)\b", text):
        intent = "balance_comparison"
    elif _threshold(text) is not None and (
        "leave" in text or leave_type is not None
    ):
        intent = "balance_comparison"
    elif ("leave" in text or leave_type is not None) and re.search(
        r"\b(balance|balances|available|remaining|how many|days do i have|entitlement)\b",
        text,
    ):
        intent = "balance"
    else:
        intent = "unsupported"

    comparison = None
    if intent == "balance_comparison":
        comparison = "highest" if re.search(r"\b(highest|most leave|largest)\b", text) else "at_least"
    return LeaveGoal(
        intent=intent,
        leave_type=leave_type,
        statuses=statuses,
        on_date=on_date,
        latest=latest,
        history=history,
        threshold=_threshold(text),
        comparison=comparison,
        trusted_request_id=reference,
        start_date=start_date,
        end_date=end_date,
        eligibility_follow_up=follow_up,
        draft_update=draft_update,
        reason=reason,
        confidence=(
            "low" if ambiguous_date else "high" if intent != "unsupported" else "low"
        ),
    )
