from __future__ import annotations

from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import orbit_chat
from app.core import authentication
from app.core.authentication import create_access_token
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.ai_workflow import AIConversation, AIConversationMessage
from app.models.employee import Employee
from app.models.leave_attendance import Attendance, LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday, TimesheetEntry
from app.models.organization import Department, Designation
from app.services.orbit_agent import (
    hermes_client,
    orbit_attendance_executor,
    orbit_employee_executor,
    orbit_leave_executor,
    orbit_router,
    orbit_timesheet_executor,
)
from app.services.orbit_agent.orbit_capabilities import OrbitIntent
from app.services.orbit_agent.orbit_classifier import OrbitClassificationResult


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _employee(employee_id: str, email: str) -> Employee:
    return Employee(
        id=employee_id,
        first_name="Orbit",
        last_name="Tester",
        work_email=email,
        phone="1000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        joining_date=date(2025, 1, 1),
        date_of_joining=date(2025, 1, 1),
        department="Engineering",
        designation="Engineer",
        reporting_manager="Admin User",
        work_location="US",
    )


@pytest.fixture()
def orbit_chat_context(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Department.__table__,
            Designation.__table__,
            Employee.__table__,
            Attendance.__table__,
            LeaveType.__table__,
            LeaveBalance.__table__,
            LeaveRequest.__table__,
            CompanyHoliday.__table__,
            TimesheetEntry.__table__,
            AIConversation.__table__,
            AIConversationMessage.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    employee = _employee("orbit-1", "orbit@example.com")
    second_employee = _employee("orbit-2", "other@example.com")
    manager = Employee(
        id="orbit-manager",
        first_name="Priya",
        last_name="Shah",
        work_email="priya.shah@example.com",
        phone="1000000001",
        workforce_type="full_time",
        role="manager",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        joining_date=date(2024, 1, 1),
        department="Engineering",
        designation="Engineering Manager",
        reporting_manager="",
    )
    ravi = Employee(
        id="orbit-ravi",
        first_name="Ravi",
        last_name="Kumar",
        work_email="ravi.kumar@example.com",
        phone="1000000002",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        joining_date=date(2025, 2, 1),
        department="Engineering",
        designation="Software Engineer",
        reporting_manager="Priya Shah",
        manager_id="orbit-manager",
    )
    db.add_all([employee, second_employee, manager, ravi])
    casual = LeaveType(
        id="orbit-cl",
        name="Casual Leave",
        code="CL",
        default_days_per_year=12,
        is_paid=True,
        is_carry_forward=False,
        max_carry_forward_days=0,
        is_active=True,
        sort_order=1,
    )
    sick = LeaveType(
        id="orbit-sl",
        name="Sick Leave",
        code="SL",
        default_days_per_year=8,
        is_paid=True,
        is_carry_forward=False,
        max_carry_forward_days=0,
        is_active=True,
        sort_order=2,
    )
    db.add_all([casual, sick])
    db.flush()
    db.add(
        LeaveBalance(
            id="orbit-balance-cl",
            employee_id=employee.id,
            leave_type_id=casual.id,
            year=2026,
            total_days=12,
            used_days=2,
            carry_forward_days=0,
        )
    )
    db.add(
        LeaveBalance(
            id="orbit-balance-sl",
            employee_id=employee.id,
            leave_type_id=sick.id,
            year=2026,
            total_days=8,
            used_days=1,
            carry_forward_days=0,
        )
    )
    db.add_all(
        [
            LeaveRequest(
                id="orbit-request-pending",
                employee_id=employee.id,
                leave_type_id=casual.id,
                start_date=date(2026, 8, 25),
                end_date=date(2026, 8, 25),
                total_days=1,
                reason="Family event",
                status="pending",
                created_at=orbit_router.datetime(2026, 8, 20, 10, 0),
                updated_at=orbit_router.datetime(2026, 8, 20, 10, 0),
            ),
            LeaveRequest(
                id="orbit-request-approved",
                employee_id=employee.id,
                leave_type_id=sick.id,
                start_date=date(2026, 7, 14),
                end_date=date(2026, 7, 14),
                total_days=1,
                reason="Appointment",
                status="approved",
                created_at=orbit_router.datetime(2026, 7, 10, 9, 0),
                updated_at=orbit_router.datetime(2026, 7, 11, 9, 0),
            ),
        ]
    )
    db.add_all(
        [
            Attendance(
                id="orbit-attendance-today",
                employee_id=employee.id,
                date=date(2026, 8, 23),
                check_in=orbit_router.datetime(2026, 8, 23, 9, 4),
                check_out=None,
                total_hours=5.2,
                status="present",
                source="web",
            ),
            Attendance(
                id="orbit-attendance-yesterday",
                employee_id=employee.id,
                date=date(2026, 8, 22),
                check_in=orbit_router.datetime(2026, 8, 22, 9, 12),
                check_out=orbit_router.datetime(2026, 8, 22, 17, 8),
                total_hours=7.93,
                status="present",
                source="web",
            ),
            Attendance(
                id="orbit-attendance-monday",
                employee_id=employee.id,
                date=date(2026, 8, 17),
                check_in=None,
                check_out=None,
                total_hours=None,
                status="absent",
                source="system",
            ),
            Attendance(
                id="orbit-attendance-friday",
                employee_id=employee.id,
                date=date(2026, 8, 21),
                check_in=orbit_router.datetime(2026, 8, 21, 9, 25),
                check_out=orbit_router.datetime(2026, 8, 21, 18, 0),
                total_hours=8.58,
                status="late",
                source="web",
            ),
        ]
    )
    db.add_all(
        [
            TimesheetEntry(
                id="orbit-timesheet-current-1",
                employee_id=employee.id,
                work_date=date(2026, 8, 23),
                week_start=date(2026, 8, 23),
                entry_code="POC",
                project_name="Proof of Concept",
                hours=8,
                status="submitted",
                time_zone="UTC",
                submitted_at=orbit_router.datetime(2026, 8, 23, 12, 0),
            ),
            TimesheetEntry(
                id="orbit-timesheet-current-2",
                employee_id=employee.id,
                work_date=date(2026, 8, 24),
                week_start=date(2026, 8, 23),
                entry_code="POC",
                project_name="Proof of Concept",
                hours=7.5,
                status="submitted",
                time_zone="UTC",
                submitted_at=orbit_router.datetime(2026, 8, 24, 12, 0),
            ),
            TimesheetEntry(
                id="orbit-timesheet-current-3",
                employee_id=employee.id,
                work_date=date(2026, 8, 25),
                week_start=date(2026, 8, 23),
                entry_code="POC",
                project_name="Proof of Concept",
                hours=8,
                status="submitted",
                time_zone="UTC",
                submitted_at=orbit_router.datetime(2026, 8, 25, 12, 0),
            ),
            TimesheetEntry(
                id="orbit-timesheet-last-1",
                employee_id=employee.id,
                work_date=date(2026, 8, 16),
                week_start=date(2026, 8, 16),
                entry_code="POC",
                project_name="Proof of Concept",
                hours=8,
                status="approved",
                time_zone="UTC",
                submitted_at=orbit_router.datetime(2026, 8, 16, 12, 0),
            ),
            TimesheetEntry(
                id="orbit-timesheet-last-2",
                employee_id=employee.id,
                work_date=date(2026, 8, 17),
                week_start=date(2026, 8, 16),
                entry_code="POC",
                project_name="Proof of Concept",
                hours=8,
                status="approved",
                time_zone="UTC",
                submitted_at=orbit_router.datetime(2026, 8, 17, 12, 0),
            ),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app = FastAPI()
    app.include_router(orbit_chat.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "orbit-chat-secret-that-is-long-enough-123")
    monkeypatch.setattr(settings, "HERMES_API_URL", "http://127.0.0.1:8642/v1")
    monkeypatch.setattr(settings, "HERMES_API_KEY", "orbit-hermes-test-key")
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orbit_leave_executor, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orbit_attendance_executor, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orbit_employee_executor, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orbit_timesheet_executor, "log_audit", lambda *_args, **_kwargs: None)
    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "employee": employee,
        "second_employee": second_employee,
        "token": create_access_token(employee),
        "second_token": create_access_token(second_employee),
    }
    db.close()
    engine.dispose()


class _StubResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _StubAsyncClient:
    def __init__(self, *args, post_result=None, post_exception=None, get_result=None, **kwargs):
        self._post_result = post_result
        self._post_exception = post_exception
        self._get_result = get_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self._post_exception is not None:
            raise self._post_exception
        return self._post_result

    async def get(self, *args, **kwargs):
        return self._get_result or _StubResponse(200, {"status": "ok"})


def _assert_message_with_conversation(response, expected_message: str) -> str:
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == expected_message
    assert isinstance(body["conversation_id"], str)
    assert body["conversation_id"]
    return body["conversation_id"]


def test_orbit_chat_success_returns_assistant_message(orbit_chat_context, monkeypatch):
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "I'm Orbit AI.",
                            }
                        }
                    ]
                },
            )
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Hello, what is your role?"},
    )
    _assert_message_with_conversation(response, "I'm Orbit AI.")


def test_orbit_chat_fast_path_date_skips_hermes(orbit_chat_context, monkeypatch):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for the date fast path.")

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(
        orbit_chat,
        "classify_orbit_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Classifier should not be called for the date fast path.")
        ),
    )
    monkeypatch.setattr(
        orbit_router,
        "_current_time_in_zone",
        lambda _zone: orbit_router.datetime(2026, 8, 23, 9, 45, tzinfo=orbit_router.timezone.utc),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is today's date?"},
    )

    _assert_message_with_conversation(response, "Today is Sunday, August 23, 2026.")


def test_orbit_chat_fast_path_time_skips_hermes(orbit_chat_context, monkeypatch):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for the time fast path.")

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(
        orbit_chat,
        "classify_orbit_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Classifier should not be called for the time fast path.")
        ),
    )
    monkeypatch.setattr(
        orbit_router,
        "_current_time_in_zone",
        lambda _zone: orbit_router.datetime(2026, 8, 23, 15, 42, tzinfo=orbit_router.timezone.utc),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What time is it?"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["message"].startswith("The current time is ")
    assert body["conversation_id"]


def test_orbit_chat_common_time_variation_skips_hermes(orbit_chat_context, monkeypatch):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for the common time fast path.")

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(
        orbit_chat,
        "classify_orbit_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Classifier should not be called for the time fast path.")
        ),
    )
    monkeypatch.setattr(
        orbit_router,
        "_current_time_in_zone",
        lambda _zone: orbit_router.datetime(2026, 8, 23, 15, 42, tzinfo=orbit_router.timezone.utc),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "hey orbit what is the time now?"},
    )

    _assert_message_with_conversation(response, "The current time is 11:42 AM America/New_York.")


def test_orbit_chat_fast_path_identity_skips_hermes(orbit_chat_context, monkeypatch):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for the identity fast path.")

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(
        orbit_chat,
        "classify_orbit_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Classifier should not be called for the identity fast path.")
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Who are you?"},
    )

    body = response.json()
    assert response.status_code == 200
    assert "I'm Orbit AI" in body["message"]
    assert body["conversation_id"]


def test_orbit_chat_greeting_fast_path_skips_hermes(orbit_chat_context, monkeypatch):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for the greeting fast path.")

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(
        orbit_chat,
        "classify_orbit_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Classifier should not be called for the greeting fast path.")
        ),
    )

    examples = (
        "hi",
        "hello",
        "hey orbit",
        "good morning",
        "good afternoon",
        "good evening",
    )

    for example in examples:
        response = orbit_chat_context["client"].post(
            "/api/v1/orbit/chat",
            headers=_bearer(orbit_chat_context["token"]),
            json={"message": example},
        )

        _assert_message_with_conversation(response, "Hi! I'm Orbit AI. How can I help you?")


def test_orbit_chat_acknowledgement_fast_path_skips_hermes(orbit_chat_context, monkeypatch):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for the acknowledgement fast path.")

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(
        orbit_chat,
        "classify_orbit_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Classifier should not be called for the acknowledgement fast path.")
        ),
    )

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
        response = orbit_chat_context["client"].post(
            "/api/v1/orbit/chat",
            headers=_bearer(orbit_chat_context["token"]),
            json={"message": example},
        )

        _assert_message_with_conversation(response, "You're welcome!")


def test_orbit_chat_false_positive_time_request_falls_back_to_hermes(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.UNKNOWN,
            confidence=0.45,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hermes handled the time-history question.",
                            }
                        }
                    ]
                },
            )
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What time did I check in yesterday?"},
    )

    _assert_message_with_conversation(response, "Hermes handled the time-history question.")


def test_orbit_chat_false_positive_date_request_falls_back_to_hermes(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.UNKNOWN,
            confidence=0.45,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hermes handled the leave-date question.",
                            }
                        }
                    ]
                },
            )
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What dates are available for leave?"},
    )

    _assert_message_with_conversation(response, "Hermes handled the leave-date question.")


def test_orbit_chat_unknown_request_falls_back_to_hermes(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.UNKNOWN,
            confidence=0.45,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hermes explained transformers.",
                            }
                        }
                    ]
                },
            )
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Explain transformers."},
    )

    _assert_message_with_conversation(response, "Hermes explained transformers.")


def test_orbit_chat_greeting_and_acknowledgement_false_positives_fall_back_to_hermes(
    orbit_chat_context,
    monkeypatch,
):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.UNKNOWN,
            confidence=0.45,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hermes handled the non-fast-path request.",
                            }
                        }
                    ]
                },
            )
        ),
    )

    examples = (
        "Can you write a thank-you email?",
        "Explain why saying hello matters in customer support.",
        "Is it okay to submit my timesheet tomorrow?",
    )

    for example in examples:
        response = orbit_chat_context["client"].post(
            "/api/v1/orbit/chat",
            headers=_bearer(orbit_chat_context["token"]),
            json={"message": example},
        )

        _assert_message_with_conversation(response, "Hermes handled the non-fast-path request.")


@pytest.mark.parametrize(
    ("message", "intent", "expected_message"),
    (
        (
            "who is on bench?",
            OrbitIntent.EMS_ALLOCATION,
            "I understand you're asking about allocation information, but live allocation data isn't connected to Orbit yet.",
        ),
    ),
)
def test_orbit_chat_disabled_ems_capabilities_skip_hermes(
    orbit_chat_context,
    monkeypatch,
    message,
    intent,
    expected_message,
):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for disabled EMS capability responses.")

    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=intent,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": message},
    )

    _assert_message_with_conversation(response, expected_message)


def test_orbit_chat_timesheet_total_skips_hermes(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_TIMESHEET,
            confidence=0.97,
            reason="classified",
        )

    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for timesheet reads.")

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "How many hours did I log this week?"},
    )

    _assert_message_with_conversation(
        response,
        "You've logged 7.5 hour(s) this week.",
    )


def test_orbit_chat_timesheet_followup_uses_context_without_hermes(
    orbit_chat_context,
    monkeypatch,
):
    classifications = iter(
        [
            OrbitClassificationResult(
                intent=OrbitIntent.EMS_TIMESHEET,
                confidence=0.97,
                reason="classified",
            ),
            OrbitClassificationResult(
                intent=OrbitIntent.CONTEXT_FOLLOWUP,
                confidence=0.95,
                reason="classified",
            ),
        ]
    )

    async def fake_classifier(_message: str, *, recent_context=None):
        return next(classifications)

    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for timesheet follow-up resolution.")

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)

    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "How many hours did I log this week?"},
    )
    conversation_id = first.json()["conversation_id"]

    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What about last week?", "conversation_id": conversation_id},
    )

    _assert_message_with_conversation(second, "You've logged 8 hour(s) last week.")


def test_orbit_chat_attendance_today_uses_ems_tool_without_hermes(
    orbit_chat_context,
    monkeypatch,
):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for attendance reads.")

    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_ATTENDANCE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my attendance today?"},
    )

    _assert_message_with_conversation(
        response,
        "Your attendance for Sunday, Aug 23, 2026 is present. Check-in: 9:04 AM. Worked: 5.2 hour(s).",
    )


def test_orbit_chat_attendance_followup_date_query_stays_in_ems_tool(
    orbit_chat_context,
    monkeypatch,
):
    classifications = iter(
        [
            OrbitClassificationResult(intent=OrbitIntent.EMS_ATTENDANCE, confidence=0.97, reason="classified"),
            OrbitClassificationResult(intent=OrbitIntent.CONTEXT_FOLLOWUP, confidence=0.95, reason="classified"),
        ]
    )
    seen_contexts: list[list[tuple[str, str]]] = []

    async def fake_classifier(_message: str, *, recent_context=None):
        seen_contexts.append([(item.role, item.content) for item in (recent_context or [])])
        return next(classifications)

    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for attendance follow-up reads.")

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)

    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my attendance today?"},
    )
    conversation_id = first.json()["conversation_id"]

    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={
            "message": "What about yesterday?",
            "conversation_id": conversation_id,
        },
    )

    _assert_message_with_conversation(
        second,
        "Your attendance for Saturday, Aug 22, 2026 is present. Check-in: 9:12 AM. Check-out: 5:08 PM. Worked: 7.93 hour(s).",
    )
    assert seen_contexts[0] == []
    assert seen_contexts[1] == [
        ("user", "What is my attendance today?"),
        ("assistant", "Your attendance for Sunday, Aug 23, 2026 is present. Check-in: 9:04 AM. Worked: 5.2 hour(s)."),
    ]


def test_orbit_chat_attendance_write_request_is_blocked_without_hermes(
    orbit_chat_context,
    monkeypatch,
):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for blocked attendance writes.")

    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_ATTENDANCE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Check me in."},
    )

    _assert_message_with_conversation(
        response,
        "Orbit can currently read your attendance information, but it can't check you in, check you out, or change attendance records yet.",
    )


def test_orbit_chat_leave_balance_uses_ems_tool_without_hermes(
    orbit_chat_context,
    monkeypatch,
):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for leave balance reads.")

    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_LEAVE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my casual leave balance?"},
    )

    body = response.json()
    assert response.status_code == 200
    assert "Your Casual Leave balance for 2026 is 9 day(s) available" in body["message"]
    assert body["conversation_id"]


def test_orbit_chat_leave_followup_used_query_stays_in_ems_tool(
    orbit_chat_context,
    monkeypatch,
):
    classifications = iter(
        [
            OrbitClassificationResult(intent=OrbitIntent.EMS_LEAVE, confidence=0.97, reason="classified"),
            OrbitClassificationResult(intent=OrbitIntent.CONTEXT_FOLLOWUP, confidence=0.95, reason="classified"),
        ]
    )
    seen_contexts: list[list[tuple[str, str]]] = []

    async def fake_classifier(_message: str, *, recent_context=None):
        seen_contexts.append([(item.role, item.content) for item in (recent_context or [])])
        return next(classifications)

    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for leave follow-up reads.")

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)

    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my casual leave balance?"},
    )
    conversation_id = first.json()["conversation_id"]

    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={
            "message": "How much did I use?",
            "conversation_id": conversation_id,
        },
    )

    _assert_message_with_conversation(
        second,
        "You've used 2 day(s) of Casual Leave in 2026. You still have 9 day(s) available and 1 day(s) pending.",
    )
    assert seen_contexts[0] == []
    assert seen_contexts[1] == [
        ("user", "What is my casual leave balance?"),
        ("assistant", "Your Casual Leave balance for 2026 is 9 day(s) available, 2 day(s) used, and 1 day(s) pending out of 12 day(s) total."),
    ]


def test_orbit_chat_leave_write_request_is_blocked_without_hermes(
    orbit_chat_context,
    monkeypatch,
):
    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for blocked leave writes.")

    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_LEAVE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)
    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Submit leave for Monday."},
    )

    _assert_message_with_conversation(
        response,
        "Orbit can currently read your leave information, but it can't create, submit, cancel, or change leave requests yet.",
    )


@pytest.mark.parametrize(
    ("message", "intent", "assistant_message"),
    (
        ("help me write an email", OrbitIntent.DRAFTING, "Hermes drafted the email."),
        ("explain transformers", OrbitIntent.GENERAL_REASONING, "Hermes explained transformers."),
        ("why?", OrbitIntent.CONTEXT_FOLLOWUP, "Hermes handled the follow-up."),
    ),
)
def test_orbit_chat_classifier_routed_hermes_intents_use_hermes(
    orbit_chat_context,
    monkeypatch,
    message,
    intent,
    assistant_message,
):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=intent,
            confidence=0.96,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": assistant_message}}]},
            )
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": message},
    )

    _assert_message_with_conversation(response, assistant_message)


@pytest.mark.parametrize(
    "classification",
    (
        OrbitClassificationResult(intent=OrbitIntent.UNKNOWN, confidence=0.45, reason="classified"),
        OrbitClassificationResult(intent=OrbitIntent.EMS_LEAVE, confidence=0.55, reason="classified"),
        OrbitClassificationResult(intent=OrbitIntent.UNKNOWN, confidence=0.0, reason="classifier_timeout"),
        OrbitClassificationResult(intent=OrbitIntent.UNKNOWN, confidence=0.0, reason="classifier_transport_error"),
        OrbitClassificationResult(intent=OrbitIntent.UNKNOWN, confidence=0.0, reason="classifier_invalid_response"),
    ),
)
def test_orbit_chat_classifier_fallback_cases_use_hermes(
    orbit_chat_context,
    monkeypatch,
    classification,
):
    async def fake_classifier(_message: str, *, recent_context=None):
        return classification

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hermes handled the fallback request.",
                            }
                        }
                    ]
                },
            )
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "something ambiguous"},
    )

    _assert_message_with_conversation(response, "Hermes handled the fallback request.")


def test_orbit_chat_requires_authentication(orbit_chat_context):
    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        json={"message": "Hello"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_orbit_chat_rejects_blank_message(orbit_chat_context):
    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "   "},
    )
    assert response.status_code == 422


def test_orbit_chat_handles_hermes_unavailable(orbit_chat_context, monkeypatch):
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_exception=httpx.ConnectError("boom"),
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Please summarize this policy."},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "ORBIT_AI_UNAVAILABLE"
    assert "Hermes" not in detail["message"]
    assert "127.0.0.1" not in str(detail)


def test_orbit_chat_handles_timeout(orbit_chat_context, monkeypatch):
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_exception=httpx.TimeoutException("slow"),
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Please summarize this policy."},
    )
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "ORBIT_AI_TIMEOUT"


def test_orbit_chat_handles_http_failure(orbit_chat_context, monkeypatch):
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(502, {"error": "bad gateway"}),
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Please summarize this policy."},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ORBIT_AI_UNAVAILABLE"


def test_orbit_chat_handles_auth_failure_from_hermes(orbit_chat_context, monkeypatch):
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(401, {"error": "unauthorized"}),
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Please summarize this policy."},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ORBIT_AI_UNAVAILABLE"


def test_orbit_chat_handles_malformed_hermes_response(orbit_chat_context, monkeypatch):
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(200, {"choices": []}),
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Please summarize this policy."},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ORBIT_AI_UNAVAILABLE"


def test_orbit_chat_creates_conversation_and_persists_turns(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        assert recent_context == []
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_LEAVE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my leave balance?"},
    )

    conversation_id = _assert_message_with_conversation(
        response,
        "Your leave balances for 2026: Casual Leave: 9 day(s) available; Sick Leave: 7 day(s) available.",
    )
    conversation = orbit_chat_context["db"].query(AIConversation).filter(
        AIConversation.id == conversation_id
    ).one()
    messages = orbit_chat_context["db"].query(AIConversationMessage).filter(
        AIConversationMessage.conversation_id == conversation_id
    ).order_by(AIConversationMessage.created_at.asc()).all()

    assert conversation.owner_employee_id == orbit_chat_context["employee"].id
    assert conversation.organization_scope == "reknew"
    assert conversation.last_resolved_intent == OrbitIntent.EMS_LEAVE.value
    assert [message.role for message in messages] == ["user", "assistant"]


def test_orbit_chat_reuses_conversation_and_resolves_ems_follow_up_without_hermes(
    orbit_chat_context,
    monkeypatch,
):
    classifications = iter(
        [
            OrbitClassificationResult(
                intent=OrbitIntent.EMS_LEAVE,
                confidence=0.97,
                reason="classified",
            ),
            OrbitClassificationResult(
                intent=OrbitIntent.CONTEXT_FOLLOWUP,
                confidence=0.95,
                reason="classified",
            ),
        ]
    )
    seen_contexts: list[list[tuple[str, str]]] = []

    async def fake_classifier(_message: str, *, recent_context=None):
        context = [(item.role, item.content) for item in (recent_context or [])]
        seen_contexts.append(context)
        return next(classifications)

    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for EMS follow-up resolution.")

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)

    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my casual leave balance?"},
    )
    conversation_id = first.json()["conversation_id"]

    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={
            "message": "what about last year?",
            "conversation_id": conversation_id,
        },
    )

    _assert_message_with_conversation(
        second,
        "Orbit can currently show your current leave balances only. Historical year-specific balances aren't available here yet.",
    )
    assert second.json()["conversation_id"] == conversation_id
    assert seen_contexts[0] == []
    assert seen_contexts[1] == [
        ("user", "What is my casual leave balance?"),
        ("assistant", "Your Casual Leave balance for 2026 is 9 day(s) available, 2 day(s) used, and 1 day(s) pending out of 12 day(s) total."),
    ]


def test_orbit_chat_general_reasoning_follow_up_reaches_hermes_with_history(
    orbit_chat_context,
    monkeypatch,
):
    classifications = iter(
        [
            OrbitClassificationResult(
                intent=OrbitIntent.GENERAL_REASONING,
                confidence=0.96,
                reason="classified",
            ),
            OrbitClassificationResult(
                intent=OrbitIntent.CONTEXT_FOLLOWUP,
                confidence=0.94,
                reason="classified",
            ),
        ]
    )
    captured_payloads: list[list[dict[str, str]]] = []

    async def fake_classifier(_message: str, *, recent_context=None):
        return next(classifications)

    class _CapturingAsyncClient(_StubAsyncClient):
        async def post(self, *args, **kwargs):
            captured_payloads.append(kwargs["json"]["messages"])
            return _StubResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "Hermes reply."}}]},
            )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _CapturingAsyncClient(),
    )

    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Explain transformers."},
    )
    conversation_id = first.json()["conversation_id"]

    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={
            "message": "Can you simplify that?",
            "conversation_id": conversation_id,
        },
    )

    _assert_message_with_conversation(second, "Hermes reply.")
    assert len(captured_payloads) == 2
    assert captured_payloads[1][1:] == [
        {"role": "user", "content": "Explain transformers."},
        {"role": "assistant", "content": "Hermes reply."},
        {"role": "user", "content": "Can you simplify that?"},
    ]


def test_orbit_chat_context_followup_without_history_falls_back_to_hermes(
    orbit_chat_context,
    monkeypatch,
):
    async def fake_classifier(_message: str, *, recent_context=None):
        assert recent_context == []
        return OrbitClassificationResult(
            intent=OrbitIntent.CONTEXT_FOLLOWUP,
            confidence=0.92,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "Hermes handled the follow-up."}}]},
            )
        ),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "why?"},
    )

    _assert_message_with_conversation(response, "Hermes handled the follow-up.")


def test_orbit_chat_topic_switch_updates_last_meaningful_intent(
    orbit_chat_context,
    monkeypatch,
):
    classifications = iter(
        [
            OrbitClassificationResult(intent=OrbitIntent.EMS_LEAVE, confidence=0.97, reason="classified"),
            OrbitClassificationResult(intent=OrbitIntent.EMS_ALLOCATION, confidence=0.97, reason="classified"),
            OrbitClassificationResult(intent=OrbitIntent.CONTEXT_FOLLOWUP, confidence=0.95, reason="classified"),
        ]
    )

    async def fake_classifier(_message: str, *, recent_context=None):
        return next(classifications)

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "Hermes fallback."}}]},
            )
        ),
    )

    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my leave balance?"},
    )
    conversation_id = first.json()["conversation_id"]
    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "who is on bench?", "conversation_id": conversation_id},
    )
    third = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "and mine?", "conversation_id": conversation_id},
    )

    _assert_message_with_conversation(
        second,
        "I understand you're asking about allocation information, but live allocation data isn't connected to Orbit yet.",
    )
    _assert_message_with_conversation(
        third,
        "I understand you're asking about allocation information, but live allocation data isn't connected to Orbit yet.",
    )
    conversation = orbit_chat_context["db"].query(AIConversation).filter(
        AIConversation.id == conversation_id
    ).one()
    assert conversation.last_resolved_intent == OrbitIntent.EMS_ALLOCATION.value


def test_orbit_chat_prevents_cross_user_conversation_access(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_LEAVE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my leave balance?"},
    )
    conversation_id = first.json()["conversation_id"]

    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["second_token"]),
        json={"message": "what about last year?", "conversation_id": conversation_id},
    )

    assert second.status_code == 404
    assert second.json()["detail"]["code"] == "CONVERSATION_NOT_FOUND"


def test_orbit_chat_prevents_cross_organization_conversation_access(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_LEAVE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my leave balance?"},
    )
    conversation_id = first.json()["conversation_id"]

    monkeypatch.setattr(settings, "AUTH_ORGANIZATION_SCOPE", "other-org")
    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "what about last year?", "conversation_id": conversation_id},
    )

    assert second.status_code == 404
    assert second.json()["detail"]["code"] == "CONVERSATION_NOT_FOUND"


def test_orbit_chat_bounded_history_only_supplies_latest_messages(orbit_chat_context, monkeypatch):
    monkeypatch.setattr(settings, "ORBIT_CONTEXT_MAX_MESSAGES", 4)
    classifications = iter(
        [
            OrbitClassificationResult(intent=OrbitIntent.GENERAL_REASONING, confidence=0.96, reason="classified"),
            OrbitClassificationResult(intent=OrbitIntent.GENERAL_REASONING, confidence=0.96, reason="classified"),
            OrbitClassificationResult(intent=OrbitIntent.GENERAL_REASONING, confidence=0.96, reason="classified"),
        ]
    )
    captured_contexts: list[list[tuple[str, str]]] = []

    async def fake_classifier(_message: str, *, recent_context=None):
        captured_contexts.append([(item.role, item.content) for item in (recent_context or [])])
        return next(classifications)

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        hermes_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _StubAsyncClient(
            post_result=_StubResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "Hermes reply."}}]},
            )
        ),
    )

    conversation_id = None
    for message in ("Explain A", "Explain B", "Explain C"):
        response = orbit_chat_context["client"].post(
            "/api/v1/orbit/chat",
            headers=_bearer(orbit_chat_context["token"]),
            json={
                "message": message,
                **({"conversation_id": conversation_id} if conversation_id else {}),
            },
        )
        conversation_id = response.json()["conversation_id"]

    assert captured_contexts[0] == []
    assert len(captured_contexts[2]) == 4
    assert captured_contexts[2] == [
        ("user", "Explain A"),
        ("assistant", "Hermes reply."),
        ("user", "Explain B"),
        ("assistant", "Hermes reply."),
    ]


def test_orbit_chat_context_load_failure_falls_back_to_context_free_behavior(
    orbit_chat_context,
    monkeypatch,
):
    async def fake_classifier(_message: str, *, recent_context=None):
        assert recent_context == []
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_LEAVE,
            confidence=0.97,
            reason="classified",
        )

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(
        orbit_chat,
        "list_recent_messages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("history unavailable")),
    )

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "What is my leave balance?"},
    )

    _assert_message_with_conversation(
        response,
        "Your leave balances for 2026: Casual Leave: 9 day(s) available; Sick Leave: 7 day(s) available.",
    )


def test_orbit_chat_employee_lookup_skips_hermes(orbit_chat_context, monkeypatch):
    async def fake_classifier(_message: str, *, recent_context=None):
        return OrbitClassificationResult(
            intent=OrbitIntent.EMS_EMPLOYEE,
            confidence=0.97,
            reason="classified",
        )

    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for employee lookup.")

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)

    response = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Who is Ravi Kumar?"},
    )

    _assert_message_with_conversation(
        response,
        "Ravi Kumar is Software Engineer in the Engineering department.",
    )


def test_orbit_chat_employee_followup_resolves_manager_without_hermes(
    orbit_chat_context,
    monkeypatch,
):
    classifications = iter(
        [
            OrbitClassificationResult(
                intent=OrbitIntent.EMS_EMPLOYEE,
                confidence=0.97,
                reason="classified",
            ),
            OrbitClassificationResult(
                intent=OrbitIntent.CONTEXT_FOLLOWUP,
                confidence=0.95,
                reason="classified",
            ),
        ]
    )

    async def fake_classifier(_message: str, *, recent_context=None):
        return next(classifications)

    def fail_async_client(*args, **kwargs):
        raise AssertionError("Hermes client should not be called for employee follow-up resolution.")

    monkeypatch.setattr(orbit_chat, "classify_orbit_message", fake_classifier)
    monkeypatch.setattr(hermes_client.httpx, "AsyncClient", fail_async_client)

    first = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Find Ravi Kumar"},
    )
    conversation_id = first.json()["conversation_id"]

    second = orbit_chat_context["client"].post(
        "/api/v1/orbit/chat",
        headers=_bearer(orbit_chat_context["token"]),
        json={"message": "Who is his manager?", "conversation_id": conversation_id},
    )

    _assert_message_with_conversation(second, "Ravi Kumar reports to Priya Shah.")
