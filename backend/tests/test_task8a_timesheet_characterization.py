"""Task 8A characterization of the legacy row-based timesheet workflow.

These tests deliberately preserve several defects.  Tests whose names contain
``current`` document behavior that Task 8E is expected to replace.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import admin_time_off, timesheets
from app.core.authentication import AuthenticatedActor, AuthenticatedPrincipal
from app.core.database import Base
from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday, Notification, Project, TimesheetEntry
from app.models.organization import Department, Designation


WEEK = date(2026, 7, 26)
NEXT_WEEK = date(2026, 8, 2)


class CountingSession(SASession):
    commit_count = 0

    def commit(self):
        self.commit_count += 1
        return super().commit()


def _employee(employee_id: str, role: str, *, manager_id: str | None = None) -> Employee:
    return Employee(
        id=employee_id,
        first_name=employee_id.replace("-", " ").title(),
        last_name="User",
        work_email=f"{employee_id}@example.com",
        phone=f"555{len(employee_id):07d}",
        workforce_type="full_time",
        role=role,
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        manager_id=manager_id,
        reporting_manager="Manager User" if manager_id else "",
        joining_date=date(2025, 1, 1),
        date_of_joining=date(2025, 1, 1),
        work_location="US",
    )


def _actor(employee: Employee) -> AuthenticatedActor:
    return AuthenticatedActor(
        principal=AuthenticatedPrincipal(
            employee_id=employee.id,
            email=employee.work_email,
            role=employee.role,
            status="active",
            permissions=frozenset(),
            token_id=f"token-{employee.id}",
            manager_id=employee.manager_id,
        ),
        employee=employee,
    )


def _payload(week: date = WEEK, *, notes: str = "characterization") -> timesheets.TimesheetSaveRequest:
    return timesheets.TimesheetSaveRequest(
        week_start=week,
        time_zone="UTC",
        entries=[timesheets.TimesheetEntryPayload(
            work_date=date.fromordinal(week.toordinal() + 1),
            entry_code="POC",
            project_name="Proof of Concept",
            start_time=time(9),
            end_time=time(17),
            notes=notes,
        )],
    )


def _entry(employee_id: str, status: str, *, week: date = WEEK, suffix: str = "one") -> TimesheetEntry:
    return TimesheetEntry(
        id=f"entry-{employee_id}-{suffix}",
        employee_id=employee_id,
        work_date=date.fromordinal(week.toordinal() + 1),
        week_start=week,
        entry_code="ADM",
        project_name="Admin",
        start_time=time(9),
        end_time=time(17),
        hours=8,
        status=status,
        time_zone="UTC",
        submitted_at=datetime.utcnow() if status in {"submitted", "approved", "rejected"} else None,
    )


@pytest.fixture()
def timesheet_context(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Department.__table__, Designation.__table__, Employee.__table__, Project.__table__,
        Allocation.__table__, TimesheetEntry.__table__, CompanyHoliday.__table__,
        LeaveType.__table__, LeaveRequest.__table__, Notification.__table__,
    ])
    Session = sessionmaker(
        bind=engine,
        class_=CountingSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    employees = {
        "employee": _employee("employee", "employee", manager_id="manager"),
        "manager": _employee("manager", "manager"),
        "other_manager": _employee("other-manager", "manager"),
        "admin": _employee("admin", "admin"),
    }
    with Session() as db:
        db.add_all(employees.values())
        db.commit()

    audits: list[dict] = []

    def capture_audit(_db, actor, **kwargs):
        audits.append({"actor": actor.id if actor else None, **kwargs})

    monkeypatch.setattr(timesheets, "log_audit", capture_audit)
    monkeypatch.setattr(timesheets, "log_authorization_failure", capture_audit)
    yield {"Session": Session, "employees": employees, "audits": audits, "monkeypatch": monkeypatch}
    engine.dispose()


def _run(awaitable):
    return asyncio.run(awaitable)


def test_saving_new_replacing_draft_and_saving_over_rejected_week(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        created = _run(timesheets.save_my_timesheet_week(_payload(notes="first"), db, actor))
        assert created.status == "draft"
        assert created.entries[0].notes == "first"
        assert db.query(TimesheetEntry).count() == 1

        replaced = _run(timesheets.save_my_timesheet_week(_payload(notes="replacement"), db, actor))
        assert replaced.entries[0].notes == "replacement"
        assert db.query(TimesheetEntry).count() == 1

        db.query(TimesheetEntry).update({"status": "rejected"})
        db.commit()
        corrected = _run(timesheets.save_my_timesheet_week(_payload(notes="corrected"), db, actor))
        assert corrected.status == "draft"
        assert corrected.entries[0].notes == "corrected"
        assert db.query(TimesheetEntry).count() == 1


def test_options_and_empty_week_current_read_contracts(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        options = _run(timesheets.my_timesheet_options(WEEK, db, actor))
        week = _run(timesheets.my_timesheet_week(WEEK, db, actor))
        assert options["requires_timesheet"] is True
        assert {item["code"] for item in options["entry_codes"]} >= {"PRJ", "POC", "BRK"}
        assert week.status == "not_started"
        assert week.entries == []


@pytest.mark.parametrize("status", ["submitted", "approved"])
def test_saving_submitted_or_approved_week_is_rejected(timesheet_context, status):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.add(_entry("employee", status))
        db.commit()
        with pytest.raises(HTTPException) as error:
            _run(timesheets.save_my_timesheet_week(_payload(), db, actor))
        assert error.value.status_code == 400


def test_copying_valid_week_replaces_target_with_drafts(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.add(_entry("employee", "approved"))
        db.commit()
        result = _run(timesheets.copy_my_timesheet_week(
            timesheets.TimesheetCopyRequest(source_week_start=WEEK, target_week_start=NEXT_WEEK), db, actor,
        ))
        assert result.status == "draft"
        assert result.entries[0].work_date == date(2026, 8, 3)


def test_current_copy_allows_target_dates_after_allocation_expired(timesheet_context):
    """Known defect: copy does not rerun per-entry allocation validation."""
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.add(Project(id="project", name="Project", code="PRJ1", status="active", project_manager_id="manager"))
        db.add(Allocation(
            id="allocation", employee_id="employee", project_id="project", project_name="Project",
            manager_id="manager", allocation_percentage=100, allocation_role="Engineer",
            billing_type="billable", status="active", start_date=WEEK, end_date=date(2026, 7, 31),
            created_by="admin",
        ))
        source = _entry("employee", "approved")
        source.entry_code = "PRJ"
        source.project_id = "project"
        source.project_name = "Project"
        db.add(source)
        db.commit()
        result = _run(timesheets.copy_my_timesheet_week(
            timesheets.TimesheetCopyRequest(source_week_start=WEEK, target_week_start=NEXT_WEEK), db, actor,
        ))
        assert result.status == "draft"
        assert result.entries[0].project_id == "project"
        assert result.entries[0].work_date > date(2026, 7, 31)


def test_submit_sets_status_notifies_unique_manager_and_admin_and_audits(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.commit_count = 0
        result = _run(timesheets.submit_my_timesheet_week(_payload(), db, actor))
        assert result.status == "submitted"
        assert db.commit_count == 2
        recipients = {row.user_id for row in db.query(Notification).all()}
        assert recipients == {"manager", "admin"}
        assert [event["action"] for event in timesheet_context["audits"]] == [
            "timesheet.saved", "timesheet.submitted",
        ]


def test_duplicate_submission_is_rejected_by_the_nested_save(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        _run(timesheets.submit_my_timesheet_week(_payload(), db, actor))
        with pytest.raises(HTTPException) as error:
            _run(timesheets.submit_my_timesheet_week(_payload(), db, actor))
        assert error.value.status_code == 400


def test_current_submit_commits_draft_before_submission_failure(timesheet_context):
    """Known defect: the nested save commits before later submission work fails."""
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    timesheet_context["monkeypatch"].setattr(
        timesheets, "create_notification", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic notification failure")),
    )
    db = Session()
    db.commit_count = 0
    with pytest.raises(RuntimeError, match="synthetic notification failure"):
        _run(timesheets.submit_my_timesheet_week(_payload(), db, actor))
    assert db.commit_count == 1
    db.close()  # rolls back the uncommitted submitted status
    with Session() as verification_db:
        persisted = verification_db.query(TimesheetEntry).all()
        assert len(persisted) == 1
        assert persisted[0].status == "draft"


def test_recall_submitted_week_and_reject_recall_after_approval(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.add(_entry("employee", "submitted"))
        db.commit()
        result = _run(timesheets.recall_my_timesheet_week(WEEK, "UTC", db, actor))
        assert result.status == "draft"
        db.query(TimesheetEntry).update({"status": "approved"})
        db.commit()
        with pytest.raises(HTTPException) as error:
            _run(timesheets.recall_my_timesheet_week(WEEK, "UTC", db, actor))
        assert error.value.status_code == 400


def test_current_recall_changes_all_rows_when_week_has_mixed_statuses(timesheet_context):
    """Known defect: one submitted row causes approved/rejected siblings to be reset."""
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.add_all([
            _entry("employee", "submitted", suffix="submitted"),
            _entry("employee", "approved", suffix="approved"),
            _entry("employee", "rejected", suffix="rejected"),
        ])
        db.commit()
        _run(timesheets.recall_my_timesheet_week(WEEK, "UTC", db, actor))
        assert {row.status for row in db.query(TimesheetEntry).all()} == {"draft"}


@pytest.mark.parametrize(
    ("status", "allowed"),
    [("draft", True), ("rejected", True), ("submitted", False), ("approved", False)],
)
def test_delete_behavior_by_current_state(timesheet_context, status, allowed):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.add(_entry("employee", status))
        db.commit()
        if allowed:
            result = _run(timesheets.delete_my_timesheet_week(WEEK, "UTC", db, actor))
            assert result.entries == []
            assert db.query(TimesheetEntry).count() == 0
        else:
            with pytest.raises(HTTPException) as error:
                _run(timesheets.delete_my_timesheet_week(WEEK, "UTC", db, actor))
            assert error.value.status_code == 400


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_manager_decision_updates_rows_notifies_employee_and_returns_approval_list(timesheet_context, decision):
    Session = timesheet_context["Session"]
    manager_actor = _actor(timesheet_context["employees"]["manager"])
    called = []
    timesheet_context["monkeypatch"].setattr(timesheets, "timesheet_approvals", lambda db, actor: _async_value(called, {"approvals": []}))
    timesheet_context["monkeypatch"].setattr(timesheets, "calculate_compliance", lambda *_args: _compliance())
    with Session() as db:
        db.add(_entry("employee", "submitted"))
        db.commit()
        result = _run(timesheets.decide_timesheet(
            "employee", WEEK, timesheets.TimesheetDecisionRequest(decision=decision, reviewer_notes="review note"), db, manager_actor,
        ))
        assert result == {"approvals": []}
        assert called == [True]
        row = db.query(TimesheetEntry).one()
        assert row.status == ("approved" if decision == "approve" else "rejected")
        assert row.reviewer_notes == "review note"
        notification = db.query(Notification).one()
        assert notification.user_id == "employee"
        assert "review note" in notification.message


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_administrator_decision_uses_admin_path_and_reason_schema(timesheet_context, decision):
    Session = timesheet_context["Session"]
    admin_actor = _actor(timesheet_context["employees"]["admin"])
    called = []
    timesheet_context["monkeypatch"].setattr(admin_time_off, "admin_time_off_dashboard", lambda db, actor: _async_value(called, {"dashboard": True}))
    timesheet_context["monkeypatch"].setattr(admin_time_off, "log_audit", lambda *_args, **_kwargs: None)
    with Session() as db:
        db.add(_entry("employee", "submitted"))
        db.commit()
        result = _run(admin_time_off.decide_timesheet(
            "employee", WEEK, admin_time_off.DecisionPayload(decision=decision, reason="required for reject"), db, admin_actor,
        ))
        assert result == {"dashboard": True}
        assert called == [True]
        row = db.query(TimesheetEntry).one()
        assert row.status == ("approved" if decision == "approve" else "rejected")
        assert row.reviewer_notes == "required for reject"


def test_self_approval_and_unauthorized_manager_are_denied(timesheet_context):
    Session = timesheet_context["Session"]
    employee_actor = _actor(timesheet_context["employees"]["employee"])
    other_actor = _actor(timesheet_context["employees"]["other_manager"])
    with Session() as db:
        db.add(_entry("employee", "submitted"))
        db.commit()
        for actor in (employee_actor, other_actor):
            with pytest.raises(HTTPException) as error:
                _run(timesheets.decide_timesheet(
                    "employee", WEEK, timesheets.TimesheetDecisionRequest(decision="reject"), db, actor,
                ))
            assert error.value.status_code == 403


def test_two_sequential_decisions_against_same_week_reject_second(timesheet_context):
    Session = timesheet_context["Session"]
    manager_actor = _actor(timesheet_context["employees"]["manager"])
    timesheet_context["monkeypatch"].setattr(timesheets, "timesheet_approvals", lambda db, actor: _async_value([], {"approvals": []}))
    timesheet_context["monkeypatch"].setattr(timesheets, "calculate_compliance", lambda *_args: _compliance())
    with Session() as db:
        db.add(_entry("employee", "submitted"))
        db.commit()
        _run(timesheets.decide_timesheet(
            "employee", WEEK, timesheets.TimesheetDecisionRequest(decision="approve"), db, manager_actor,
        ))
        with pytest.raises(HTTPException) as error:
            _run(timesheets.decide_timesheet(
                "employee", WEEK, timesheets.TimesheetDecisionRequest(decision="reject"), db, manager_actor,
            ))
        assert error.value.status_code == 400


def test_manager_approval_list_includes_only_authorized_submitted_weeks(timesheet_context):
    Session = timesheet_context["Session"]
    manager_actor = _actor(timesheet_context["employees"]["manager"])
    with Session() as db:
        db.add_all([
            _entry("employee", "submitted"),
            _entry("admin", "submitted", suffix="admin"),
        ])
        db.commit()
        result = _run(timesheets.timesheet_approvals(db, manager_actor))
        assert [item["employee_id"] for item in result["approvals"]] == ["employee"]


def test_compliance_evaluation_is_a_read_with_audit_and_commit_side_effect(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    timesheet_context["monkeypatch"].setattr(timesheets, "calculate_compliance", lambda *_args: _compliance())
    with Session() as db:
        db.add(_entry("employee", "submitted"))
        db.commit()
        db.commit_count = 0
        result = _run(timesheets.timesheet_allocation_compliance("entry-employee-one", db, actor))
        assert result.overall_status == "compliant"
        assert db.commit_count == 1
        assert timesheet_context["audits"][-1]["action"] == "allocation_compliance_checked"


def test_history_and_summary_current_output_contracts(timesheet_context):
    Session = timesheet_context["Session"]
    actor = _actor(timesheet_context["employees"]["employee"])
    with Session() as db:
        db.add_all([
            _entry("employee", "draft"),
            _entry("employee", "approved", week=NEXT_WEEK, suffix="next"),
        ])
        db.commit()
        summary = _run(timesheets.my_timesheet_summary(db, actor))
        history = _run(timesheets.my_timesheet_history(db, actor))
        assert summary.week_start == NEXT_WEEK
        assert summary.status == "approved"
        assert [week.week_start for week in history] == [NEXT_WEEK, WEEK]
        assert all(hasattr(week, "entries") and hasattr(week, "leave_days") for week in history)


async def _async_value(called: list, value):
    called.append(True)
    return value


def _compliance():
    return SimpleNamespace(
        overall_status="compliant", week_start=WEEK, week_end=date(2026, 8, 1),
        unallocated_hours=0.0, total_expected_hours=8.0, total_actual_hours=8.0,
        total_variance_hours=0.0, project_rows=[],
    )


@pytest.mark.skip(reason="Task 8B requires PostgreSQL SELECT FOR UPDATE/version integration coverage")
def test_production_database_concurrent_timesheet_decisions_are_serialized():
    """Reserved production-engine test; SQLite cannot prove row-lock semantics."""
