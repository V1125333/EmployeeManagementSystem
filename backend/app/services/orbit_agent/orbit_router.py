from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.authentication import AuthenticatedActor
from app.services.orbit_agent.orbit_capabilities import (
    OrbitExecutor,
    OrbitIntent,
    get_orbit_capability,
)
from app.services.work_calendar_service import employee_region

_IDENTITY_MESSAGE = (
    "I'm Orbit AI, the assistant inside the ReKnew Employee Management System. "
    "I can help with general questions today, and approved EMS capabilities will be connected progressively."
)
_GREETING_MESSAGE = "Hi! I'm Orbit AI. How can I help you?"
_ACKNOWLEDGEMENT_MESSAGE = "You're welcome!"

_GREETING_PATTERNS = {
    "hi",
    "hello",
    "hey",
    "hi orbit",
    "hello orbit",
    "hey orbit",
    "good morning",
    "good afternoon",
    "good evening",
}

_ACKNOWLEDGEMENT_PATTERNS = {
    "thanks",
    "thank you",
    "thank you orbit",
    "got it",
    "okay",
    "ok",
    "sounds good",
}

_DATE_PATTERNS = {
    "what is todays date",
    "whats todays date",
    "what date is it",
    "tell me todays date",
    "todays date",
}

_TIME_PATTERNS = {
    "what time is it",
    "what is the time",
    "what is the time now",
    "whats the time now",
    "whats the current time",
    "tell me the current time",
    "current time",
}

_IDENTITY_PATTERNS = {
    "who are you",
    "what are you",
    "what is orbit ai",
    "tell me about yourself",
}

_REGION_TIMEZONES = {
    "IN": "Asia/Kolkata",
    "US": "America/New_York",
    "AE": "Asia/Dubai",
}

_CONVERSATIONAL_PREFIXES = (
    "hey orbit ",
    "hi orbit ",
    "orbit ",
)


@dataclass(frozen=True)
class OrbitRouteResult:
    intent: OrbitIntent
    executor: OrbitExecutor
    confidence: float
    handled: bool
    message: str | None = None
    timezone_name: str | None = None
    reason: str | None = None


def _local_result(
    intent: OrbitIntent,
    *,
    message: str,
    timezone_name: str | None = None,
    reason: str | None = None,
) -> OrbitRouteResult:
    capability = get_orbit_capability(intent)
    executor = capability.executor if capability else OrbitExecutor.LOCAL
    return OrbitRouteResult(
        intent=intent,
        executor=executor,
        confidence=1.0,
        handled=True,
        message=message,
        timezone_name=timezone_name,
        reason=reason,
    )


def _fallback_result(*, reason: str) -> OrbitRouteResult:
    return OrbitRouteResult(
        intent=OrbitIntent.UNKNOWN,
        executor=OrbitExecutor.HERMES,
        confidence=0.0,
        handled=False,
        reason=reason,
    )


def _normalize_message(message: str) -> str:
    message = message.replace("'", "")
    normalized = "".join(
        character.lower()
        if character.isalnum() or character.isspace()
        else " "
        for character in message
    )
    collapsed = " ".join(normalized.split())
    for prefix in _CONVERSATIONAL_PREFIXES:
        if collapsed.startswith(prefix):
            collapsed = collapsed[len(prefix):].strip()
            break
    return collapsed


def _timezone_for_actor(actor: AuthenticatedActor) -> str:
    candidate = _REGION_TIMEZONES.get(employee_region(actor.employee), "UTC")
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return "UTC"
    return candidate


def _current_time_in_zone(zone: ZoneInfo) -> datetime:
    return datetime.now(zone)


def _observed_now(
    actor: AuthenticatedActor,
    *,
    now: datetime | None = None,
) -> tuple[datetime, str]:
    timezone_name = _timezone_for_actor(actor)
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
        timezone_name = "UTC"
    observed = now or _current_time_in_zone(zone)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc).astimezone(zone)
    else:
        observed = observed.astimezone(zone)
    return observed, timezone_name


def route_orbit_message(
    message: str,
    actor: AuthenticatedActor,
    *,
    now: datetime | None = None,
) -> OrbitRouteResult:
    normalized = _normalize_message(message)

    if normalized in _GREETING_PATTERNS:
        return _local_result(
            OrbitIntent.GREETING,
            message=_GREETING_MESSAGE,
            reason="deterministic_exact_greeting_match",
        )

    if normalized in _ACKNOWLEDGEMENT_PATTERNS:
        return _local_result(
            OrbitIntent.ACKNOWLEDGEMENT,
            message=_ACKNOWLEDGEMENT_MESSAGE,
            reason="deterministic_exact_acknowledgement_match",
        )

    if normalized in _DATE_PATTERNS:
        observed, timezone_name = _observed_now(actor, now=now)
        return _local_result(
            OrbitIntent.UTILITY_DATE,
            message=f"Today is {observed.strftime('%A, %B %d, %Y')}.",
            timezone_name=timezone_name,
            reason="deterministic_exact_date_match",
        )

    if normalized in _TIME_PATTERNS:
        observed, timezone_name = _observed_now(actor, now=now)
        return _local_result(
            OrbitIntent.UTILITY_TIME,
            message=(
                f"The current time is {observed.strftime('%I:%M %p').lstrip('0')} "
                f"{timezone_name}."
            ),
            timezone_name=timezone_name,
            reason="deterministic_exact_time_match",
        )

    if normalized in _IDENTITY_PATTERNS:
        return _local_result(
            OrbitIntent.ORBIT_IDENTITY,
            message=_IDENTITY_MESSAGE,
            reason="deterministic_exact_identity_match",
        )

    return _fallback_result(reason="no_deterministic_match")
