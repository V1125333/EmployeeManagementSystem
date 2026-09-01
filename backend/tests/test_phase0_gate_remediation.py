from __future__ import annotations

from datetime import date, timedelta
import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import allocations, auth, certificates, dashboard, projects
from app.core import authentication
from app.core.authentication import create_access_token
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import documentation_paths
from app.models.allocation import Allocation
from app.models.certificate import Certificate, CertificateAuditLog
from app.models.employee import Employee
from app.models.leave_attendance import Attendance, AttendanceCorrection, LeaveRequest
from app.models.operations import Announcement, Project, ProjectDocument
from app.models.organization import Department, Designation
from app.models.transactional_email import AccountActivationToken, SecurityRateLimit
from app.services import project_service


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
        joining_date=date.today(),
        date_of_joining=date.today(),
        work_location="US",
    )


@pytest.fixture()
def gate_context(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Department.__table__,
        Designation.__table__,
        Employee.__table__,
        Project.__table__,
        Allocation.__table__,
        ProjectDocument.__table__,
        Announcement.__table__,
        LeaveRequest.__table__,
        Attendance.__table__,
        AttendanceCorrection.__table__,
        Certificate.__table__,
        CertificateAuditLog.__table__,
        AccountActivationToken.__table__,
        SecurityRateLimit.__table__,
    ])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    actors = {
        "employee": _employee("employee", "employee"),
        "allocated": _employee("allocated", "employee"),
        "unrelated": _employee("unrelated", "employee"),
        "manager": _employee("manager", "manager"),
        "unrelated_manager": _employee("unrelated-manager", "manager"),
        "report": _employee("report", "employee", manager_id="manager"),
        "hr_admin": _employee("hr-admin", "hr_admin"),
        "admin": _employee("admin", "admin"),
    }
    with Session() as db:
        db.add_all(actors.values())
        db.add_all([
            Project(id="project-one", name="Project One", code="P1", status="active", project_manager_id="manager"),
            Project(id="project-two", name="Project Two", code="P2", status="active", project_manager_id="unrelated-manager"),
            Allocation(
                id="allocation-one", employee_id="allocated", project_id="project-one", project_name="Project One",
                manager_id="manager", allocation_percentage=100, allocation_role="Engineer", billing_type="billable",
                status="active", start_date=date.today() - timedelta(days=1), end_date=None, created_by="admin",
            ),
            Allocation(
                id="allocation-two", employee_id="unrelated", project_id="project-two", project_name="Project Two",
                manager_id="unrelated-manager", allocation_percentage=100, allocation_role="Engineer", billing_type="billable",
                status="active", start_date=date.today() - timedelta(days=1), end_date=None, created_by="admin",
            ),
            ProjectDocument(
                id="document-one", project_id="project-one", uploaded_by_id="admin", original_file_name="one.txt",
                stored_file_name="one.txt", mime_type="text/plain", storage_path="project-one/one.txt", document_type="OTHER",
            ),
            ProjectDocument(
                id="document-two", project_id="project-two", uploaded_by_id="admin", original_file_name="two.txt",
                stored_file_name="two.txt", mime_type="text/plain", storage_path="project-two/two.txt", document_type="OTHER",
            ),
            Certificate(
                certificate_code="CERT-ONE", learner_name="Learner One", course_name="Course One",
                start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), issue_date=date(2026, 1, 3),
                status="valid", verification_url="https://internal/verify/CERT-ONE", pdf_url="private/path.pdf",
            ),
        ])
        db.commit()
        monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "phase-zero-gate-secret-that-is-long-enough")
        tokens = {name: create_access_token(actor) for name, actor in actors.items()}

    app = FastAPI()
    for router in (dashboard.router, projects.router, allocations.router, auth.router, certificates.router):
        app.include_router(router, prefix="/api/v1")

    def override_db():
        with Session() as db:
            yield db

    class Storage:
        @staticmethod
        def download_file(path: str) -> bytes:
            return path.encode()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(certificates, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(project_service, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(project_service, "get_storage", lambda: Storage())
    client = TestClient(app)
    yield {"client": client, "Session": Session, "tokens": tokens, "actors": actors}
    client.close()
    engine.dispose()


def _bearer(context, actor: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {context['tokens'][actor]}", **extra}


def test_normal_startup_has_no_automatic_or_predictable_administrator():
    from app import main

    source = inspect.getsource(main)
    assert not hasattr(main, "seed_admin")
    assert "hash_password(\"test\")" not in source
    assert "superadmin@reknew.ai / test" not in source
    assert "password = \"test\"" not in source


def test_documentation_paths_are_development_only_and_operational_payloads_are_minimal():
    assert documentation_paths("development")["openapi_url"] == "/openapi.json"
    assert documentation_paths("production") == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
        "swagger_ui_oauth2_redirect_url": None,
    }


@pytest.mark.parametrize(
    "path",
    ["kpis", "pending-tasks", "announcements", "department-chart", "attendance-trend", "on-leave-today", "leave-calendar"],
)
def test_all_dashboard_routes_reject_anonymous_requests(gate_context, path):
    assert gate_context["client"].get(f"/api/v1/dashboard/{path}").status_code == 401


def test_dashboard_role_scope_and_spoofed_headers(gate_context):
    client = gate_context["client"]
    assert client.get("/api/v1/dashboard/kpis", headers=_bearer(gate_context, "employee")).status_code == 403
    spoofed = _bearer(gate_context, "employee", **{"X-User-Role": "super_admin", "X-User-Id": "admin"})
    assert client.get("/api/v1/dashboard/kpis", headers=spoofed).status_code == 403
    assert client.get("/api/v1/dashboard/announcements", headers=_bearer(gate_context, "employee")).status_code == 200

    manager_payload = client.get("/api/v1/dashboard/kpis", headers=_bearer(gate_context, "manager")).json()
    detail_names = {
        item["name"]
        for kpi in manager_payload["kpis"]
        for item in kpi.get("details", [])
    }
    assert "Report User" in detail_names
    assert "Unrelated User" not in detail_names
    assert client.get("/api/v1/dashboard/kpis", headers=_bearer(gate_context, "hr_admin")).status_code == 200
    assert client.get("/api/v1/dashboard/kpis", headers=_bearer(gate_context, "admin")).status_code == 200


@pytest.mark.parametrize("actor", ["allocated", "manager", "hr_admin", "admin"])
def test_explicit_project_readers_can_list_allocations_and_documents(gate_context, actor):
    headers = _bearer(gate_context, actor)
    assert gate_context["client"].get("/api/v1/allocations/project/project-one", headers=headers).status_code == 200
    assert gate_context["client"].get("/api/v1/projects/project-one/documents", headers=headers).status_code == 200
    assert gate_context["client"].get(
        "/api/v1/projects/project-one/documents/document-one/download", headers=headers
    ).status_code == 200


@pytest.mark.parametrize("actor", ["employee", "unrelated", "unrelated_manager"])
def test_unrelated_actors_cannot_guess_project_allocations_or_documents(gate_context, actor):
    headers = _bearer(gate_context, actor)
    assert gate_context["client"].get("/api/v1/allocations/project/project-one", headers=headers).status_code == 403
    assert gate_context["client"].get("/api/v1/projects/project-one/documents", headers=headers).status_code == 403
    assert gate_context["client"].get(
        "/api/v1/projects/project-one/documents/document-one/download", headers=headers
    ).status_code == 403
    assert gate_context["client"].get(
        "/api/v1/projects/project-one/documents/document-two/download", headers=headers
    ).status_code == 403


def test_project_document_writes_remain_admin_only(gate_context):
    response = gate_context["client"].delete(
        "/api/v1/projects/project-one/documents/document-one",
        headers=_bearer(gate_context, "allocated"),
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("path", "payload", "code"),
    [
        ("/api/v1/auth/check-email", {"email": "{email}"}, "ACCOUNT_DISCOVERY_RETIRED"),
        ("/api/v1/auth/login", {"email": "{email}", "password": "not-a-password", "totp_code": "000000"}, "LEGACY_LOGIN_RETIRED"),
        ("/api/v1/auth/forgot-password", {"email": "{email}", "totp_code": "000000", "new_password": "new-password"}, "LEGACY_PASSWORD_RESET_RETIRED"),
    ],
)
def test_retired_auth_routes_are_non_enumerating(gate_context, path, payload, code):
    responses = []
    for email in ("employee@example.com", "missing@example.com"):
        response = gate_context["client"].post(path, json={key: value.format(email=email) for key, value in payload.items()})
        responses.append((response.status_code, response.json()))
    assert responses[0] == responses[1]
    assert responses[0][0] == 410
    assert responses[0][1]["detail"]["code"] == code


def test_public_auth_rate_limit_is_durable_and_does_not_trust_forwarded_for(gate_context, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_AUTH_ATTEMPTS_PER_HOUR", 2)
    payload = {"email": "employee@example.com", "setup_code": "wrong"}
    client = gate_context["client"]
    first = client.post("/api/v1/auth/verify-setup-code", json=payload, headers={"X-Forwarded-For": "1.1.1.1"})
    second = client.post("/api/v1/auth/verify-setup-code", json=payload, headers={"X-Forwarded-For": "2.2.2.2"})
    third = client.post("/api/v1/auth/verify-setup-code", json=payload, headers={"X-Forwarded-For": "3.3.3.3"})
    assert first.status_code == second.status_code == 200
    assert third.status_code == 429


def test_public_certificate_response_is_minimized_and_repeated_writes_are_bounded(gate_context, monkeypatch):
    monkeypatch.setattr(settings, "CERTIFICATE_VERIFY_RATE_LIMIT_PER_HOUR", 2)
    client = gate_context["client"]
    first = client.get("/api/v1/certificates/verify/CERT-ONE")
    second = client.get("/api/v1/certificates/verify/CERT-ONE")
    third = client.get("/api/v1/certificates/verify/CERT-ONE")
    assert first.status_code == second.status_code == 200
    assert third.status_code == 429
    assert "pdf_url" not in first.json()
    assert "verification_url" not in first.json()
    with gate_context["Session"]() as db:
        limiter = db.query(SecurityRateLimit).filter(SecurityRateLimit.scope == "public_certificate_verify").one()
        assert limiter.count == 2
