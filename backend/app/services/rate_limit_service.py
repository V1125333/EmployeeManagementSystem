"""Database-backed fixed-window security rate limiting."""

import hashlib
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.transactional_email import SecurityRateLimit


def consume_rate_limit(db: Session, *, scope: str, key: str, limit: int, window_seconds: int = 3600) -> bool:
    key_hash = hashlib.sha256(key.strip().lower().encode()).hexdigest()
    now = datetime.utcnow()
    row = db.query(SecurityRateLimit).filter(
        SecurityRateLimit.scope == scope, SecurityRateLimit.key_hash == key_hash
    ).with_for_update().first()
    if not row:
        db.add(SecurityRateLimit(scope=scope, key_hash=key_hash, window_started_at=now, count=1))
        db.commit()
        return True
    if row.window_started_at + timedelta(seconds=window_seconds) <= now:
        row.window_started_at, row.count = now, 1
        db.commit()
        return True
    if row.count >= limit:
        db.rollback()
        return False
    row.count += 1
    db.commit()
    return True
