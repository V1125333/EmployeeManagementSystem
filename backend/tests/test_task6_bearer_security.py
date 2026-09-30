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
    allocations,
    announcements,
    employees,
    forecasting,
    inbox_notifications,
    leaves,
    projects,
    requests,
    staffing_requests,
    timesheets,
)
from app.core import authentication
from app.core.authentication import create_access_token, get_authenticated_actor
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import (
    ActionInboxItem,
    Announcement,
    AnnouncementAcknowledgment,
    AnnouncementAudience,
    AnnouncementRead,
    Notification,
    TimesheetEntry,
)
from app.models.organization import Department, Designation


TASK6_ROUTERS = (
    employees.router,
    projects.router,
    allocations.router,
    forecasting.router,
    staffing_requests.router,
    requests.router,
    announcements.router,
)

TASK6_REVIEW_ROUTES = {
    ("GET", "/leaves/approvals"),
    ("POST", "/leaves/approvals/{request_id}/decision"),
    ("GET", "/timesheets/{timesheet_id}/allocation-compliance"),
    ("GET", "/timesheets/approvals"),
    ("POST", "/timesheets/approvals/{employee_id}/{week_start}/decision"),
}


def _dependency_calls(route: APIRoute):
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop()
        yield dependency.call
        pending.extend(dependency.dependencies)


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


@pytest.fixture()
def task6_context(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Department.__table__,
            Designation.__table__,
            Employee.__table__,
            LeaveType.__table__,
            LeaveRequest.__table__,
            Announcement.__table__,
            AnnouncementAudience.__table__,
            AnnouncementAcknowledgment.__table__,
            AnnouncementRead.__table__,
            Notification.__table__,
            ActionInboxItem.__table__,
            TimesheetEntry.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    actors = {
        "employee": _employee("employee", "employee"),
        "unrelated": _employee("unrelated", "employee"),
        "manager": _employee("manager", "manager"),
        "report": _employee("report", "employee", manager_id="manager"),
        "hr_admin": _employee("hr-admin", "hr_admin"),
        "finance": _employee("finance", "finance"),
        "project_manager": _employee("project-manager", "manager"),
    }
    with Session() as db:
        db.add_all(actors.values())
        db.commit()
        monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "task-six-secret-that-is-long-enough")
        tokens = {name: create_access_token(actor) for name, actor in actors.items()}

    app = FastAPI()
    for router in (*TASK6_ROUTERS, inbox_notifications.router, leaves.router, timesheets.router):
        app.include_router(router)

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(allocations, "log_authorization_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(forecasting, "log_authorization_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(staffing_requests, "log_authorization_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(projects, "log_authorization_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(leaves, "log_authorization_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(timesheets, "log_authorization_failure", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    yield {"client": client, "Session": Session, "tokens": tokens}
    client.close()
    engine.dispose()


def _bearer(context, actor: str = "employee", **spoofed: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {context['tokens'][actor]}"}
    headers.update(spoofed)
    return headers


def test_every_task6_route_uses_the_central_authenticated_actor_dependency():
    app = FastAPI()
    for router in (*TASK6_ROUTERS, inbox_notifications.router, leaves.router, timesheets.router):
        app.include_router(router)

    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        route_keys = {(method, route.path) for method in route.methods}
        if route.path.startswith(("/employees", "/projects", "/allocations", "/forecasting", "/staffing-requests", "/requests", "/announcements")) or route.path.startswith(
            ("/inbox/leave-requests", "/inbox/attendance-corrections")
        ) or route_keys.intersection(TASK6_REVIEW_ROUTES):
            if get_authenticated_actor not in set(_dependency_calls(route)):
                missing.append((sorted(route.methods), route.path))

    assert missing == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/employees/organization"),
        ("get", "/projects/"),
        ("get", "/allocations/employee/employee"),
        ("get", "/forecasting"),
        ("get", "/staffing-requests/options"),
        ("get", "/requests/types"),
        ("get", "/announcements/my"),
        ("post", "/inbox/leave-requests/request/approve"),
        ("post", "/inbox/attendance-corrections/correction/approve"),
        ("get", "/leaves/approvals"),
        ("get", "/timesheets/approvals"),
        ("get", "/timesheets/timesheet/allocation-compliance"),
    ],
)
def test_each_task6_domain_requires_bearer_authentication(task6_context, method, path):
    response = task6_context["client"].request(method, path)
    assert response.status_code == 401


def test_spoofed_admin_headers_do_not_grant_privileged_domain_access(task6_context):
    headers = _bearer(
        task6_context,
        "employee",
        **{
            "X-User-Id": "admin",
            "X-User-Email": "admin@example.com",
            "X-User-Name": "Admin User",
        },
    )

    assert task6_context["client"].get("/employees/", headers=headers).status_code == 403
    assert task6_context["client"].get("/forecasting", headers=headers).status_code == 403
    assert task6_context["client"].get("/staffing-requests/options", headers=headers).status_code == 403
    assert task6_context["client"].post(
        "/announcements",
        headers=headers,
        json={"title": "Fixed", "message": "Synthetic", "status": "draft"},
    ).status_code == 403


def test_project_and_request_services_receive_only_the_bearer_actor(task6_context, monkeypatch):
    observed: list[tuple[str, str]] = []

    def fake_projects(_db, *, actor, **_kwargs):
        observed.append(("projects", actor.id))
        return [], 0

    def fake_my_requests(_db, actor, **_kwargs):
        observed.append(("requests", actor.id))
        return {"items": [], "total": 0, "page": 1, "per_page": 25, "pages": 0}

    monkeypatch.setattr(projects, "list_projects", fake_projects)
    monkeypatch.setattr(requests, "get_my_requests", fake_my_requests)
    headers = _bearer(task6_context, "employee", **{"X-User-Id": "unrelated", "X-User-Email": "unrelated@example.com"})

    assert task6_context["client"].get("/projects/", headers=headers).status_code == 200
    assert task6_context["client"].get("/requests/my", headers=headers).status_code == 200
    assert observed == [("projects", "employee"), ("requests", "employee")]


def test_cross_employee_allocation_read_uses_target_only_and_denies_spoofing(task6_context):
    response = task6_context["client"].get(
        "/allocations/employee/unrelated",
        headers=_bearer(task6_context, "employee", **{"X-User-Id": "admin", "X-User-Email": "admin@example.com"}),
    )
    assert response.status_code == 403


def test_inbox_leave_decision_revalidates_canonical_self_approval_rule(task6_context):
    with task6_context["Session"]() as db:
        leave_type = LeaveType(id="sick", name="Sick", code="SL", default_days_per_year=10)
        request = LeaveRequest(
            id="self-leave",
            employee_id="manager",
            leave_type_id="sick",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 1),
            total_days=1,
            status="pending",
        )
        db.add_all([leave_type, request])
        db.commit()

    response = task6_context["client"].post(
        "/inbox/leave-requests/self-leave/approve",
        headers=_bearer(task6_context, "manager", **{"X-User-Id": "admin", "X-User-Email": "admin@example.com"}),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot review your own leave request"


def test_timesheet_decision_revalidates_self_approval_despite_spoofed_headers(task6_context):
    with task6_context["Session"]() as db:
        db.add(TimesheetEntry(
            id="self-timesheet",
            employee_id="manager",
            work_date=date(2026, 7, 27),
            week_start=date(2026, 7, 26),
            entry_code="ADM",
            project_name="Administration",
            hours=8,
            status="submitted",
        ))
        db.commit()

    response = task6_context["client"].post(
        "/timesheets/approvals/manager/2026-07-26/decision",
        headers=_bearer(task6_context, "manager", **{"X-User-Id": "admin", "X-User-Email": "admin@example.com"}),
        json={"decision": "approve"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot review your own timesheet."


def test_announcement_creation_and_audit_attribution_are_bearer_derived(task6_context, monkeypatch):
    audit_actor_ids: list[str] = []
    monkeypatch.setattr(
        announcements,
        "log_audit",
        lambda _db, actor, **_kwargs: audit_actor_ids.append(actor.id),
    )
    response = task6_context["client"].post(
        "/announcements",
        headers=_bearer(task6_context, "hr_admin", **{"X-User-Id": "employee", "X-User-Email": "employee@example.com"}),
        json={"title": "Fixed", "message": "Synthetic", "status": "draft"},
    )
    assert response.status_code == 200
    assert response.json()["announcement"]["created_by"] == "hr-admin@example.com"
    assert audit_actor_ids == ["hr-admin"]
