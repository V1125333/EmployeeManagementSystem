from types import SimpleNamespace
from datetime import date

from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.transactional_email import AccountActivationToken, EmailOutbox, SecurityRateLimit
from app.models.employee import Employee
from app.models.organization import Department, Designation
from app.schemas.employee import AddEmployeeRequest
from app.services.auth_service import find_employee_by_email
from app.services.employee_service import create_employee
from app.services.rate_limit_service import consume_rate_limit
from app.services.transactional_email_service import (
    decrypt_context,
    enqueue_email,
    issue_activation,
    render_email,
    verify_activation_token,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Department.__table__.create(engine)
    Designation.__table__.create(engine)
    Employee.__table__.create(engine)
    EmailOutbox.__table__.create(engine)
    AccountActivationToken.__table__.create(engine)
    SecurityRateLimit.__table__.create(engine)
    return sessionmaker(bind=engine)()


def test_outbox_encrypts_payload_and_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "TRANSACTIONAL_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PAYLOAD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    db = _session()
    first = enqueue_email(
        db, recipient="USER@example.com", template_name="password_changed",
        context={"first_name": "Ada", "changed_at": "now"}, idempotency_key="changed:1",
    )
    second = enqueue_email(
        db, recipient="user@example.com", template_name="password_changed",
        context={"first_name": "Ada", "changed_at": "later"}, idempotency_key="changed:1",
    )
    db.commit()
    assert first.id == second.id
    assert db.query(EmailOutbox).count() == 1
    assert "Ada" not in first.encrypted_payload
    assert decrypt_context(first.encrypted_payload)["first_name"] == "Ada"


def test_activation_token_is_random_hashed_expiring_and_renderable(monkeypatch):
    monkeypatch.setattr(settings, "TRANSACTIONAL_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PAYLOAD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    db = _session()
    employee = SimpleNamespace(id="employee-1", work_email="ada@example.com", first_name="Ada")
    token = issue_activation(db, employee)
    db.commit()
    stored = db.query(AccountActivationToken).one()
    assert token not in stored.token_hash
    assert verify_activation_token(db, employee.id, token) is not None
    context = decrypt_context(db.query(EmailOutbox).one().encrypted_payload)
    assert token in context["activation_url"]
    rendered = render_email("account_activation", "v1", context)
    assert "Activate your Orbit account" == rendered.subject
    assert "Ada" in rendered.html_body


def test_database_rate_limit_blocks_after_limit():
    db = _session()
    assert consume_rate_limit(db, scope="reset", key="ip:user@example.com", limit=2)
    assert consume_rate_limit(db, scope="reset", key="ip:user@example.com", limit=2)
    assert not consume_rate_limit(db, scope="reset", key="ip:user@example.com", limit=2)


def test_auth_lookup_is_case_insensitive_and_creation_normalizes_email(monkeypatch):
    monkeypatch.setattr(settings, "TRANSACTIONAL_EMAIL_ENABLED", False)
    db = _session()
    result = create_employee(db, AddEmployeeRequest(
        first_name="Vasu",
        last_name="Pendurthi",
        work_email="VPendurthi@Reknew.ai",
        phone="1000000000",
        date_of_birth=date(1990, 1, 1),
        workforce_type="full_time",
        role="employee",
        department="Engineering",
        designation="Engineer",
        reporting_manager="Manager",
        joining_date=date(2026, 1, 1),
        work_location="US",
    ))
    assert result.success
    stored = db.query(Employee).one()
    assert stored.work_email == "vpendurthi@reknew.ai"
    assert find_employee_by_email(db, "VPENDURTHI@REKNEW.AI").id == stored.id
