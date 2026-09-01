from __future__ import annotations

import asyncio
from datetime import date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.authentication import AuthenticatedActor, AuthenticatedPrincipal
from app.core.database import Base
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday, TimesheetEntry
from app.models.organization import Department, Designation
from app.services.orbit_agent import orbit_timesheet_executor
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage
from app.services.orbit_agent.orbit_timesheet_executor import (
    OrbitTimesheetOperation,
    execute_timesheet_read,
)


CURRENT_WEEK = date(2026, 8, 23)
LAST_WEEK = date(2026, 8, 16)


def _employee(employee_id: str = "timesheet-user") -> Employee:
    return Employee(
        id=employee_id,
        first_name="Orbit",
        last_name="Timesheet",
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
        work_location="US",
    )


def _actor(employee: Employee) -> AuthenticatedActor:
    principal = AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role="employee",
        status="active",
        permissions=frozenset({"timesheet.read.self"}),
        token_id="token-1",
        access_level="standard",
        manager_id=None,
        department_id=None,
        organization_scope="reknew",
    )
    return AuthenticatedActor(principal=principal, employee=employee)


def _entry(
    employee_id: str,
    *,
    work_date: date,
    week_start: date,
    hours: float,
    status: str,
    suffix: str,
) -> TimesheetEntry:
    return TimesheetEntry(
        id=f"ts-{suffix}",
        employee_id=employee_id,
        work_date=work_date,
        week_start=week_start,
        entry_code="POC",
        project_name="Proof of Concept",
        start_time=time(9, 0),
        end_time=time(9 + int(hours), 0) if hours.is_integer() else time(17, 30),
        hours=hours,
        status=status,
        time_zone="UTC",
        submitted_at=datetime(2026, 8, 23, 12, 0) if status in {"submitted", "approved", "rejected"} else None,
    )


@pytest.fixture()
def timesheet_executor_context(monkeypatch):
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
            LeaveType.__table__,
            LeaveRequest.__table__,
            CompanyHoliday.__table__,
            TimesheetEntry.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    employee = _employee()
    other = _employee("other-user")
    db.add_all([employee, other])
    db.add_all(
        [
            _entry(employee.id, work_date=date(2026, 8, 23), week_start=CURRENT_WEEK, hours=8.0, status="submitted", suffix="today"),
            _entry(employee.id, work_date=date(2026, 8, 24), week_start=CURRENT_WEEK, hours=7.5, status="submitted", suffix="current-1"),
            _entry(employee.id, work_date=date(2026, 8, 25), week_start=CURRENT_WEEK, hours=8.0, status="submitted", suffix="current-2"),
            _entry(employee.id, work_date=date(2026, 8, 16), week_start=LAST_WEEK, hours=8.0, status="approved", suffix="last-1"),
            _entry(employee.id, work_date=date(2026, 8, 17), week_start=LAST_WEEK, hours=8.0, status="approved", suffix="last-2"),
            _entry(employee.id, work_date=date(2026, 8, 18), week_start=LAST_WEEK, hours=8.0, status="approved", suffix="last-3"),
        ]
    )
    db.commit()
    monkeypatch.setattr(orbit_timesheet_executor, "log_audit", lambda *_args, **_kwargs: None)
    yield {"db": db, "actor": _actor(employee)}
    db.close()
    engine.dispose()


def test_execute_timesheet_read_returns_today_hours(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="How many hours did I log today?",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_TODAY
    assert result.message == "You've logged 8 hour(s) today."


def test_execute_timesheet_read_returns_week_total(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="How many hours did I log this week?",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_TOTAL_HOURS
    assert result.message == "You've logged 15.5 hour(s) this week."


def test_execute_timesheet_read_returns_last_week_total(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="How many hours did I log last week?",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_TOTAL_HOURS
    assert result.message == "You've logged 16 hour(s) last week."


def test_execute_timesheet_read_returns_week_details(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="Show my timesheet this week.",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_WEEK
    assert "Your timesheet for 2026-08-23 to 2026-08-29:" in result.message
    assert "Total: 15.5 hour(s). Status: submitted." in result.message


def test_execute_timesheet_read_returns_recent_history(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="Show my recent timesheets.",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_RECENT
    assert "2026-08-23 to 2026-08-29: 15.5 hour(s) (submitted)" in result.message
    assert "2026-08-16 to 2026-08-22: 16 hour(s) (approved)" in result.message


def test_execute_timesheet_read_returns_status(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="Did I submit my timesheet?",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_STATUS
    assert result.message == "Your timesheet for 2026-08-23 to 2026-08-29 is submitted."


def test_execute_timesheet_read_handles_no_entry_for_day(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="How many hours did I log yesterday?",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_DAY
    assert result.message == "I don't see a timesheet entry for 2026-08-22."


def test_execute_timesheet_read_blocks_write_requests(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="Submit my timesheet.",
        )
    )

    assert result.operation is OrbitTimesheetOperation.WRITE_REQUEST
    assert "adding, changing, or submitting timesheets through Orbit isn't enabled yet" in result.message


def test_execute_timesheet_read_blocks_third_party_requests(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="Show Ravi's timesheet.",
        )
    )

    assert result.operation is OrbitTimesheetOperation.UNKNOWN_TIMESHEET_QUERY
    assert result.message == "Orbit can currently access only your own timesheet information."


def test_execute_timesheet_read_uses_followup_context_for_last_week(timesheet_executor_context):
    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="What about last week?",
            recent_context=[
                OrbitContextMessage(role="user", content="How many hours did I log this week?"),
                OrbitContextMessage(role="assistant", content="You've logged 15.5 hour(s) this week."),
            ],
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_TOTAL_HOURS
    assert result.message == "You've logged 16 hour(s) last week."


def test_execute_timesheet_read_handles_service_failure_safely(timesheet_executor_context, monkeypatch):
    monkeypatch.setattr(
        orbit_timesheet_executor.timesheet_api,
        "load_week_entries",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    result = asyncio.run(
        execute_timesheet_read(
            db=timesheet_executor_context["db"],
            actor=timesheet_executor_context["actor"],
            query="How many hours did I log this week?",
        )
    )

    assert result.operation is OrbitTimesheetOperation.TIMESHEET_TOTAL_HOURS
    assert result.message == "I couldn't retrieve your timesheet information right now."
