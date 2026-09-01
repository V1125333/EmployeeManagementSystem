from __future__ import annotations

import asyncio
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.authentication import AuthenticatedActor, AuthenticatedPrincipal
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.organization import Department, Designation
from app.services.orbit_agent import orbit_leave_executor
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage
from app.services.orbit_agent.orbit_leave_executor import (
    OrbitLeaveOperation,
    execute_leave_read,
)


def _employee(employee_id: str = "leave-user") -> Employee:
    return Employee(
        id=employee_id,
        first_name="Orbit",
        last_name="Leave",
        work_email=f"{employee_id}@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        joining_date=date(2025, 1, 1),
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
        permissions=frozenset(
            {
                "leave.balance.read.self",
                "leave.request.read.self",
            }
        ),
        token_id="token-1",
        access_level="standard",
        manager_id=None,
        department_id=None,
        organization_scope="reknew",
    )
    return AuthenticatedActor(principal=principal, employee=employee)


@pytest.fixture()
def leave_executor_context(monkeypatch):
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
            LeaveBalance.__table__,
            LeaveRequest.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    employee = _employee()
    other = _employee("other-user")
    db.add_all([employee, other])
    casual = LeaveType(
        id="leave-cl",
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
        id="leave-sl",
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
    db.add_all(
        [
            LeaveBalance(
                id="lb-cl",
                employee_id=employee.id,
                leave_type_id=casual.id,
                year=2026,
                total_days=12,
                used_days=3,
                carry_forward_days=0,
            ),
            LeaveBalance(
                id="lb-sl",
                employee_id=employee.id,
                leave_type_id=sick.id,
                year=2026,
                total_days=8,
                used_days=1,
                carry_forward_days=0,
            ),
            LeaveRequest(
                id="lr-pending",
                employee_id=employee.id,
                leave_type_id=casual.id,
                start_date=date(2026, 8, 25),
                end_date=date(2026, 8, 25),
                total_days=1,
                reason="Family event",
                status="pending",
                created_at=datetime(2026, 8, 20, 10, 0),
                updated_at=datetime(2026, 8, 20, 10, 0),
            ),
            LeaveRequest(
                id="lr-approved",
                employee_id=employee.id,
                leave_type_id=sick.id,
                start_date=date(2026, 7, 14),
                end_date=date(2026, 7, 14),
                total_days=1,
                reason="Appointment",
                status="approved",
                created_at=datetime(2026, 7, 10, 9, 0),
                updated_at=datetime(2026, 7, 11, 9, 0),
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(orbit_leave_executor, "log_audit", lambda *_args, **_kwargs: None)
    yield {
        "db": db,
        "employee": employee,
        "actor": _actor(employee),
    }
    db.close()
    engine.dispose()


def test_execute_leave_read_returns_grounded_balance(leave_executor_context):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="What is my casual leave balance?",
        )
    )

    assert result.operation is OrbitLeaveOperation.LEAVE_BALANCE
    assert result.message == (
        "Your Casual Leave balance for 2026 is 8 day(s) available, 3 day(s) used, "
        "and 1 day(s) pending out of 12 day(s) total."
    )


def test_execute_leave_read_returns_recent_history(leave_executor_context):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="Show my recent leave requests.",
        )
    )

    assert result.operation is OrbitLeaveOperation.LEAVE_HISTORY
    assert "Your recent leave requests:" in result.message
    assert "Casual Leave (pending, Aug 25, 2026, 1 day(s))" in result.message


def test_execute_leave_read_returns_latest_status(leave_executor_context):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="What is the status of my leave request?",
        )
    )

    assert result.operation is OrbitLeaveOperation.LEAVE_STATUS
    assert result.message == (
        "Your latest matching leave request is pending: Casual Leave for Aug 25, 2026 "
        "(1 day(s)). It is currently pending with Admin User."
    )


def test_execute_leave_read_uses_context_for_followup_operation_and_type(
    leave_executor_context,
):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="How much did I use?",
            conversation_context=[
                OrbitContextMessage(role="user", content="What is my casual leave balance?"),
                OrbitContextMessage(
                    role="assistant",
                    content="Your Casual Leave balance for 2026 is 8 day(s) available, 3 day(s) used, and 1 day(s) pending out of 12 day(s) total.",
                ),
            ],
        )
    )

    assert result.operation is OrbitLeaveOperation.LEAVE_USED
    assert result.message == (
        "You've used 3 day(s) of Casual Leave in 2026. You still have 8 day(s) available and 1 day(s) pending."
    )


def test_execute_leave_read_blocks_write_requests(leave_executor_context):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="Apply leave tomorrow.",
        )
    )

    assert result.operation is OrbitLeaveOperation.WRITE_REQUEST
    assert "can't create, submit, cancel, or change leave requests yet" in result.message


def test_execute_leave_read_refuses_third_party_access(leave_executor_context):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="Show another employee's leave balance.",
        )
    )

    assert result.operation is OrbitLeaveOperation.UNKNOWN_LEAVE_QUERY
    assert result.message == "Orbit can currently access only your own leave information."


def test_execute_leave_read_handles_no_matching_history(leave_executor_context):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="Show my rejected leave requests.",
        )
    )

    assert result.operation is OrbitLeaveOperation.LEAVE_HISTORY
    assert result.message == "You don't have any matching leave requests."


def test_execute_leave_read_handles_service_failure_safely(
    leave_executor_context,
    monkeypatch,
):
    monkeypatch.setattr(
        orbit_leave_executor,
        "get_my_leave_balances",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="What is my leave balance?",
        )
    )

    assert result.operation is OrbitLeaveOperation.LEAVE_BALANCE
    assert result.message == "Your leave information is temporarily unavailable."


def test_execute_leave_read_handles_historical_balance_followup_conservatively(
    leave_executor_context,
):
    result = asyncio.run(
        execute_leave_read(
            db=leave_executor_context["db"],
            actor=leave_executor_context["actor"],
            query="What about last year?",
            conversation_context=[
                OrbitContextMessage(role="user", content="What is my casual leave balance?"),
                OrbitContextMessage(role="assistant", content="Previous answer"),
            ],
        )
    )

    assert result.operation is OrbitLeaveOperation.LEAVE_BALANCE
    assert "Historical year-specific balances aren't available here yet." in result.message
