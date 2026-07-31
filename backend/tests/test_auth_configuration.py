from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest

from app.core.authentication import create_access_token, decode_access_token
from app.core.config import (
    BACKEND_ENV_FILE,
    BACKEND_ROOT,
    settings,
    validate_security_settings,
)
from app.services import auth_service


def test_backend_environment_file_is_explicit():
    assert BACKEND_ROOT == Path(__file__).resolve().parents[1]
    assert BACKEND_ENV_FILE == BACKEND_ROOT / ".env"


def test_missing_jwt_secret_fails_with_backend_env_path(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "")

    with pytest.raises(RuntimeError) as exc_info:
        validate_security_settings()

    message = str(exc_info.value)
    assert "AUTH_JWT_SECRET is required" in message
    assert str(BACKEND_ENV_FILE) in message


def test_short_jwt_secret_fails_clearly(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "too-short")

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_security_settings()


def test_token_signing_and_verification_use_same_setting(monkeypatch):
    signing_secret = "a" * 48
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", signing_secret)
    token = create_access_token(SimpleNamespace(id="employee-1"))

    assert decode_access_token(token)["sub"] == "employee-1"

    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "b" * 48)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_no_mfa_super_admin_password_login_returns_signed_token(monkeypatch):
    employee = SimpleNamespace(
        id="super-admin-1",
        first_name="Super",
        last_name="Admin",
        work_email="superadmin@example.com",
        role="super_admin",
        department="People",
        profile_image_url=None,
        force_password_change=False,
        account_locked=False,
        is_active=True,
        is_first_login=False,
        password_hash="stored-password-hash",
        totp_secret=None,
        failed_login_attempts=0,
        last_login_at=None,
    )

    class FakeSession:
        def commit(self):
            return None

    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "c" * 48)
    monkeypatch.setattr(auth_service, "find_employee_by_email", lambda _db, _email: employee)
    monkeypatch.setattr(auth_service, "verify_password", lambda _password, _hash: True)
    monkeypatch.setattr(auth_service, "get_or_create_preferences", lambda _db, _id: None)
    monkeypatch.setattr(auth_service, "_audit", lambda *_args, **_kwargs: None)

    response = auth_service.verify_login_password(
        FakeSession(),
        employee.work_email,
        "correct-password",
    )

    assert response["success"] is True
    assert response["employee"]["id"] == employee.id
    assert decode_access_token(response["token"])["sub"] == employee.id
