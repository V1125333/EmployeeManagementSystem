from __future__ import annotations

import asyncio
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.authentication import AuthenticatedActor, AuthenticatedPrincipal
from app.core.database import Base
from app.models.employee import Employee
from app.models.leave_attendance import Attendance
from app.models.organization import Department, Designation
from app.services.orbit_agent import orbit_attendance_executor
from app.services.orbit_agent.orbit_attendance_executor import (
    OrbitAttendanceOperation,
    execute_attendance_read,
)
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage


def _employee(employee_id: str = "attendance-user") -> Employee:
    return Employee(
        id=employee_id,
        first_name="Orbit",
        last_name="Attendance",
        work_email=f"{employee_id}@example.com",
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
    )


def _actor(employee: Employee) -> AuthenticatedActor:
    principal = AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role="employee",
        status="active",
        permissions=frozenset({"attendance.read.self"}),
        token_id="token-1",
        access_level="standard",
        manager_id=None,
        department_id=None,
        organization_scope="reknew",
    )
    return AuthenticatedActor(principal=principal, employee=employee)


@pytest.fixture()
def attendance_executor_context(monkeypatch):
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
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    employee = _employee()
    db.add(employee)
    db.add_all(
        [
            Attendance(
                id="attendance-today",
                employee_id=employee.id,
                date=date(2026, 8, 23),
                check_in=datetime(2026, 8, 23, 9, 4),
                check_out=None,
                total_hours=5.2,
                status="present",
                source="web",
            ),
            Attendance(
                id="attendance-yesterday",
                employee_id=employee.id,
                date=date(2026, 8, 22),
                check_in=datetime(2026, 8, 22, 9, 12),
                check_out=datetime(2026, 8, 22, 17, 8),
                total_hours=7.93,
                status="present",
                source="web",
            ),
            Attendance(
                id="attendance-monday",
                employee_id=employee.id,
                date=date(2026, 8, 17),
                check_in=None,
                check_out=None,
                total_hours=None,
                status="absent",
                source="system",
            ),
            Attendance(
                id="attendance-friday",
                employee_id=employee.id,
                date=date(2026, 8, 21),
                check_in=datetime(2026, 8, 21, 9, 25),
                check_out=datetime(2026, 8, 21, 18, 0),
                total_hours=8.58,
                status="late",
                source="web",
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(orbit_attendance_executor, "log_audit", lambda *_args, **_kwargs: None)
    yield {"db": db, "actor": _actor(employee)}
    db.close()
    engine.dispose()


def test_execute_attendance_read_returns_today(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="What is my attendance today?",
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_TODAY
    assert result.message == (
        "Your attendance for Sunday, Aug 23, 2026 is present. Check-in: 9:04 AM. Worked: 5.2 hour(s)."
    )


def test_execute_attendance_read_returns_specific_day(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="Was I present yesterday?",
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_DATE
    assert result.message == (
        "Your attendance for Saturday, Aug 22, 2026 is present. Check-in: 9:12 AM. Check-out: 5:08 PM. Worked: 7.93 hour(s)."
    )


def test_execute_attendance_read_returns_recent(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="Show my recent attendance.",
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_RECENT
    assert "2026-08-23: present" in result.message
    assert "2026-08-17: absent" in result.message


def test_execute_attendance_read_returns_week_summary(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="Show my attendance this week.",
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_SUMMARY
    assert result.message == (
        "Your attendance summary for this week: 3 present or working-from-home day(s), 1 absent day(s), and 1 late day(s), based on 4 recorded day(s)."
    )


def test_execute_attendance_read_returns_present_count(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="How many days was I present this week?",
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_PRESENT_COUNT
    assert result.message == "You were present or working from home for 3 recorded day(s) in this week."


def test_execute_attendance_read_returns_absent_count(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="How many days was I absent this week?",
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_ABSENT_COUNT
    assert result.message == "You were absent for 1 recorded day(s) in this week."


def test_execute_attendance_read_blocks_write_requests(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="Fix yesterday's attendance.",
        )
    )

    assert result.operation is OrbitAttendanceOperation.WRITE_REQUEST
    assert "can't check you in, check you out, or change attendance records yet" in result.message


def test_execute_attendance_read_uses_followup_context(attendance_executor_context):
    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="What about yesterday?",
            recent_context=[
                OrbitContextMessage(role="user", content="What is my attendance today?"),
                OrbitContextMessage(role="assistant", content="Previous answer"),
            ],
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_DATE
    assert result.message == (
        "Your attendance for Saturday, Aug 22, 2026 is present. Check-in: 9:12 AM. Check-out: 5:08 PM. Worked: 7.93 hour(s)."
    )


def test_execute_attendance_read_handles_service_failure_safely(
    attendance_executor_context,
    monkeypatch,
):
    monkeypatch.setattr(
        orbit_attendance_executor,
        "get_my_attendance_today",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    result = asyncio.run(
        execute_attendance_read(
            db=attendance_executor_context["db"],
            actor=attendance_executor_context["actor"],
            query="What is my attendance today?",
        )
    )

    assert result.operation is OrbitAttendanceOperation.ATTENDANCE_TODAY
    assert result.message == "Your attendance information is temporarily unavailable."
