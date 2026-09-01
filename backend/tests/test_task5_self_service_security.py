from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import (
    attendance,
    dashboard,
    documents,
    holidays,
    inbox_notifications,
    leaves,
    settings as settings_api,
    support_tickets,
    timesheets,
)
from app.core import authentication
from app.core.authentication import create_access_token, get_authenticated_actor
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.documents import EmployeeDocument
from app.models.employee import Employee
from app.models.leave_attendance import Attendance, LeaveRequest, LeaveType
from app.models.operations import ActionInboxItem, CompanyHoliday, Notification, TimesheetEntry
from app.models.organization import Department, Designation
from app.models.settings import OrganizationSecurityPolicy, SupportTicket, UserSettings
from app.models.audit import AuditLog
from app.models.user_preferences import UserPreferences


MIGRATED_ROUTES = {
    ("GET", "/attendance/me/today"),
    ("GET", "/attendance/me/context"),
    ("POST", "/attendance/me/check-in"),
    ("POST", "/attendance/me/check-out"),
    ("GET", "/attendance/me/history"),
    ("GET", "/leaves/me/context"),
    ("POST", "/leaves/me/assess"),
    ("POST", "/leaves/me/submissions"),
    ("GET", "/leaves/me/requests/{request_id}/status"),
    ("GET", "/leaves/me/summary"),
    ("POST", "/leaves/me/requests"),
    ("PUT", "/leaves/me/requests/{request_id}"),
    ("DELETE", "/leaves/me/requests/{request_id}"),
    ("POST", "/leaves/me/requests/{request_id}/withdraw"),
    ("GET", "/timesheets/me/options"),
    ("GET", "/timesheets/me/week"),
    ("POST", "/timesheets/me/week"),
    ("POST", "/timesheets/me/week/submit"),
    ("POST", "/timesheets/me/week/recall"),
    ("POST", "/timesheets/me/week/copy"),
    ("DELETE", "/timesheets/me/week"),
    ("GET", "/timesheets/me/summary"),
    ("GET", "/timesheets/me/history"),
    ("GET", "/holidays"),
    ("GET", "/holidays/available-floating"),
    ("GET", "/holidays/working-days"),
    ("GET", "/documents"),
    ("POST", "/documents"),
    ("PUT", "/documents/{document_id}"),
    ("GET", "/documents/{document_id}/download"),
    ("GET", "/settings/me"),
    ("GET", "/settings/preferences"),
    ("PATCH", "/settings/preferences/appearance"),
    ("PATCH", "/settings/preferences/general"),
    ("PATCH", "/settings/preferences/notifications"),
    ("GET", "/settings/activity"),
    ("GET", "/settings/profile"),
    ("PATCH", "/settings/me/general"),
    ("PATCH", "/settings/me/security"),
    ("PATCH", "/settings/me/notifications"),
    ("PATCH", "/settings/me/appearance"),
    ("PATCH", "/settings/me/privacy"),
    ("GET", "/dashboard/employee-context"),
    ("POST", "/support-tickets"),
    ("GET", "/inbox"),
    ("GET", "/inbox/count"),
    ("POST", "/inbox/{item_id}/complete"),
    ("GET", "/notifications"),
    ("GET", "/notifications/unread-count"),
    ("PUT", "/notifications/{notification_id}/read"),
    ("PUT", "/notifications/mark-all-read"),
}


def _dependency_calls(route: APIRoute):
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop()
        yield dependency.call
        pending.extend(dependency.dependencies)


def _employee(employee_id: str, email: str, *, work_location: str = "US") -> Employee:
    return Employee(
        id=employee_id,
        first_name=employee_id.title(),
        last_name="Employee",
        work_email=email,
        phone=f"555{employee_id[-1] * 7}",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        reporting_manager="",
        joining_date=date(2025, 1, 1),
        date_of_joining=date(2025, 1, 1),
        work_location=work_location,
    )


@pytest.fixture()
def task5_context(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Department.__table__,
            Designation.__table__,
            Employee.__table__,
            Attendance.__table__,
            LeaveType.__table__,
            LeaveRequest.__table__,
            TimesheetEntry.__table__,
            CompanyHoliday.__table__,
            EmployeeDocument.__table__,
            UserSettings.__table__,
            OrganizationSecurityPolicy.__table__,
            AuditLog.__table__,
            UserPreferences.__table__,
            SupportTicket.__table__,
            Notification.__table__,
            ActionInboxItem.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        owner = _employee("employee-1", "owner@example.com", work_location="US")
        other = _employee("employee-2", "other@example.com", work_location="IN")
        db.add_all([owner, other])
        db.commit()
        monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "task-five-secret-that-is-long-enough")
        owner_token = create_access_token(owner)
        other_token = create_access_token(other)

    app = FastAPI()
    for router in (
        attendance.router,
        leaves.router,
        timesheets.router,
        holidays.router,
        documents.router,
        settings_api.router,
        dashboard.router,
        support_tickets.router,
        inbox_notifications.router,
    ):
        app.include_router(router)

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    audit_actor_ids: list[str] = []
    monkeypatch.setattr(
        timesheets,
        "log_audit",
        lambda _db, actor, **_kwargs: audit_actor_ids.append(actor.id),
    )
    client = TestClient(app)
    yield {
        "client": client,
        "Session": Session,
        "owner_token": owner_token,
        "other_token": other_token,
        "audit_actor_ids": audit_actor_ids,
    }
    client.close()
    engine.dispose()


def _spoofed_bearer(context) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {context['owner_token']}",
        "X-User-Id": "employee-2",
        "X-User-Email": "other@example.com",
        "X-User-Name": "Spoofed Employee",
    }


def test_every_task5_route_declares_the_server_derived_actor_dependency():
    app = FastAPI()
    for router in (
        attendance.router,
        leaves.router,
        timesheets.router,
        holidays.router,
        documents.router,
        settings_api.router,
        dashboard.router,
        support_tickets.router,
        inbox_notifications.router,
    ):
        app.include_router(router)

    protected = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            key = (method, route.path)
            if key in MIGRATED_ROUTES and get_authenticated_actor in set(_dependency_calls(route)):
                protected.add(key)

    assert protected == MIGRATED_ROUTES


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/attendance/me/today"),
        ("get", "/leaves/me/context"),
        ("get", "/timesheets/me/summary"),
        ("get", "/holidays"),
        ("get", "/documents"),
        ("get", "/settings/me"),
        ("get", "/dashboard/employee-context"),
        ("post", "/support-tickets"),
        ("get", "/inbox"),
        ("get", "/notifications"),
    ],
)
def test_each_task5_domain_rejects_missing_bearer(task5_context, method, path):
    response = task5_context["client"].request(method, path)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_settings_and_support_writes_use_bearer_owner_despite_spoofed_headers(task5_context):
    client = task5_context["client"]
    headers = _spoofed_bearer(task5_context)

    settings_response = client.patch("/settings/me/security", headers=headers, json={"mfa_enabled": True})
    assert settings_response.status_code == 200
    assert settings_response.json()["user_id"] == "employee-1"

    ticket_response = client.post(
        "/support-tickets",
        headers=headers,
        json={"category": "IT", "subject": "Access issue", "description": "Synthetic test ticket"},
    )
    assert ticket_response.status_code == 200
    assert ticket_response.json()["user_id"] == "employee-1"
    assert ticket_response.json()["created_by"] == "employee-1"

    with task5_context["Session"]() as db:
        assert db.query(UserSettings).filter(UserSettings.user_id == "employee-1").one().mfa_enabled is True
        assert db.query(UserSettings).filter(UserSettings.user_id == "employee-2").count() == 0
        assert db.query(SupportTicket).one().user_id == "employee-1"


def test_documents_holidays_and_dashboard_are_actor_scoped(task5_context):
    with task5_context["Session"]() as db:
        db.add_all(
            [
                CompanyHoliday(id="us-holiday", name="US Day", holiday_date=date(2026, 8, 3), regions="US"),
                CompanyHoliday(id="in-holiday", name="IN Day", holiday_date=date(2026, 8, 4), regions="IN"),
                EmployeeDocument(
                    id="owner-doc", employee_id="employee-1", uploaded_by_id="employee-1", name="owner.pdf",
                    stored_file_name="owner.pdf", mime_type="application/pdf", file_size_bytes=1,
                    checksum_sha256="a" * 64, storage_path="owner.pdf", category="personal", folder="Personal", status="none",
                ),
                EmployeeDocument(
                    id="other-doc", employee_id="employee-2", uploaded_by_id="employee-2", name="other.pdf",
                    stored_file_name="other.pdf", mime_type="application/pdf", file_size_bytes=1,
                    checksum_sha256="b" * 64, storage_path="other.pdf", category="personal", folder="Personal", status="none",
                ),
            ]
        )
        db.commit()

    headers = _spoofed_bearer(task5_context)
    client = task5_context["client"]
    holiday_response = client.get("/holidays?from_date=2026-08-01&to_date=2026-08-10", headers=headers)
    assert holiday_response.status_code == 200
    assert [item["id"] for item in holiday_response.json()["holidays"]] == ["us-holiday"]

    document_response = client.get("/documents", headers=headers)
    assert document_response.status_code == 200
    assert [item["id"] for item in document_response.json()] == ["owner-doc"]
    assert client.get("/documents/other-doc/download", headers=headers).status_code == 404

    dashboard_response = client.get("/dashboard/employee-context", headers=headers)
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["employee"]["id"] == "employee-1"


def test_inbox_and_notifications_never_read_or_mutate_another_owner(task5_context):
    with task5_context["Session"]() as db:
        db.add_all(
            [
                ActionInboxItem(id="owner-item", assigned_to_user_id="employee-1", item_type="task", title="Owner item"),
                ActionInboxItem(id="other-item", assigned_to_user_id="employee-2", item_type="task", title="Other item"),
                Notification(id="owner-note", user_id="employee-1", title="Owner note", is_read=False),
                Notification(id="other-note", user_id="employee-2", title="Other note", is_read=False),
            ]
        )
        db.commit()

    headers = _spoofed_bearer(task5_context)
    client = task5_context["client"]
    assert [item["id"] for item in client.get("/inbox", headers=headers).json()["items"]] == ["owner-item"]
    assert client.post("/inbox/other-item/complete", headers=headers).status_code == 404
    assert [item["id"] for item in client.get("/notifications", headers=headers).json()["notifications"]] == ["owner-note"]
    assert client.put("/notifications/other-note/read", headers=headers).status_code == 404
    assert client.put("/notifications/mark-all-read", headers=headers).status_code == 200

    with task5_context["Session"]() as db:
        assert db.get(ActionInboxItem, "other-item").status == "pending"
        assert db.get(Notification, "owner-note").is_read is True
        assert db.get(Notification, "other-note").is_read is False


def test_timesheet_reads_and_mutations_are_limited_to_the_bearer_owner(task5_context):
    week_start = date(2026, 8, 2)
    with task5_context["Session"]() as db:
        db.add_all(
            [
                TimesheetEntry(
                    id="owner-time", employee_id="employee-1", work_date=date(2026, 8, 3),
                    week_start=week_start, entry_code="POC", project_name="Owner work",
                    hours=8, status="draft", time_zone="UTC",
                ),
                TimesheetEntry(
                    id="other-time", employee_id="employee-2", work_date=date(2026, 8, 3),
                    week_start=week_start, entry_code="POC", project_name="Other work",
                    hours=8, status="draft", time_zone="UTC",
                ),
            ]
        )
        db.commit()

    client = task5_context["client"]
    headers = _spoofed_bearer(task5_context)
    week_response = client.get(f"/timesheets/me/week?week_start={week_start}", headers=headers)
    assert week_response.status_code == 200
    assert [entry["id"] for entry in week_response.json()["entries"]] == ["owner-time"]

    save_response = client.post(
        "/timesheets/me/week",
        headers=headers,
        json={
            "week_start": str(week_start),
            "time_zone": "UTC",
            "entries": [
                {
                    "work_date": "2026-08-04",
                    "entry_code": "POC",
                    "project_name": "Updated owner work",
                    "start_time": "09:00:00",
                    "end_time": "17:00:00",
                }
            ],
        },
    )
    assert save_response.status_code == 200
    assert [entry["project_name"] for entry in save_response.json()["entries"]] == ["Updated owner work"]
    assert task5_context["audit_actor_ids"] == ["employee-1"]

    with task5_context["Session"]() as db:
        assert db.query(TimesheetEntry).filter(TimesheetEntry.employee_id == "employee-1").count() == 1
        assert db.get(TimesheetEntry, "other-time").project_name == "Other work"

    other_only_week = date(2026, 8, 9)
    with task5_context["Session"]() as db:
        db.add(TimesheetEntry(
            id="other-only-time", employee_id="employee-2", work_date=date(2026, 8, 10),
            week_start=other_only_week, entry_code="POC", project_name="Other-only work",
            hours=8, status="submitted", time_zone="UTC",
        ))
        db.commit()
    assert client.post(f"/timesheets/me/week/recall?week_start={other_only_week}", headers=headers).status_code == 404
    copy_response = client.post(
        "/timesheets/me/week/copy",
        headers=headers,
        json={"source_week_start": str(other_only_week), "target_week_start": "2026-08-16", "time_zone": "UTC"},
    )
    assert copy_response.status_code == 404
