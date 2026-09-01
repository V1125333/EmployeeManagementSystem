from __future__ import annotations

import asyncio

import pytest

from app.services.orbit_agent import orbit_classifier
from app.services.orbit_agent.orbit_capabilities import OrbitIntent


def test_parse_classifier_content_accepts_supported_intent_and_confidence():
    result = orbit_classifier._parse_classifier_content(
        {"intent": "ems_leave", "confidence": 0.97}
    )

    assert result.intent is OrbitIntent.EMS_LEAVE
    assert result.confidence == 0.97
    assert result.reason == "classified"


@pytest.mark.parametrize(
    "payload",
    (
        {"intent": "unsupported_intent", "confidence": 0.97},
        {"intent": "ems_leave"},
        {"intent": "ems_leave", "confidence": 1.5},
        {"intent": "ems_leave", "confidence": -0.1},
        "not-json",
    ),
)
def test_parse_classifier_content_rejects_invalid_output(payload):
    result = orbit_classifier._parse_classifier_content(payload)

    assert result.intent is OrbitIntent.UNKNOWN
    assert result.confidence == 0.0
    assert result.reason == "classifier_invalid_response"


def test_classify_orbit_message_returns_unknown_when_provider_unconfigured(monkeypatch):
    monkeypatch.setattr(orbit_classifier.settings, "ORBIT_CLASSIFIER_PROVIDER", "disabled")
    monkeypatch.setattr(orbit_classifier.settings, "CONTEXTUAL_LLM_PROVIDER", "disabled")

    result = asyncio.run(orbit_classifier.classify_orbit_message("my leave?"))

    assert result.intent is OrbitIntent.UNKNOWN
    assert result.confidence == 0.0
    assert result.reason == "classifier_unavailable"


def test_classify_orbit_message_returns_unknown_on_timeout(monkeypatch):
    monkeypatch.setattr(orbit_classifier.settings, "ORBIT_CLASSIFIER_PROVIDER", "openai")
    monkeypatch.setattr(orbit_classifier.settings, "ORBIT_CLASSIFIER_MODEL", "gpt-test")
    monkeypatch.setattr(orbit_classifier.settings, "ORBIT_CLASSIFIER_API_KEY", "key")
    monkeypatch.setattr(orbit_classifier.settings, "ORBIT_CLASSIFIER_BASE_URL", "https://example.com/v1")

    async def fake_request(_message: str, _recent_context=None) -> str:
        raise asyncio.TimeoutError("slow")

    monkeypatch.setattr(orbit_classifier, "_request_classifier_completion", fake_request)

    result = asyncio.run(orbit_classifier.classify_orbit_message("my leave?"))

    assert result.intent is OrbitIntent.UNKNOWN
    assert result.confidence == 0.0
    assert result.reason == "classifier_timeout"
