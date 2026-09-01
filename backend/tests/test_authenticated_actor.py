from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import authentication
from app.core.authentication import (
    AuthenticatedActor,
    AuthenticatedPrincipal,
    create_access_token,
    get_authenticated_actor,
    get_authenticated_employee,
    get_authenticated_principal,
    get_password_change_actor,
)
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.employee import Employee
from app.models.organization import Department, Designation


@pytest.fixture()
def actor_context(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[Department.__table__, Designation.__table__, Employee.__table__],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    department = Department(id="dept-ai", name="AI", code="AI")
    manager = Employee(
        id="manager-1",
        first_name="Mina",
        last_name="Shah",
        work_email="mina@example.com",
        phone="2000000000",
        workforce_type="full_time",
        role="manager",
        employment_status="active",
        is_active=True,
        account_locked=False,
        joining_date=date(2024, 1, 1),
    )
    employee = Employee(
        id="employee-1",
        first_name="Asha",
        last_name="Rao",
        work_email="asha@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role="HR Admin",
        employment_status="active",
        is_active=True,
        account_locked=False,
        force_password_change=False,
        access_level="elevated",
        manager_id=manager.id,
        department_id=department.id,
        joining_date=date(2025, 1, 1),
    )
    db.add_all([department, manager, employee])
    db.commit()

    def override_db():
        yield db

    app = FastAPI()

    @app.get("/actor")
    def actor_endpoint(actor: AuthenticatedActor = Depends(get_authenticated_actor)):
        return {
            "employee_id": actor.principal.employee_id,
            "email": actor.principal.email,
            "role": actor.principal.role,
            "status": actor.principal.status,
            "access_level": actor.principal.access_level,
            "manager_id": actor.principal.manager_id,
            "department_id": actor.principal.department_id,
            "organization_scope": actor.principal.organization_scope,
            "employee_object_id": actor.employee.id,
        }

    @app.post("/identity/{path_email}")
    def identity_endpoint(
        path_email: str,
        payload: dict,
        actor: AuthenticatedActor = Depends(get_authenticated_actor),
    ):
        return {
            "employee_id": actor.principal.employee_id,
            "email": actor.principal.email,
            "ignored_path_email": path_email,
            "ignored_payload": bool(payload),
        }

    @app.get("/combined")
    def combined_endpoint(
        actor: AuthenticatedActor = Depends(get_authenticated_actor),
        principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
        current_employee: Employee = Depends(get_authenticated_employee),
    ):
        return {
            "actor_id": actor.employee.id,
            "principal_id": principal.employee_id,
            "employee_id": current_employee.id,
        }

    @app.get("/password-change")
    def password_change_endpoint(
        actor: AuthenticatedActor = Depends(get_password_change_actor),
    ):
        return {"employee_id": actor.employee.id}

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "task-one-secret-that-is-long-enough-123")
    monkeypatch.setattr(settings, "AUTH_ORGANIZATION_SCOPE", "reknew-test")
    # Authentication denial persistence is exercised separately from this
    # SQLite fixture; AuditLog uses PostgreSQL JSONB.
    monkeypatch.setattr(authentication, "log_audit", lambda *_args, **_kwargs: None)
    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "engine": engine,
        "employee": employee,
        "manager": manager,
        "token": create_access_token(employee),
    }
    db.close()
    engine.dispose()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def encoded_claims(**overrides) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "employee-1",
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "jti": "test-jti",
    }
    claims.update(overrides)
    return jwt.encode(claims, settings.AUTH_JWT_SECRET, algorithm="HS256")


def test_valid_jwt_resolves_employee_and_server_owned_principal(actor_context):
    response = actor_context["client"].get(
        "/actor", headers=bearer(actor_context["token"])
    )

    assert response.status_code == 200
    assert response.json() == {
        "employee_id": "employee-1",
        "email": "asha@example.com",
        "role": "hr_admin",
        "status": "active",
        "access_level": "elevated",
        "manager_id": "manager-1",
        "department_id": "dept-ai",
        "organization_scope": "reknew-test",
        "employee_object_id": "employee-1",
    }


def test_request_identity_values_cannot_change_actor(actor_context):
    response = actor_context["client"].post(
        "/identity/admin@example.com",
        headers={
            **bearer(actor_context["token"]),
            "X-User-Id": actor_context["manager"].id,
            "X-User-Email": actor_context["manager"].work_email,
            "X-User-Name": "Spoofed Admin",
        },
        json={"employee_id": actor_context["manager"].id, "role": "super_admin"},
    )

    assert response.status_code == 200
    assert response.json()["employee_id"] == "employee-1"
    assert response.json()["email"] == "asha@example.com"


@pytest.mark.parametrize(
    "token",
    [
        lambda: jwt.encode(
            {
                "sub": "employee-1",
                "iss": settings.AUTH_JWT_ISSUER,
                "aud": settings.AUTH_JWT_AUDIENCE,
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "jti": "bad-signature",
            },
            "different-secret-that-is-long-enough-456",
            algorithm="HS256",
        ),
        lambda: encoded_claims(iss="wrong-issuer"),
        lambda: encoded_claims(aud="wrong-audience"),
        lambda: encoded_claims(exp=datetime.now(timezone.utc) - timedelta(seconds=1)),
    ],
    ids=["invalid-signature", "wrong-issuer", "wrong-audience", "expired"],
)
def test_invalid_token_variants_are_rejected(actor_context, token):
    response = actor_context["client"].get("/actor", headers=bearer(token()))
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_missing_required_claim_is_rejected(actor_context):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "employee-1",
            "iss": settings.AUTH_JWT_ISSUER,
            "aud": settings.AUTH_JWT_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.AUTH_JWT_SECRET,
        algorithm="HS256",
    )
    response = actor_context["client"].get("/actor", headers=bearer(token))
    assert response.status_code == 401


def test_unknown_subject_is_rejected(actor_context):
    token = create_access_token(SimpleNamespace(id="missing-employee"))
    response = actor_context["client"].get("/actor", headers=bearer(token))
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("changes", "expected_status"),
    [
        ({"is_active": False}, 401),
        ({"employment_status": "inactive"}, 401),
        ({"employment_status": "terminated"}, 401),
        ({"account_locked": True}, 401),
        ({"locked_until": datetime.utcnow() + timedelta(minutes=5)}, 401),
    ],
    ids=["inactive", "inactive-employment", "terminated", "locked", "temporary-lock"],
)
def test_restricted_account_states_are_rejected(
    actor_context, changes, expected_status
):
    employee = actor_context["employee"]
    for field, value in changes.items():
        setattr(employee, field, value)
    actor_context["db"].commit()

    response = actor_context["client"].get(
        "/actor", headers=bearer(actor_context["token"])
    )
    assert response.status_code == expected_status


def test_forced_password_is_denied_normally_but_allowed_for_change_flow(actor_context):
    actor_context["employee"].force_password_change = True
    actor_context["db"].commit()

    normal = actor_context["client"].get(
        "/actor", headers=bearer(actor_context["token"])
    )
    password_change = actor_context["client"].get(
        "/password-change", headers=bearer(actor_context["token"])
    )

    assert normal.status_code == 403
    assert normal.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert password_change.status_code == 200
    assert password_change.json()["employee_id"] == "employee-1"


def test_shared_dependencies_resolve_employee_once(actor_context):
    employee_selects = []

    def count_employee_selects(_conn, _cursor, statement, *_args):
        normalized = " ".join(statement.lower().split())
        if " from employees " in f" {normalized} ":
            employee_selects.append(statement)

    event.listen(actor_context["engine"], "before_cursor_execute", count_employee_selects)
    try:
        response = actor_context["client"].get(
            "/combined", headers=bearer(actor_context["token"])
        )
    finally:
        event.remove(
            actor_context["engine"],
            "before_cursor_execute",
            count_employee_selects,
        )

    assert response.status_code == 200
    assert response.json() == {
        "actor_id": "employee-1",
        "principal_id": "employee-1",
        "employee_id": "employee-1",
    }
    assert len(employee_selects) == 1
