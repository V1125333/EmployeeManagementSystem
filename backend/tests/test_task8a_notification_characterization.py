"""Task 8A characterization of notifications and action-inbox behavior."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import admin_time_off, announcements, inbox_notifications
from app.core.authentication import AuthenticatedActor, AuthenticatedPrincipal
from app.core.database import Base
from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.leave_attendance import Attendance, AttendanceCorrection, LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import (
    ActionInboxItem,
    ActivityLog,
    Announcement,
    AnnouncementAudience,
    Notification,
    Project,
)
from app.models.organization import Department, Designation
from app.schemas.allocation import AllocationCreate
from app.services import allocation_service, auth_service, requests_service


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
        AuthenticatedPrincipal(
            employee_id=employee.id, email=employee.work_email, role=employee.role,
            status="active", permissions=frozenset(), token_id=f"token-{employee.id}",
            manager_id=employee.manager_id,
        ),
        employee,
    )


@pytest.fixture()
def notification_context(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Department.__table__, Designation.__table__, Employee.__table__, Project.__table__,
        Allocation.__table__, Notification.__table__, ActionInboxItem.__table__,
        Announcement.__table__, AnnouncementAudience.__table__, ActivityLog.__table__,
        LeaveType.__table__, LeaveBalance.__table__, LeaveRequest.__table__,
        Attendance.__table__, AttendanceCorrection.__table__,
    ])
    Session = sessionmaker(
        bind=engine, class_=CountingSession, autoflush=False, autocommit=False, expire_on_commit=False,
    )
    employees = {
        "employee": _employee("employee", "employee", manager_id="manager"),
        "other": _employee("other", "employee"),
        "manager": _employee("manager", "manager"),
        "admin": _employee("admin", "admin"),
    }
    with Session() as db:
        db.add_all(employees.values())
        db.commit()
    monkeypatch.setattr(allocation_service, "log_audit", lambda *_args, **_kwargs: None)
    yield {"Session": Session, "employees": employees, "monkeypatch": monkeypatch}
    engine.dispose()


def _run(awaitable):
    return asyncio.run(awaitable)


def test_leave_and_attendance_decisions_notify_only_the_request_owner(notification_context):
    Session = notification_context["Session"]
    manager_actor = _actor(notification_context["employees"]["manager"])
    with Session() as db:
        leave_type = LeaveType(id="sick", name="Sick", code="SL", default_days_per_year=10)
        leave = LeaveRequest(
            id="leave", employee_id="employee", leave_type_id="sick", start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 3), total_days=1, status="pending",
        )
        attendance = Attendance(id="attendance", employee_id="employee", date=date(2026, 8, 1))
        correction = AttendanceCorrection(
            id="correction", employee_id="employee", attendance_id="attendance",
            reason="Missed checkout", status="pending",
        )
        db.add_all([leave_type, leave, attendance, correction])
        db.commit()
        assert _run(inbox_notifications.decide_leave_request("leave", "reject", db, manager_actor))["status"] == "rejected"
        assert _run(inbox_notifications.decide_attendance_correction("correction", "approve", db, manager_actor))["status"] == "approved"
        rows = db.query(Notification).order_by(Notification.created_at).all()
        assert [(row.user_id, row.related_entity_type) for row in rows] == [
            ("employee", "leave_request"), ("employee", "attendance_correction"),
        ]


def test_allocation_creation_adds_notification_and_commit_is_owned_by_service_flag(notification_context):
    Session = notification_context["Session"]
    with Session() as db:
        db.add(Project(id="project", name="Project", code="P1", status="active", project_manager_id="manager"))
        db.commit()
        db.commit_count = 0
        allocation_service.create_allocation(db, AllocationCreate(
            employee_id="employee", manager_id="manager", allocation_percentage=100,
            allocation_role="Engineer", billing_type="billable", start_date=date(2026, 8, 1),
            project_id="project", project_name="Project", status="active",
        ), "admin", commit=False)
        db.flush()
        row = db.query(Notification).one()
        assert row.user_id == "employee"
        assert row.link_url == "/profile?tab=allocations"
        assert db.commit_count == 0


def test_request_helpers_create_duplicates_for_sequential_identical_events(notification_context):
    """Known defect: request notification and inbox helpers have no deduplication."""
    Session = notification_context["Session"]
    with Session() as db:
        for _ in range(2):
            requests_service._notify(db, "employee", "Request updated", "Request changed", "request-1")
            requests_service._inbox(db, "manager", "Review request", "Please review", "request-1")
        db.commit()
        assert db.query(Notification).count() == 2
        assert db.query(ActionInboxItem).count() == 2


def test_announcement_notification_and_acknowledgment_are_sequentially_deduplicated(notification_context):
    Session = notification_context["Session"]
    with Session() as db:
        announcement = Announcement(
            id="announcement", title="Policy", description="Read the policy", message="Read the policy",
            status="published", audience_type="everyone", requires_acknowledgment=True,
            priority="high", publish_date=date.today(), publish_at=datetime.utcnow(), is_active=True,
        )
        db.add(announcement)
        db.commit()
        announcements.create_notifications_for_published(announcement, db)
        db.flush()
        announcements.create_notifications_for_published(announcement, db)
        db.commit()
        assert db.query(Notification).count() == 4  # one per visible employee, not eight
        assert db.query(ActionInboxItem).count() == 4
        assert {row.link_url for row in db.query(Notification).all()} == {"/announcements/announcement"}


def test_authentication_and_admin_helpers_accept_domain_specific_recipients_and_links(notification_context):
    Session = notification_context["Session"]
    with Session() as db:
        auth_service.notify_admins_account_locked(db, notification_context["employees"]["employee"])
        admin_time_off.notify(db, "employee", "Balance adjusted", "Your balance changed.", "leave_balance", "balance-1")
        db.commit()
        rows = db.query(Notification).order_by(Notification.title).all()
        assert {row.user_id for row in rows} == {"admin", "employee"}
        assert {row.link_url for row in rows} == {"/admin/security", "/employee/notifications"}


def test_current_notification_messages_are_not_canonically_bounded(notification_context):
    """Known defect: generic helpers can persist long free-form content."""
    Session = notification_context["Session"]
    with Session() as db:
        long_message = "sensitive-free-form:" + ("x" * 1200)
        admin_time_off.notify(db, "employee", "Unbounded", long_message, "timesheet", "entry")
        db.commit()
        row = db.query(Notification).one()
        assert row.message == long_message
        assert len(row.message) > 1000


def test_mark_one_and_mark_all_read_are_owner_scoped_without_audit(notification_context):
    Session = notification_context["Session"]
    employee_actor = _actor(notification_context["employees"]["employee"])
    other_actor = _actor(notification_context["employees"]["other"])
    with Session() as db:
        db.add_all([
            Notification(id="mine-1", user_id="employee", title="One"),
            Notification(id="mine-2", user_id="employee", title="Two"),
            Notification(id="other-1", user_id="other", title="Other"),
        ])
        db.commit()
        with pytest.raises(HTTPException) as error:
            _run(inbox_notifications.mark_notification_read("mine-1", db, other_actor))
        assert error.value.status_code == 404
        _run(inbox_notifications.mark_notification_read("mine-1", db, employee_actor))
        _run(inbox_notifications.mark_all_notifications_read(db, employee_actor))
        assert all(row.is_read for row in db.query(Notification).filter(Notification.user_id == "employee"))
        assert not db.query(Notification).filter(Notification.id == "other-1").one().is_read
        assert db.query(ActivityLog).count() == 0


def test_completing_inbox_item_is_owner_scoped_and_has_no_audit(notification_context):
    Session = notification_context["Session"]
    employee_actor = _actor(notification_context["employees"]["employee"])
    other_actor = _actor(notification_context["employees"]["other"])
    with Session() as db:
        db.add(ActionInboxItem(id="item", assigned_to_user_id="employee", item_type="profile_update", title="Complete profile"))
        db.commit()
        with pytest.raises(HTTPException) as error:
            _run(inbox_notifications.complete_inbox_item("item", db, other_actor))
        assert error.value.status_code == 404
        assert _run(inbox_notifications.complete_inbox_item("item", db, employee_actor)) == {"success": True}
        assert db.query(ActionInboxItem).one().status == "completed"
        assert db.query(ActivityLog).count() == 0


@pytest.mark.parametrize("operation", ["inbox", "count"])
def test_current_get_inbox_and_count_mutate_stale_profile_records(notification_context, operation):
    """Known defect: GET endpoints complete items, delete notifications, and commit."""
    Session = notification_context["Session"]
    employee = notification_context["employees"]["employee"]
    employee.emergency_contact_name = "Contact"
    employee.emergency_contact_phone = "5551234567"
    employee.emergency_contact_relation = "Friend"
    actor = _actor(employee)
    with Session() as db:
        stored = db.query(Employee).filter(Employee.id == "employee").one()
        stored.emergency_contact_name = "Contact"
        stored.emergency_contact_phone = "5551234567"
        stored.emergency_contact_relation = "Friend"
        db.add(ActionInboxItem(
            id="stale", assigned_to_user_id="employee", item_type="profile_update", title="Profile",
            related_entity_type="employee", related_entity_id="employee", status="pending",
        ))
        db.add(Notification(
            id="stale-note", user_id="employee", title="Profile", notification_type="profile_update",
            related_entity_type="employee", related_entity_id="employee",
        ))
        db.commit()
        db.commit_count = 0
        if operation == "inbox":
            _run(inbox_notifications.get_inbox(db, actor))
        else:
            _run(inbox_notifications.get_inbox_count(db, actor))
        assert db.query(ActionInboxItem).one().status == "completed"
        assert db.query(Notification).count() == 0
        assert db.commit_count == 1


def test_notification_and_business_mutation_roll_back_together_when_caller_rolls_back(notification_context):
    Session = notification_context["Session"]
    with Session() as db:
        item = ActionInboxItem(id="rollback-item", assigned_to_user_id="employee", item_type="request", title="Request")
        db.add(item)
        db.commit()
        item.status = "completed"
        inbox_notifications.create_notification(
            db, "employee", "Status", "Changed", "request", "employee_request", "request-rollback",
        )
        db.flush()
        db.rollback()
    with Session() as verification_db:
        assert verification_db.query(ActionInboxItem).filter_by(id="rollback-item").one().status == "pending"
        assert verification_db.query(Notification).count() == 0


def test_startup_allocation_reminder_job_sequentially_deduplicates_by_current_query(notification_context):
    Session = notification_context["Session"]
    with Session() as db:
        db.add(Project(id="ending-project", name="Ending", code="END", status="active", project_manager_id="manager"))
        db.add(Allocation(
            id="ending", employee_id="employee", project_id="ending-project", project_name="Ending",
            manager_id="manager", allocation_percentage=100, allocation_role="Engineer", billing_type="billable",
            status="active", start_date=date.today() - timedelta(days=30), end_date=date.today() + timedelta(days=3),
            created_by="admin",
        ))
        db.commit()
        first = allocation_service.ensure_allocation_ending_notifications(db, date.today())
        second = allocation_service.ensure_allocation_ending_notifications(db, date.today())
        assert first > 0
        assert second == 0
        assert db.query(Notification).count() == first


@pytest.mark.skip(reason="Task 8B requires PostgreSQL unique-key/concurrent transaction coverage")
def test_production_database_concurrent_notification_deduplication():
    """Reserved production-engine test; SQLite sequential checks are not concurrency proof."""
