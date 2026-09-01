"""Keep tests deterministic regardless of developer-local service settings."""

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_transactional_email_by_default(monkeypatch):
    monkeypatch.setattr(settings, "TRANSACTIONAL_EMAIL_ENABLED", False)


@pytest.fixture(autouse=True)
def disable_contextual_llm_by_default(monkeypatch):
    """Never let ordinary tests schedule a live contextual-provider request.

    Contextual-shadow tests explicitly opt back in and replace the provider
    with their deterministic fake.  Shadow mode itself remains enabled, as
    required by the Phase A configuration contract.
    """
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_ENABLED", False)
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_SHADOW_MODE", True)
