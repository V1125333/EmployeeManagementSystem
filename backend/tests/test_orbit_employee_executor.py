from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.authentication import AuthenticatedActor, AuthenticatedPrincipal
from app.core.database import Base
from app.models.employee import Employee
from app.models.organization import Department, Designation
from app.services.orbit_agent import orbit_employee_executor
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage
from app.services.orbit_agent.orbit_employee_executor import (
    OrbitEmployeeOperation,
    execute_employee_read,
)


def _employee(
    employee_id: str,
    first_name: str,
    last_name: str,
    *,
    role: str = "employee",
    department: str = "Engineering",
    designation: str = "Software Engineer",
    manager_id: str | None = None,
    reporting_manager: str = "",
    work_email: str | None = None,
) -> Employee:
    return Employee(
        id=employee_id,
        first_name=first_name,
        last_name=last_name,
        work_email=work_email or f"{employee_id}@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role=role,
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        joining_date=date(2025, 1, 1),
        department=department,
        designation=designation,
        reporting_manager=reporting_manager,
        manager_id=manager_id,
    )


def _actor(employee: Employee) -> AuthenticatedActor:
    principal = AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role=employee.role,
        status="active",
        permissions=frozenset({"employee.directory.read", "employee.manager.read.self"}),
        token_id="token-1",
        access_level="standard",
        manager_id=employee.manager_id,
        department_id=None,
        organization_scope="reknew",
    )
    return AuthenticatedActor(principal=principal, employee=employee)


@pytest.fixture()
def employee_executor_context(monkeypatch):
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
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    engineering = Department(id="dept-eng", name="Engineering", code="ENG", is_active=True)
    finance = Department(id="dept-fin", name="Finance", code="FIN", is_active=True)
    manager_title = Designation(id="des-mgr", name="Engineering Manager", level=4, is_active=True)
    engineer_title = Designation(id="des-se", name="Software Engineer", level=2, is_active=True)
    lead_title = Designation(id="des-fin", name="Finance Manager", level=4, is_active=True)
    db.add_all([engineering, finance, manager_title, engineer_title, lead_title])
    db.flush()

    manager = _employee(
        "manager-1",
        "Priya",
        "Shah",
        role="manager",
        designation="Engineering Manager",
        manager_id=None,
        department="Engineering",
        work_email="priya.shah@example.com",
    )
    manager.department_id = engineering.id
    manager.designation_id = manager_title.id

    actor_employee = _employee(
        "employee-1",
        "Asha",
        "Rao",
        manager_id=manager.id,
        reporting_manager="Priya Shah",
        department="Engineering",
        designation="Software Engineer",
        work_email="asha.rao@example.com",
    )
    actor_employee.department_id = engineering.id
    actor_employee.designation_id = engineer_title.id

    ravi = _employee(
        "employee-2",
        "Ravi",
        "Kumar",
        department="Engineering",
        designation="Software Engineer",
        manager_id=manager.id,
        reporting_manager="Priya Shah",
        work_email="ravi.kumar@example.com",
    )
    ravi.department_id = engineering.id
    ravi.designation_id = engineer_title.id

    ravi_finance = _employee(
        "employee-3",
        "Ravi",
        "Sharma",
        department="Finance",
        designation="Finance Manager",
        work_email="ravi.sharma@example.com",
    )
    ravi_finance.department_id = finance.id
    ravi_finance.designation_id = lead_title.id

    db.add_all([manager, actor_employee, ravi, ravi_finance])
    db.commit()
    monkeypatch.setattr(orbit_employee_executor, "log_audit", lambda *_args, **_kwargs: None)
    yield {"db": db, "actor": _actor(actor_employee), "ravi": ravi}
    db.close()
    engine.dispose()


def test_execute_employee_read_returns_safe_profile(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="Who is Ravi Kumar?",
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_PROFILE
    assert result.message == "Ravi Kumar is Software Engineer in the Engineering department."


def test_execute_employee_read_returns_department(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="What department is Ravi Kumar in?",
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_DEPARTMENT
    assert result.message == "Ravi Kumar is in the Engineering department."


def test_execute_employee_read_returns_title(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="What is Ravi Kumar's job title?",
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_TITLE
    assert result.message == "Ravi Kumar's job title is Software Engineer."


def test_execute_employee_read_returns_manager_for_self(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="Who is my manager?",
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_MANAGER
    assert result.message == "Your manager is Priya Shah, Engineering Manager. You can reach them at priya.shah@example.com."


def test_execute_employee_read_uses_recent_context_for_followup(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="Who is his manager?",
            recent_context=[
                OrbitContextMessage(role="user", content="Find Ravi Kumar"),
                OrbitContextMessage(role="assistant", content="Ravi Kumar is Software Engineer in the Engineering department."),
            ],
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_MANAGER
    assert result.message == "Ravi Kumar reports to Priya Shah."


def test_execute_employee_read_returns_multiple_matches(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="Find Ravi",
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_PROFILE
    assert result.message.startswith("I found multiple matches:")
    assert "Ravi Kumar — Engineering, Software Engineer" in result.message
    assert "Ravi Sharma — Finance, Finance Manager" in result.message


def test_execute_employee_read_blocks_sensitive_field_requests(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="What is Ravi Kumar's salary?",
        )
    )

    assert result.operation is OrbitEmployeeOperation.SENSITIVE_FIELD_REQUEST
    assert "can't share that field" in result.message


def test_execute_employee_read_blocks_write_requests(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="Change Ravi Kumar's department to Finance.",
        )
    )

    assert result.operation is OrbitEmployeeOperation.WRITE_REQUEST
    assert "changing employee records through Orbit isn't enabled yet" in result.message


def test_execute_employee_read_returns_not_found(employee_executor_context):
    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="Show me John Smith",
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_PROFILE
    assert result.message == 'I couldn\'t find an employee matching "john smith".'


def test_execute_employee_read_handles_service_failure_safely(employee_executor_context, monkeypatch):
    monkeypatch.setattr(
        orbit_employee_executor,
        "_lookup_profiles",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    result = asyncio.run(
        execute_employee_read(
            db=employee_executor_context["db"],
            actor=employee_executor_context["actor"],
            query="Who is Ravi Kumar?",
        )
    )

    assert result.operation is OrbitEmployeeOperation.EMPLOYEE_PROFILE
    assert result.message == "I couldn't retrieve employee information right now."
