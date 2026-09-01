from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import admin_security, admin_time_off, audit_logs, certificates, client_onboarding, hr_documents
from app.core import authentication
from app.core.authentication import create_access_token, get_authenticated_actor
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.certificate import Certificate, CertificateAuditLog
from app.models.client_onboarding import (
    Client as OnboardingClient,
    ClientActivityLog,
    ClientChecklistItem,
    ClientDocument,
    ClientMilestone,
    ClientOnboarding,
    ClientTask,
    ClientTeamMember,
)
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.organization import Department, Designation
from app.models.transactional_email import SecurityRateLimit


TASK7_MODULES = (admin_security, admin_time_off, audit_logs, certificates, hr_documents, client_onboarding)
PUBLIC_ROUTES = {("GET", "/certificates/verify/{cert_id}")}


def _dependency_calls(route: APIRoute):
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop()
        yield dependency.call
        pending.extend(dependency.dependencies)


def _employee(employee_id: str, role: str) -> Employee:
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
        reporting_manager="",
        joining_date=date(2025, 1, 1),
        date_of_joining=date(2025, 1, 1),
        work_location="US",
    )


@pytest.fixture()
def task7_context(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Department.__table__,
            Designation.__table__,
            Employee.__table__,
            Certificate.__table__,
            CertificateAuditLog.__table__,
            SecurityRateLimit.__table__,
            LeaveType.__table__,
            LeaveRequest.__table__,
            OnboardingClient.__table__,
            ClientOnboarding.__table__,
            ClientChecklistItem.__table__,
            ClientTask.__table__,
            ClientTeamMember.__table__,
            ClientDocument.__table__,
            ClientMilestone.__table__,
            ClientActivityLog.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    actors = {
        "employee": _employee("employee", "employee"),
        "unrelated": _employee("unrelated", "employee"),
        "manager": _employee("manager", "manager"),
        "hr_admin": _employee("hr-admin", "hr_admin"),
        "admin": _employee("admin", "admin"),
        "global_access": _employee("global-access", "global_access"),
        "super_admin": _employee("super-admin", "super_admin"),
        "audit_viewer": _employee("audit-viewer", "audit_viewer"),
    }
    with Session() as db:
        db.add_all(actors.values())
        db.commit()
        monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "task-seven-secret-that-is-long-enough")
        tokens = {name: create_access_token(actor) for name, actor in actors.items()}

    app = FastAPI()
    for module in TASK7_MODULES:
        app.include_router(module.router)

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(audit_logs, "log_authorization_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(certificates, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(certificates, "get_certificate_verification", lambda _cert_id: None)
    monkeypatch.setattr(certificates, "sync_legacy_certificates", lambda _db: None)
    monkeypatch.setattr(admin_time_off, "log_central_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(admin_time_off, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(client_onboarding, "log_audit", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    yield {"client": client, "Session": Session, "tokens": tokens}
    client.close()
    engine.dispose()


def _bearer(context, actor: str, **spoofed: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {context['tokens'][actor]}"}
    headers.update(spoofed)
    return headers


def test_every_task7_management_route_uses_central_auth_and_only_verification_is_public():
    app = FastAPI()
    for module in TASK7_MODULES:
        app.include_router(module.router)

    protected = set()
    public = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            key = (method, route.path)
            if get_authenticated_actor in set(_dependency_calls(route)):
                protected.add(key)
            else:
                public.add(key)

    assert public == PUBLIC_ROUTES
    assert len(protected) == 40


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/admin/security/locked-accounts"),
        ("get", "/admin/time-off/dashboard"),
        ("get", "/audit-logs"),
        ("get", "/certificates/meta"),
        ("get", "/certificates/next-serial?certificate_type=Internship&year=2026"),
        ("post", "/hr-documents/internship-completion"),
        ("get", "/admin/client-onboarding"),
    ],
)
def test_each_administrative_domain_requires_bearer(task7_context, method, path):
    response = task7_context["client"].request(method, path)
    assert response.status_code == 401


def test_spoofed_admin_headers_do_not_elevate_an_employee(task7_context):
    headers = _bearer(
        task7_context,
        "employee",
        **{
            "X-User-Id": "super-admin",
            "X-User-Email": "super-admin@example.com",
            "X-User-Name": "Super Admin User",
        },
    )
    checks = [
        task7_context["client"].get("/admin/security/locked-accounts", headers=headers),
        task7_context["client"].get("/admin/time-off/dashboard", headers=headers),
        task7_context["client"].get("/audit-logs", headers=headers),
        task7_context["client"].get("/certificates/meta", headers=headers),
        task7_context["client"].get("/admin/client-onboarding", headers=headers),
    ]
    assert [response.status_code for response in checks] == [403, 403, 403, 403, 403]


def test_security_service_receives_the_bearer_actor_and_target_remains_a_target(task7_context, monkeypatch):
    observed: list[tuple[str, str]] = []

    def fake_approve(_db, actor, request_id, _notes):
        observed.append((actor.id, request_id))
        return {"success": True, "message": "approved"}

    monkeypatch.setattr(admin_security, "approve_unlock", fake_approve)
    response = task7_context["client"].post(
        "/admin/security/unlock-requests/target-request/approve",
        headers=_bearer(task7_context, "admin", **{"X-User-Id": "unrelated"}),
        json={"admin_notes": "Reviewed safely"},
    )
    assert response.status_code == 200
    assert observed == [("admin", "target-request")]


def test_audit_view_and_export_role_distinctions_are_preserved(task7_context):
    spoofed = {"X-User-Id": "super-admin", "X-User-Email": "super-admin@example.com"}
    assert task7_context["client"].get("/audit-logs", headers=_bearer(task7_context, "admin", **spoofed)).status_code == 403
    assert task7_context["client"].get("/audit-logs/export", headers=_bearer(task7_context, "hr_admin", **spoofed)).status_code == 403
    assert audit_logs.can_view_audit("hr_admin")
    assert audit_logs.can_view_audit("global_access")
    assert not audit_logs.can_view_audit("admin")
    assert not audit_logs.can_view_audit("audit_viewer")


def test_certificate_management_is_protected_while_verification_remains_public(task7_context):
    public_response = task7_context["client"].get(
        "/certificates/verify/UNKNOWN",
        headers={"X-User-Id": "super-admin", "X-User-Email": "super-admin@example.com"},
    )
    assert public_response.status_code == 200
    assert public_response.json() == {
        "valid": False,
        "certificate_code": "UNKNOWN",
        "status": "not_found",
        "message": "Certificate not found in ReKnew records.",
    }
    assert task7_context["client"].get("/certificates", headers=_bearer(task7_context, "admin")).status_code == 200


def test_public_certificate_verification_excludes_management_fields(task7_context):
    with task7_context["Session"]() as db:
        db.add(
            Certificate(
                certificate_code="PUBLIC-2026-0001",
                learner_name="Public Learner",
                course_name="Public Course",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                issue_date=date(2026, 2, 1),
                status="valid",
                verification_url="https://internal.example.invalid/verify/PUBLIC-2026-0001",
                pdf_url="C:/private/certificates/PUBLIC-2026-0001.pdf",
                issued_by="ReKnew",
            )
        )
        db.commit()

    response = task7_context["client"].get("/certificates/verify/PUBLIC-2026-0001")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["certificate_code"] == "PUBLIC-2026-0001"
    assert "verification_url" not in body
    assert "pdf_url" not in body


def test_admin_time_off_preserves_self_approval_prevention(task7_context):
    with task7_context["Session"]() as db:
        leave_type = LeaveType(id="sick", name="Sick Leave", code="SL")
        leave_request = LeaveRequest(
            id="admin-own-leave",
            employee_id="admin",
            leave_type_id="sick",
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 3),
            total_days=1,
            status="pending",
        )
        db.add_all([leave_type, leave_request])
        db.commit()

    response = task7_context["client"].post(
        "/admin/time-off/leave-requests/admin-own-leave/decision",
        headers=_bearer(task7_context, "admin", **{"X-User-Id": "super-admin"}),
        json={"decision": "approve"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot review your own leave request."


def test_certificate_revocation_is_attributed_to_bearer_actor(task7_context):
    with task7_context["Session"]() as db:
        db.add(
            Certificate(
                certificate_code="RK-2026-0001",
                learner_name="Synthetic Learner",
                course_name="Synthetic Course",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                issue_date=date(2026, 2, 1),
                status="valid",
                verification_url="https://example.invalid/verify/RK-2026-0001",
            )
        )
        db.commit()

    response = task7_context["client"].post(
        "/certificates/RK-2026-0001/revoke",
        headers=_bearer(task7_context, "admin", **{"X-User-Id": "unrelated"}),
    )
    assert response.status_code == 200
    with task7_context["Session"]() as db:
        audit = db.query(CertificateAuditLog).one()
        assert audit.performed_by == "admin"
        assert db.query(Certificate).one().status == "revoked"


def test_client_owner_is_a_target_while_creation_is_attributed_to_bearer_actor(task7_context):
    response = task7_context["client"].post(
        "/admin/client-onboarding",
        headers=_bearer(task7_context, "admin", **{"X-User-Id": "unrelated"}),
        json={
            "client_name": "Synthetic Client",
            "industry": "Testing",
            "primary_contact_name": "Synthetic Contact",
            "contact_email": "contact@example.com",
            "owner_id": "unrelated",
        },
    )
    assert response.status_code == 200
    with task7_context["Session"]() as db:
        client = db.query(OnboardingClient).one()
        assert client.owner_id == "unrelated"
        assert client.created_by == "admin"
        assert client.updated_by == "admin"
        activity = db.query(ClientActivityLog).one()
        assert activity.performed_by == "admin"


def test_hr_generation_uses_bearer_actor_for_sensitive_access(task7_context, monkeypatch):
    observed: list[str] = []
    monkeypatch.setattr(hr_documents, "generate_internship_completion_pdf", lambda _request: b"safe-pdf")
    monkeypatch.setattr(
        hr_documents,
        "log_sensitive_access",
        lambda _db, actor, **_kwargs: observed.append(actor.id),
    )
    response = task7_context["client"].post(
        "/hr-documents/internship-completion?format=pdf",
        headers=_bearer(task7_context, "hr_admin", **{"X-User-Id": "employee"}),
        json={
            "intern_name": "Synthetic Intern",
            "programme": "Synthetic Programme",
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
            "issued_date": "2026-02-02",
            "responsibility_summary": "Synthetic fixed test content.",
        },
    )
    assert response.status_code == 200
    assert response.content == b"safe-pdf"
    assert observed == ["hr-admin"]
