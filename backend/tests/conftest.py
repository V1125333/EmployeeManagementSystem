"""Keep tests deterministic regardless of a developer's local email settings."""

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_transactional_email_by_default(monkeypatch):
    monkeypatch.setattr(settings, "TRANSACTIONAL_EMAIL_ENABLED", False)
