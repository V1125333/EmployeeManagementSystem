from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.core import authentication
from app.core.authentication import create_access_token
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.employee import Employee
from app.models.organization import Department, Designation
from app.models.password_reset import PasswordResetSession
from app.models.unlock_request import AccountUnlockRequest
from app.services import auth_service


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def employee(employee_id: str, email: str, role: str, **values) -> Employee:
    defaults = {
        "id": employee_id,
        "first_name": employee_id.title(),
        "last_name": "User",
        "work_email": email,
        "phone": "1000000000",
        "workforce_type": "full_time",
        "role": role,
        "employment_status": "active",
        "is_active": True,
        "account_locked": False,
        "force_password_change": False,
        "joining_date": date(2025, 1, 1),
        "department": "Engineering",
        "designation": "Engineer",
        "reporting_manager": "Admin User",
    }
    defaults.update(values)
    return Employee(**defaults)


@pytest.fixture()
def auth_context(monkeypatch):
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
            PasswordResetSession.__table__,
            AccountUnlockRequest.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    admin = employee("admin-1", "admin@example.com", "super_admin")
    manager = employee("manager-1", "manager@example.com", "manager")
    target = employee(
        "target-1",
        "target@example.com",
        "employee",
        account_locked=True,
        personal_email="target.personal@example.net",
        totp_secret="never-return-this-secret",
        setup_code="NEVER-RETURN",
    )
    forced = employee(
        "forced-1",
        "forced@example.com",
        "employee",
        force_password_change=True,
        password_hash=auth_service.hash_password("Temporary1!"),
    )
    regular = employee(
        "regular-1",
        "regular@example.com",
        "employee",
        password_hash=auth_service.hash_password("CurrentPass1!"),
    )
    db.add_all([admin, manager, target, forced, regular])
    db.commit()

    audit_calls: list[dict] = []

    def capture_audit(*args, **kwargs):
        audit_calls.append({"args": args[1:], "kwargs": kwargs})

    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "task-three-secret-that-is-long-enough-123")
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_service, "_audit", capture_audit)
    monkeypatch.setattr(auth_service, "notify_admins_unlock_requested", lambda *_args, **_kwargs: None)

    def override_db():
        yield db

    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "admin": admin,
        "manager": manager,
        "target": target,
        "forced": forced,
        "tokens": {
            "admin": create_access_token(admin),
            "manager": create_access_token(manager),
            "target": create_access_token(target),
            "forced": create_access_token(forced),
            "regular": create_access_token(regular),
        },
        "audit_calls": audit_calls,
        "regular": regular,
    }
    db.close()
    engine.dispose()


def test_current_profile_requires_bearer_and_uses_jwt_subject(auth_context):
    client = auth_context["client"]
    assert client.get("/api/v1/auth/me").status_code == 401

    response = client.get(
        "/api/v1/auth/me?email=admin@example.com&employee_id=admin-1",
        headers={
            **bearer(auth_context["tokens"]["manager"]),
            "X-User-Id": "admin-1",
            "X-User-Email": "admin@example.com",
            "X-User-Name": "Spoofed Admin",
        },
    )
    assert response.status_code == 200
    profile = response.json()["employee"]
    assert profile["id"] == auth_context["manager"].id
    assert profile["work_email"] == auth_context["manager"].work_email


def test_current_profile_is_bounded_and_excludes_credentials(auth_context):
    auth_context["target"].account_locked = False
    auth_context["db"].commit()
    response = auth_context["client"].get(
        "/api/v1/auth/me", headers=bearer(auth_context["tokens"]["target"])
    )
    assert response.status_code == 200
    profile = response.json()["employee"]
    assert profile["personal_email"] == "target.personal@example.net"
    forbidden = {
        "password_hash",
        "totp_secret",
        "setup_code",
        "failed_reset_attempts",
        "locked_until",
        "unlocked_by_user_id",
    }
    assert forbidden.isdisjoint(profile)
    assert "never-return-this-secret" not in response.text
    assert "NEVER-RETURN" not in response.text


@pytest.mark.parametrize("email", ["target@example.com", "missing@example.com"])
def test_arbitrary_email_profile_lookup_is_retired(auth_context, email):
    response = auth_context["client"].get(f"/api/v1/auth/me/{email}")
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "PROFILE_LOOKUP_RETIRED"
    assert "employee" not in response.json()


def test_forced_password_actor_is_limited_and_clears_required_state(auth_context):
    client = auth_context["client"]
    token = auth_context["tokens"]["forced"]
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 403

    response = client.post(
        "/api/v1/auth/force-change-password",
        headers={
            **bearer(token),
            "X-User-Id": auth_context["target"].id,
            "X-User-Email": auth_context["target"].work_email,
        },
        json={
            "current_password": "Temporary1!",
            "new_password": "Permanent2@",
            "confirm_password": "Permanent2@",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    auth_context["db"].refresh(auth_context["forced"])
    auth_context["db"].refresh(auth_context["target"])
    assert auth_context["forced"].force_password_change is False
    assert auth_context["target"].account_locked is True
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200


def test_forced_password_rejects_incorrect_current_password_without_secret_audit(auth_context):
    response = auth_context["client"].post(
        "/api/v1/auth/force-change-password",
        headers=bearer(auth_context["tokens"]["forced"]),
        json={
            "current_password": "WrongCurrent9!",
            "new_password": "NewPassword8!",
            "confirm_password": "NewPassword8!",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert auth_context["forced"].force_password_change is True
    serialized = repr(auth_context["audit_calls"])
    assert "WrongCurrent9!" not in serialized
    assert "NewPassword8!" not in serialized


def test_authenticated_user_can_change_password_without_forced_reset(auth_context):
    response = auth_context["client"].post(
        "/api/v1/auth/change-password",
        headers=bearer(auth_context["tokens"]["regular"]),
        json={
            "current_password": "CurrentPass1!",
            "new_password": "UpdatedPass2@",
            "confirm_password": "UpdatedPass2@",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Password changed successfully.",
    }
    auth_context["db"].refresh(auth_context["regular"])
    assert auth_service.verify_password("UpdatedPass2@", auth_context["regular"].password_hash)
    assert auth_context["regular"].force_password_change is False


def test_authenticated_user_change_password_rejects_wrong_current_password(auth_context):
    response = auth_context["client"].post(
        "/api/v1/auth/change-password",
        headers=bearer(auth_context["tokens"]["regular"]),
        json={
            "current_password": "WrongCurrent9!",
            "new_password": "UpdatedPass2@",
            "confirm_password": "UpdatedPass2@",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["message"] == "Current password is incorrect."
    auth_context["db"].refresh(auth_context["regular"])
    assert auth_service.verify_password("CurrentPass1!", auth_context["regular"].password_hash)


def test_admin_reset_requires_bearer_and_strict_role_and_ignores_spoofing(auth_context):
    client = auth_context["client"]
    payload = {"employee_id": auth_context["target"].id, "reason": "Security reset"}
    assert client.post("/api/v1/auth/admin-reset-password", json=payload).status_code == 401

    denied = client.post(
        "/api/v1/auth/admin-reset-password",
        headers={
            **bearer(auth_context["tokens"]["manager"]),
            "X-User-Id": auth_context["admin"].id,
            "X-User-Email": auth_context["admin"].work_email,
        },
        json=payload,
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/v1/auth/admin-reset-password",
        headers=bearer(auth_context["tokens"]["admin"]),
        json=payload,
    )
    assert allowed.status_code == 200
    assert allowed.json()["temporary_password"]
    auth_context["db"].refresh(auth_context["target"])
    assert auth_context["target"].force_password_change is True


def test_admin_reset_target_is_not_an_actor_or_self_service_selector(auth_context):
    response = auth_context["client"].post(
        "/api/v1/auth/admin-reset-password",
        headers=bearer(auth_context["tokens"]["admin"]),
        json={"employee_id": auth_context["admin"].id, "reason": "Self reset"},
    )
    assert response.status_code == 400


def test_colleague_unlock_uses_bearer_requester_and_ignores_spoofed_headers(auth_context):
    client = auth_context["client"]
    payload = {"employee_id": auth_context["target"].id, "reason": "Colleague needs access"}
    assert client.post("/api/v1/auth/request-unlock-for-colleague", json=payload).status_code == 401
    response = client.post(
        "/api/v1/auth/request-unlock-for-colleague",
        headers={
            **bearer(auth_context["tokens"]["manager"]),
            "X-User-Id": auth_context["admin"].id,
            "X-User-Email": auth_context["admin"].work_email,
        },
        json=payload,
    )
    assert response.status_code == 200
    row = auth_context["db"].query(AccountUnlockRequest).one()
    assert row.requested_by_user_id == auth_context["manager"].id
    assert row.locked_user_id == auth_context["target"].id


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/login",
        "/api/v1/auth/check-email",
        "/api/v1/auth/verify-setup-code",
        "/api/v1/auth/forgot-password/initiate",
        "/api/v1/auth/request-unlock",
    ],
)
def test_public_authentication_flows_do_not_require_bearer(auth_context, path):
    response = auth_context["client"].post(path, json={})
    assert response.status_code == 422


def test_auth_audit_adds_correlation_without_credentials_or_legacy_headers(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        auth_service,
        "log_audit",
        lambda **kwargs: captured.update(kwargs),
    )
    db = SimpleNamespace(commit=lambda: None)
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/force-change-password",
        "headers": [
            (b"authorization", b"Bearer secret-token"),
            (b"x-user-email", b"spoofed@example.com"),
        ],
        "client": ("127.0.0.1", 1234),
    })
    auth_service._audit(
        db,
        None,
        "forced_password_change_failed",
        "employee-1",
        reason="Password confirmation did not match",
        request=request,
    )
    assert captured["metadata"]["correlation_id"]
    serialized = repr(captured)
    assert "secret-token" not in serialized
    assert "spoofed@example.com" not in serialized
