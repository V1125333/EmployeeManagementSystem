"""Template rendering and transaction-safe outbox enqueueing."""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.transactional_email import AccountActivationToken, EmailOutbox

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates" / "email"
jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATE_ROOT)),
    autoescape=select_autoescape(("html", "xml")),
    undefined=StrictUndefined,
)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html_body: str
    text_body: str


SUBJECTS = {
    "manager_approval": "Approval needed: {{ request_type }} from {{ employee_name }}",
    "account_activation": "Activate your Orbit account",
    "password_reset": "Reset your Orbit password",
    "password_changed": "Your Orbit password was changed",
}


def _fernet() -> Fernet:
    if not settings.EMAIL_PAYLOAD_ENCRYPTION_KEY:
        raise RuntimeError("EMAIL_PAYLOAD_ENCRYPTION_KEY is required when transactional email is enabled")
    return Fernet(settings.EMAIL_PAYLOAD_ENCRYPTION_KEY.encode())


def encrypt_context(context: dict) -> str:
    return _fernet().encrypt(json.dumps(context, default=str).encode()).decode()


def decrypt_context(payload: str) -> dict:
    try:
        return json.loads(_fernet().decrypt(payload.encode()).decode())
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt email outbox payload") from exc


def render_email(template_name: str, version: str, context: dict) -> RenderedEmail:
    subject = jinja.from_string(SUBJECTS[template_name]).render(**context)
    html_body = jinja.get_template(f"{version}/{template_name}.html.j2").render(**context)
    text_body = jinja.get_template(f"{version}/{template_name}.txt.j2").render(**context)
    return RenderedEmail(subject=subject, html_body=html_body, text_body=text_body)


def enqueue_email(
    db: Session, *, recipient: str, template_name: str, context: dict,
    idempotency_key: str, version: str = "v1",
) -> EmailOutbox | None:
    if not settings.TRANSACTIONAL_EMAIL_ENABLED:
        return None
    existing = db.query(EmailOutbox).filter(EmailOutbox.idempotency_key == idempotency_key).first()
    if existing:
        return existing
    row = EmailOutbox(
        recipient_email=recipient.strip().lower(), template_name=template_name,
        template_version=version, encrypted_payload=encrypt_context(context),
        idempotency_key=idempotency_key, max_attempts=settings.EMAIL_MAX_ATTEMPTS,
    )
    db.add(row)
    return row


def issue_activation(db: Session, employee) -> str:
    now = datetime.utcnow()
    db.query(AccountActivationToken).filter(
        AccountActivationToken.employee_id == employee.id,
        AccountActivationToken.used_at.is_(None),
        AccountActivationToken.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session=False)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = now + timedelta(minutes=settings.ACTIVATION_TOKEN_EXPIRY_MINUTES)
    db.add(AccountActivationToken(employee_id=employee.id, token_hash=token_hash, expires_at=expires_at))
    query = urlencode({"email": employee.work_email, "activation_token": token})
    enqueue_email(
        db, recipient=employee.work_email, template_name="account_activation",
        idempotency_key=f"account-activation:{employee.id}:{token_hash}",
        context={
            "first_name": employee.first_name,
            "activation_url": f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login?{query}",
            "expires_minutes": settings.ACTIVATION_TOKEN_EXPIRY_MINUTES,
        },
    )
    return token


def verify_activation_token(db: Session, employee_id: str, token: str) -> AccountActivationToken | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return db.query(AccountActivationToken).filter(
        AccountActivationToken.employee_id == employee_id,
        AccountActivationToken.token_hash == token_hash,
        AccountActivationToken.used_at.is_(None),
        AccountActivationToken.revoked_at.is_(None),
        AccountActivationToken.expires_at > datetime.utcnow(),
    ).first()
