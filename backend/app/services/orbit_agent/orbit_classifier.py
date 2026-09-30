from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import settings
from app.services.orbit_agent.orbit_capabilities import OrbitIntent

logger = logging.getLogger(__name__)

_CLASSIFIER_ALLOWED_INTENTS = frozenset(
    {
        OrbitIntent.EMS_LEAVE,
        OrbitIntent.EMS_ATTENDANCE,
        OrbitIntent.EMS_TIMESHEET,
        OrbitIntent.EMS_ALLOCATION,
        OrbitIntent.EMS_EMPLOYEE,
        OrbitIntent.DRAFTING,
        OrbitIntent.GENERAL_REASONING,
        OrbitIntent.CONTEXT_FOLLOWUP,
        OrbitIntent.UNKNOWN,
    }
)
_CLASSIFIER_INTENT_VALUES = tuple(intent.value for intent in _CLASSIFIER_ALLOWED_INTENTS)
_CLASSIFIER_SYSTEM_PROMPT = """You are an intent classifier for Orbit AI inside the ReKnew Employee Management System.

Classify the user's message into exactly one allowed intent.

Allowed intents:
- ems_leave
- ems_attendance
- ems_timesheet
- ems_allocation
- ems_employee
- drafting
- general_reasoning
- context_followup
- unknown

Do not answer the user's request.
Do not explain the task.
Return structured JSON only.

Examples:
"my leave?" -> ems_leave
"attendance?" -> ems_attendance
"timesheet?" -> ems_timesheet
"who is on bench?" -> ems_allocation
"find Ravi" -> ems_employee
"help me write an email" -> drafting
"explain transformers" -> general_reasoning
"why?" -> context_followup
"""


@dataclass(frozen=True)
class OrbitClassificationResult:
    intent: OrbitIntent
    confidence: float
    reason: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("classification confidence must be between 0.0 and 1.0")


class _ClassifierPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    confidence: float


@dataclass(frozen=True)
class OrbitContextMessage:
    role: str
    content: str


def _unknown_result(reason: str) -> OrbitClassificationResult:
    return OrbitClassificationResult(
        intent=OrbitIntent.UNKNOWN,
        confidence=0.0,
        reason=reason,
    )


def _classifier_provider_name() -> str:
    provider = getattr(settings, "ORBIT_CLASSIFIER_PROVIDER", "").strip().lower()
    if provider:
        return provider
    return settings.CONTEXTUAL_LLM_PROVIDER.strip().lower()


def _classifier_model() -> str:
    return (
        getattr(settings, "ORBIT_CLASSIFIER_MODEL", "").strip()
        or settings.CONTEXTUAL_LLM_MODEL.strip()
    )


def _classifier_api_key() -> str:
    return (
        getattr(settings, "ORBIT_CLASSIFIER_API_KEY", "").strip()
        or settings.CONTEXTUAL_LLM_API_KEY.strip()
    )


def _classifier_base_url() -> str:
    return (
        getattr(settings, "ORBIT_CLASSIFIER_BASE_URL", "").strip().rstrip("/")
        or settings.CONTEXTUAL_LLM_BASE_URL.strip().rstrip("/")
    )


def _classifier_timeout_seconds() -> float:
    configured = float(
        getattr(
            settings,
            "ORBIT_CLASSIFIER_TIMEOUT_SECONDS",
            settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS,
        )
    )
    return max(0.25, min(configured, 15.0))


def orbit_classifier_confidence_threshold() -> float:
    configured = float(getattr(settings, "ORBIT_CLASSIFIER_CONFIDENCE_THRESHOLD", 0.9))
    return max(0.0, min(configured, 1.0))


def _classifier_retry_count() -> int:
    configured = int(
        getattr(
            settings,
            "ORBIT_CLASSIFIER_RETRY_COUNT",
            settings.CONTEXTUAL_LLM_RETRY_COUNT,
        )
    )
    return max(0, min(configured, 1))


def _classifier_max_output_tokens() -> int:
    configured = int(getattr(settings, "ORBIT_CLASSIFIER_MAX_OUTPUT_TOKENS", 80))
    return max(32, min(configured, 256))


def _provider_is_configured() -> bool:
    provider = _classifier_provider_name()
    return (
        provider in {"openai", "openai_compatible"}
        and bool(_classifier_model())
        and bool(_classifier_api_key())
        and bool(_classifier_base_url())
    )


def _parse_classifier_content(raw_content: str | dict) -> OrbitClassificationResult:
    try:
        payload = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
        parsed = _ClassifierPayload.model_validate(payload)
        intent = OrbitIntent(parsed.intent)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return _unknown_result("classifier_invalid_response")

    if intent not in _CLASSIFIER_ALLOWED_INTENTS:
        return _unknown_result("classifier_invalid_response")
    if not 0.0 <= float(parsed.confidence) <= 1.0:
        return _unknown_result("classifier_invalid_response")
    return OrbitClassificationResult(
        intent=intent,
        confidence=float(parsed.confidence),
        reason="classified",
    )


def _format_recent_context(recent_context: list[OrbitContextMessage] | None) -> str:
    if not recent_context:
        return ""
    rendered = "\n".join(
        f"{item.role.title()}: {item.content}"
        for item in recent_context
        if item.role in {"user", "assistant"} and item.content.strip()
    ).strip()
    return rendered[:4000]


async def _request_classifier_completion(
    message: str,
    recent_context: list[OrbitContextMessage] | None = None,
) -> str:
    recent_context_text = _format_recent_context(recent_context)
    user_content = (
        f"Recent conversation:\n{recent_context_text}\n\nCurrent message:\n{message}"
        if recent_context_text
        else message
    )
    payload = {
        "model": _classifier_model(),
        "messages": [
            {"role": "system", "content": _CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "orbit_intent_classification",
                "strict": True,
                "schema": _ClassifierPayload.model_json_schema(),
            },
        },
        "max_completion_tokens": _classifier_max_output_tokens(),
    }
    async with httpx.AsyncClient(timeout=_classifier_timeout_seconds()) as client:
        response = await client.post(
            f"{_classifier_base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {_classifier_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code in {401, 403}:
        raise PermissionError("classifier_authentication_error")
    if response.status_code >= 400:
        raise RuntimeError(f"classifier_http_{response.status_code}")
    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("classifier_invalid_response") from exc
    if not isinstance(content, str) or not content.strip():
        raise ValueError("classifier_invalid_response")
    return content


async def classify_orbit_message(
    message: str,
    *,
    recent_context: list[OrbitContextMessage] | None = None,
) -> OrbitClassificationResult:
    if not _provider_is_configured():
        return _unknown_result("classifier_unavailable")

    attempts = _classifier_retry_count() + 1
    last_reason = "classifier_unavailable"
    for attempt in range(attempts):
        try:
            content = await asyncio.wait_for(
                _request_classifier_completion(message, recent_context),
                timeout=_classifier_timeout_seconds(),
            )
            return _parse_classifier_content(content)
        except asyncio.TimeoutError:
            last_reason = "classifier_timeout"
        except httpx.TimeoutException:
            last_reason = "classifier_timeout"
        except httpx.HTTPError:
            last_reason = "classifier_transport_error"
        except PermissionError as exc:
            last_reason = str(exc) or "classifier_authentication_error"
        except RuntimeError as exc:
            last_reason = str(exc) or "classifier_transport_error"
        except ValueError as exc:
            last_reason = str(exc) or "classifier_invalid_response"
        except Exception:
            last_reason = "classifier_unexpected_error"

        if attempt + 1 >= attempts:
            break
        await asyncio.sleep(0.1)

    logger.warning("Orbit classifier fallback reason=%s", last_reason)
    return _unknown_result(last_reason)
