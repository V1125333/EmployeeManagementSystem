from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.authentication import AuthenticatedPrincipal
from app.core.authorization import (
    ADMIN_ROLES,
    AUDIT_VIEWER_ROLES,
    has_any_role,
    is_self_or_authorized_role,
    normalize_role,
    require_roles,
    require_self_or_roles,
)


def principal(role: str = "employee", employee_id: str = "employee-1"):
    return AuthenticatedPrincipal(
        employee_id=employee_id,
        email="employee@example.com",
        role=role,
        status="active",
        permissions=frozenset(),
        token_id="token-id",
    )


class RecordingSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def request_with_sensitive_headers() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/protected",
            "headers": [
                (b"authorization", b"Bearer secret.jwt.value"),
                (b"x-user-id", b"spoofed-admin-id"),
                (b"x-user-email", b"admin@example.com"),
                (b"user-agent", b"pytest"),
            ],
            "client": ("127.0.0.1", 1234),
        }
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HR Admin", "hr_admin"),
        ("global-access", "global_access"),
        (" manager ", "manager"),
        (None, ""),
    ],
)
def test_role_normalization_is_spelling_only(raw, expected):
    assert normalize_role(raw) == expected


def test_role_normalization_does_not_broaden_privileges():
    assert has_any_role(principal("administrator"), ADMIN_ROLES) is False
    assert has_any_role(principal("admin assistant"), ADMIN_ROLES) is False
    assert has_any_role(principal("admin"), AUDIT_VIEWER_ROLES) is False
    assert has_any_role(principal("HR Admin"), ADMIN_ROLES) is True


def test_self_or_authorized_role_is_explicit():
    employee = principal("employee")
    manager = principal("manager", "manager-1")

    assert is_self_or_authorized_role(employee, "employee-1", ADMIN_ROLES)
    assert not is_self_or_authorized_role(employee, "employee-2", ADMIN_ROLES)
    assert not is_self_or_authorized_role(manager, "employee-2", ADMIN_ROLES)
    assert is_self_or_authorized_role(
        principal("hr_admin", "hr-1"), "employee-2", ADMIN_ROLES
    )


def test_require_roles_returns_principal_when_allowed():
    allowed = principal("HR Admin")
    assert require_roles(allowed, *ADMIN_ROLES) is allowed


def test_authorization_denial_is_sanitized_and_audited():
    db = RecordingSession()
    request = request_with_sensitive_headers()

    with pytest.raises(HTTPException) as exc_info:
        require_roles(
            principal("employee"),
            *ADMIN_ROLES,
            db=db,
            request=request,
            action="employee.export",
            entity_type="employee",
        )

    assert exc_info.value.status_code == 403
    assert db.commits == 1
    assert len(db.added) == 1
    audit = db.added[0]
    serialized = json.dumps(
        {
            "reason": audit.reason,
            "metadata": audit.metadata_json,
            "action": audit.action,
        }
    )
    assert "secret.jwt.value" not in serialized
    assert "spoofed-admin-id" not in serialized
    assert "admin@example.com" not in serialized
    assert audit.action == "employee.export.denied"
    assert audit.metadata_json["security_event"] is True
    assert audit.metadata_json["correlation_id"]


def test_reason_redaction_defends_against_future_caller_mistakes():
    db = RecordingSession()
    with pytest.raises(HTTPException):
        require_self_or_roles(
            principal("employee"),
            "employee-2",
            *ADMIN_ROLES,
            db=db,
            reason=(
                "Bearer secret.jwt.value "
                "X-User-Id=spoofed-admin-id "
                "X-User-Email=admin@example.com"
            ),
        )

    assert db.added
    assert "secret.jwt.value" not in db.added[0].reason
    assert "spoofed-admin-id" not in db.added[0].reason
    assert "admin@example.com" not in db.added[0].reason
