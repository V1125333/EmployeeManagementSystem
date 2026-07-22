"""Run with: python -m app.workers.email_worker [--once]."""

import argparse
import logging
import os
import socket
import time
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.transactional_email import EmailOutbox
from app.services.email_provider import EmailMessage, build_email_provider
from app.services.transactional_email_service import decrypt_context, render_email

logger = logging.getLogger(__name__)


def _claim_one(worker_id: str) -> str | None:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        stale_before = now - timedelta(seconds=settings.EMAIL_LOCK_TIMEOUT_SECONDS)
        query = db.query(EmailOutbox).filter(
            EmailOutbox.next_attempt_at <= now,
            ((EmailOutbox.status == "pending") | ((EmailOutbox.status == "processing") & (EmailOutbox.locked_at < stale_before))),
        ).order_by(EmailOutbox.created_at)
        if db.bind and db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        row = query.first()
        if not row:
            return None
        row.status = "processing"
        row.locked_at = now
        row.locked_by = worker_id
        row.attempt_count += 1
        db.commit()
        return row.id
    finally:
        db.close()


def _finish(row_id: str, *, provider_message_id: str | None = None, error: Exception | None = None) -> None:
    db = SessionLocal()
    try:
        row = db.query(EmailOutbox).filter(EmailOutbox.id == row_id).first()
        if not row:
            return
        row.locked_at = None
        row.locked_by = None
        if error is None:
            row.status = "sent"
            row.sent_at = datetime.utcnow()
            row.provider_message_id = provider_message_id
            row.last_error = None
        else:
            row.last_error = f"{type(error).__name__}: {error}"[:2000]
            if row.attempt_count >= row.max_attempts:
                row.status = "failed"
            else:
                row.status = "pending"
                delay = min(settings.EMAIL_MAX_RETRY_SECONDS, settings.EMAIL_BASE_RETRY_SECONDS * (2 ** (row.attempt_count - 1)))
                row.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay)
        db.commit()
    finally:
        db.close()


def process_one(provider, worker_id: str) -> bool:
    row_id = _claim_one(worker_id)
    if not row_id:
        return False
    try:
        db = SessionLocal()
        try:
            row = db.query(EmailOutbox).filter(EmailOutbox.id == row_id).first()
            context = decrypt_context(row.encrypted_payload)
            rendered = render_email(row.template_name, row.template_version, context)
            message = EmailMessage(row.recipient_email, rendered.subject, rendered.html_body, rendered.text_body)
        finally:
            db.close()
        provider_id = provider.send(message)
        _finish(row_id, provider_message_id=provider_id)
    except Exception as exc:
        logger.exception("Transactional email %s failed", row_id)
        _finish(row_id, error=exc)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Drain currently-due messages and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    provider = build_email_provider()
    while True:
        worked = process_one(provider, worker_id)
        if args.once and not worked:
            return
        if not worked:
            time.sleep(settings.EMAIL_WORKER_POLL_SECONDS)


if __name__ == "__main__":
    main()
