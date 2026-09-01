from __future__ import annotations

from datetime import datetime, timezone

from app.core.authentication import AuthenticatedActor, AuthenticatedPrincipal
from app.models.employee import Employee
from app.services.orbit_agent.orbit_capabilities import OrbitExecutor, OrbitIntent
from app.services.orbit_agent.orbit_router import route_orbit_message


def _actor(*, work_country: str | None = "United States") -> AuthenticatedActor:
    employee = Employee(
        id="orbit-router-user",
        first_name="Orbit",
        last_name="Router",
        work_email="router@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        joining_date=datetime(2025, 1, 1, tzinfo=timezone.utc).date(),
        department="Engineering",
        designation="Engineer",
        reporting_manager="Admin User",
        work_country=work_country,
    )
    principal = AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role="employee",
        status="active",
        permissions=frozenset(),
        token_id="token-1",
        access_level="standard",
        manager_id=None,
        department_id=None,
        organization_scope="reknew",
    )
    return AuthenticatedActor(principal=principal, employee=employee)


def test_route_orbit_message_handles_current_date():
    actor = _actor()
    observed = datetime(2026, 8, 23, 9, 45, tzinfo=timezone.utc)

    result = route_orbit_message("What is today's date?", actor, now=observed)

    assert result.intent is OrbitIntent.UTILITY_DATE
    assert result.executor is OrbitExecutor.LOCAL
    assert result.confidence == 1.0
    assert result.handled is True
    assert result.message == "Today is Sunday, August 23, 2026."


def test_route_orbit_message_handles_current_time_in_backend_timezone():
    actor = _actor()
    observed = datetime(2026, 8, 23, 15, 42, tzinfo=timezone.utc)

    result = route_orbit_message("What time is it?", actor, now=observed)

    assert result.intent is OrbitIntent.UTILITY_TIME
    assert result.executor is OrbitExecutor.LOCAL
    assert result.confidence == 1.0
    assert result.handled is True
    assert result.message == "The current time is 11:42 AM America/New_York."
    assert result.timezone_name == "America/New_York"


def test_route_orbit_message_handles_common_time_variations():
    actor = _actor()
    observed = datetime(2026, 8, 23, 15, 42, tzinfo=timezone.utc)

    examples = (
        "What time is it?",
        "What is the time?",
        "What is the time now?",
        "What's the time now?",
        "Tell me the current time.",
        "Hey Orbit, what is the time now?",
        "Orbit, what time is it?",
    )

    for example in examples:
        result = route_orbit_message(example, actor, now=observed)
        assert result.intent is OrbitIntent.UTILITY_TIME, example
        assert result.executor is OrbitExecutor.LOCAL, example
        assert result.confidence == 1.0, example
        assert result.handled is True, example
        assert result.message == "The current time is 11:42 AM America/New_York.", example


def test_route_orbit_message_handles_identity():
    result = route_orbit_message("Who are you?", _actor())

    assert result.intent is OrbitIntent.ORBIT_IDENTITY
    assert result.executor is OrbitExecutor.LOCAL
    assert result.confidence == 1.0
    assert result.handled is True
    assert "I'm Orbit AI" in (result.message or "")


def test_route_orbit_message_handles_greetings():
    examples = (
        "hi",
        "hello",
        "hey orbit",
        "good morning",
        "good afternoon",
        "good evening",
    )

    for example in examples:
        result = route_orbit_message(example, _actor())
        assert result.intent is OrbitIntent.GREETING, example
        assert result.executor is OrbitExecutor.LOCAL, example
        assert result.confidence == 1.0, example
        assert result.handled is True, example
        assert result.message == "Hi! I'm Orbit AI. How can I help you?", example


def test_route_orbit_message_handles_acknowledgements():
    examples = (
        "thanks",
        "thank you",
        "thank you orbit",
        "got it",
        "ok",
        "okay",
        "sounds good",
    )

    for example in examples:
        result = route_orbit_message(example, _actor())
        assert result.intent is OrbitIntent.ACKNOWLEDGEMENT, example
        assert result.executor is OrbitExecutor.LOCAL, example
        assert result.confidence == 1.0, example
        assert result.handled is True, example
        assert result.message == "You're welcome!", example


def test_route_orbit_message_keeps_false_positive_time_requests_for_hermes():
    examples = (
        "What time did I check in yesterday?",
        "What time does my shift start?",
        "What time is my meeting?",
    )

    for example in examples:
        result = route_orbit_message(example, _actor())
        assert result.intent is OrbitIntent.UNKNOWN, example
        assert result.executor is OrbitExecutor.HERMES, example
        assert result.confidence == 0.0, example
        assert result.handled is False, example
        assert result.reason == "no_deterministic_match", example


def test_route_orbit_message_keeps_false_positive_date_requests_for_hermes():
    result = route_orbit_message("What dates are available for leave?", _actor())

    assert result.intent is OrbitIntent.UNKNOWN
    assert result.executor is OrbitExecutor.HERMES
    assert result.confidence == 0.0
    assert result.handled is False
    assert result.reason == "no_deterministic_match"


def test_route_orbit_message_keeps_greeting_and_acknowledgement_false_positives_for_hermes():
    examples = (
        "Can you write a thank-you email?",
        "Explain why saying hello matters in customer support.",
        "Is it okay to submit my timesheet tomorrow?",
    )

    for example in examples:
        result = route_orbit_message(example, _actor())
        assert result.intent is OrbitIntent.UNKNOWN, example
        assert result.executor is OrbitExecutor.HERMES, example
        assert result.confidence == 0.0, example
        assert result.handled is False, example
        assert result.reason == "no_deterministic_match", example


def test_route_orbit_message_falls_back_to_utc_when_region_is_unknown():
    actor = _actor(work_country=None)
    actor.employee.work_location = "Onshore"
    actor.employee.work_city = None
    actor.employee.work_state = None
    observed = datetime(2026, 8, 23, 15, 42, tzinfo=timezone.utc)

    result = route_orbit_message("Current time?", actor, now=observed)

    assert result.intent is OrbitIntent.UTILITY_TIME
    assert result.executor is OrbitExecutor.LOCAL
    assert result.confidence == 1.0
    assert result.handled is True
    assert result.message == "The current time is 3:42 PM UTC."
    assert result.timezone_name == "UTC"


def test_route_orbit_message_unknown_falls_back_to_hermes():
    result = route_orbit_message("Explain transformers.", _actor())

    assert result.intent is OrbitIntent.UNKNOWN
    assert result.executor is OrbitExecutor.HERMES
    assert result.confidence == 0.0
    assert result.handled is False
    assert result.message is None
    assert result.reason == "no_deterministic_match"
