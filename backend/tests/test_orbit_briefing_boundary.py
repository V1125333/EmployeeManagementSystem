from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import orbit_ai
from app.core import authentication
from app.core.authentication import create_access_token
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday, Notification, TimesheetEntry
from app.models.organization import Department, Designation


def _employee(employee_id: str, email: str, *, manager_id: str | None = None) -> Employee:
    return Employee(
        id=employee_id,
        first_name=employee_id.title(),
        last_name="Tester",
        work_email=email,
        phone="1000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        manager_id=manager_id,
        joining_date=date(2025, 1, 1),
        work_location="India",
    )


@pytest.fixture()
def orbit_context(monkeypatch):
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
            Notification.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    manager = _employee("manager-1", "manager@example.com")
    owner = _employee("owner-1", "owner@example.com", manager_id=manager.id)
    other = _employee("other-1", "other@example.com", manager_id=manager.id)
    leave_type = LeaveType(id="sick-leave", name="Sick Leave", code="SL")
    today = date.today()
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    owner_entry = TimesheetEntry(
        id="owner-entry",
        employee_id=owner.id,
        work_date=week_start + timedelta(days=1),
        week_start=week_start,
        entry_code="REG",
        project_name="Orbit",
        hours=4,
        status="draft",
        time_zone="Asia/Kolkata",
    )
    other_entry = TimesheetEntry(
        id="other-entry",
        employee_id=other.id,
        work_date=week_start + timedelta(days=1),
        week_start=week_start,
        entry_code="REG",
        project_name="Private",
        hours=7,
        status="draft",
    )
    owner_leave = LeaveRequest(
        id="owner-leave-id",
        employee_id=owner.id,
        leave_type_id=leave_type.id,
        start_date=today + timedelta(days=4),
        end_date=today + timedelta(days=4),
        total_days=1,
        status="pending",
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    other_leave = LeaveRequest(
        id="other-leave-id",
        employee_id=other.id,
        leave_type_id=leave_type.id,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=5),
        total_days=1,
        status="pending",
    )
    holidays = [
        CompanyHoliday(name="India Holiday", holiday_date=today + timedelta(days=3), regions="IN"),
        CompanyHoliday(name="US Holiday", holiday_date=today + timedelta(days=1), regions="US"),
    ]
    db.add_all([manager, owner, other, leave_type, owner_entry, other_entry, owner_leave, other_leave, *holidays])
    db.commit()

    def override_db():
        yield db

    audit_events: list[dict] = []
    app = FastAPI()
    app.include_router(orbit_ai.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "orbit-boundary-secret-that-is-long-enough")
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        orbit_ai,
        "log_audit",
        lambda *_args, **kwargs: audit_events.append(kwargs),
    )
    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "owner": owner,
        "other": other,
        "token": create_access_token(owner),
        "other_token": create_access_token(other),
        "events": audit_events,
    }
    db.close()
    engine.dispose()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _business_snapshot(db) -> tuple[list[tuple[str, str, object]], int]:
    rows = db.query(TimesheetEntry).order_by(TimesheetEntry.id).all()
    return (
        [(row.id, row.status, row.submitted_at) for row in rows],
        db.query(Notification).count(),
    )


@pytest.mark.parametrize("path", ["/api/v1/me/action-items", "/api/v1/me/upcoming"])
def test_briefing_gets_require_bearer_authentication(orbit_context, path):
    response = orbit_context["client"].get(path)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_action_items_are_owner_scoped_read_only_and_navigation_only(orbit_context):
    db = orbit_context["db"]
    before = _business_snapshot(db)
    response = orbit_context["client"].get(
        "/api/v1/me/action-items",
        headers={
            **_bearer(orbit_context["token"]),
            "X-User-Id": orbit_context["other"].id,
            "X-User-Email": orbit_context["other"].work_email,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert {item["key"] for item in payload["items"]} == {
        "timesheet_attention",
        "leave_request_waiting",
    }
    serialized = str(payload)
    assert "owner-leave-id" not in serialized
    assert "other-leave-id" not in serialized
    assert "intent" not in serialized
    assert "secondaryAction" not in serialized
    assert "undo" not in serialized.lower()
    assert all(item["primaryAction"]["type"] == "navigate" for item in payload["items"])
    assert all(item["primaryAction"]["href"].startswith("/employee/") for item in payload["items"])
    assert _business_snapshot(db) == before


def test_upcoming_is_actor_region_scoped_and_ignores_spoof_headers(orbit_context):
    response = orbit_context["client"].get(
        "/api/v1/me/upcoming",
        headers={**_bearer(orbit_context["token"]), "X-User-Id": orbit_context["other"].id},
    )
    assert response.status_code == 200
    assert response.json()["item"]["title"] == "India Holiday"


@pytest.mark.parametrize(
    "item_id",
    ["timesheet:2099-01-01", "leave:other-leave-id", "malformed", "leave:not-a-uuid"],
)
def test_execute_compatibility_boundary_always_returns_410_without_business_writes(orbit_context, item_id):
    db = orbit_context["db"]
    before = _business_snapshot(db)
    response = orbit_context["client"].post(
        f"/api/v1/me/action-items/{item_id}/execute",
        headers=_bearer(orbit_context["token"]),
        json={"ignored": "payload"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "ORBIT_ACTION_TEMPORARILY_DISABLED"
    assert response.json()["detail"]["correlation_id"]
    assert _business_snapshot(db) == before


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/v1/me/undo", None),
        ("/api/v1/me/undo", {"undoToken": "sensitive-token-value"}),
        ("/api/v1/me/action-items/leave:other-leave-id/undo", {"undoToken": "not-valid"}),
        ("/api/v1/me/action-items/malformed/undo", "not-json"),
    ],
)
def test_undo_compatibility_boundaries_ignore_body_and_return_410_without_business_writes(orbit_context, path, body):
    db = orbit_context["db"]
    before = _business_snapshot(db)
    response = orbit_context["client"].post(
        path,
        headers=_bearer(orbit_context["token"]),
        json=body,
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "ORBIT_UNDO_TEMPORARILY_DISABLED"
    assert _business_snapshot(db) == before


def test_disabled_attempt_audit_is_bounded_and_contains_no_ids_or_tokens(orbit_context):
    client = orbit_context["client"]
    secret_value = "very-sensitive-undo-token"
    client.post(
        "/api/v1/me/action-items/leave:other-leave-id/undo",
        headers={**_bearer(orbit_context["token"]), "X-User-Email": "spoof@example.com"},
        json={"undoToken": secret_value},
    )
    event = orbit_context["events"][-1]
    assert event["action"] == "orbit.legacy_undo.disabled"
    assert event["metadata"]["category"] == "leave"
    serialized = str(event)
    assert "other-leave-id" not in serialized
    assert secret_value not in serialized
    assert "spoof@example.com" not in serialized


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/me/action-items/timesheet:any/execute",
        "/api/v1/me/undo",
        "/api/v1/me/action-items/leave:any/undo",
    ],
)
def test_disabled_mutation_routes_require_bearer_authentication(orbit_context, path):
    response = orbit_context["client"].post(path, json={"undoToken": "x"})
    assert response.status_code == 401
