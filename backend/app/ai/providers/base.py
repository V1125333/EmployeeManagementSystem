"""Provider-neutral interface and bounded execution policy."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Protocol

from pydantic import ValidationError

from app.ai.contextual_schemas import (
    ContextualInterpretation,
    LLMProviderRequest,
    LLMProviderResponse,
)


_SAFE_IDENTIFIER = re.compile(r"[^a-zA-Z0-9._:-]+")


def safe_provider_identifier(value: object, *, max_length: int) -> str | None:
    """Bound provider identifiers without retaining response or request data."""
    if value is None:
        return None
    normalized = _SAFE_IDENTIFIER.sub("_", str(value).strip())
    return normalized[:max_length] or None


class LLMProviderError(Exception):
    category = "provider_unknown"
    default_retryable = False

    def __init__(
        self,
        safe_message: str,
        *,
        code: object = None,
        http_status: int | None = None,
        request_id: object = None,
        retryable: bool | None = None,
    ):
        message = " ".join(str(safe_message).split())[:240]
        super().__init__(message)
        self.safe_message = message
        self.code = safe_provider_identifier(code, max_length=80)
        self.http_status = http_status
        self.request_id = safe_provider_identifier(request_id, max_length=120)
        self.retryable = (
            self.default_retryable if retryable is None else bool(retryable)
        )


class ProviderDisabledError(LLMProviderError):
    category = "provider_disabled"


class ProviderAuthenticationError(LLMProviderError):
    category = "provider_authentication"


class ProviderPermissionError(LLMProviderError):
    category = "provider_permission"


class ProviderTimeoutError(LLMProviderError):
    category = "provider_timeout"
    default_retryable = True


class ProviderConnectionError(LLMProviderError):
    category = "provider_connection"
    default_retryable = True


class ProviderDNSError(LLMProviderError):
    category = "provider_dns"
    default_retryable = True


class ProviderTLSError(LLMProviderError):
    category = "provider_tls"
    default_retryable = True


class ProviderTransportError(ProviderConnectionError):
    """Compatibility alias for non-OpenAI adapters."""


class ProviderRateLimitError(LLMProviderError):
    category = "provider_rate_limit"
    default_retryable = True


class ProviderQuotaError(LLMProviderError):
    category = "provider_quota"


class ProviderModelNotFoundError(LLMProviderError):
    category = "provider_model_not_found"


class ProviderBadRequestError(LLMProviderError):
    category = "provider_bad_request"


class ProviderStructuredOutputError(LLMProviderError):
    category = "provider_structured_output"


class ProviderServerError(LLMProviderError):
    category = "provider_server_error"
    default_retryable = True


class ProviderUnknownError(LLMProviderError):
    category = "provider_unknown"


class ProviderInputBudgetError(LLMProviderError):
    category = "input_budget_exceeded"


class ProviderInvalidOutputError(LLMProviderError):
    category = "provider_invalid_response"


class LLMProvider(Protocol):
    name: str
    model: str

    async def interpret(
        self, request: LLMProviderRequest
    ) -> LLMProviderResponse: ...


def parse_structured_interpretation(
    raw: str | dict,
) -> ContextualInterpretation:
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
        return ContextualInterpretation.model_validate(value)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ProviderInvalidOutputError(
            "The provider returned invalid structured output."
        ) from exc


async def interpret_with_policy(
    provider: LLMProvider,
    request: LLMProviderRequest,
    *,
    timeout_seconds: float,
    retry_count: int,
) -> LLMProviderResponse:
    attempts = max(1, min(retry_count + 1, 2))
    for attempt in range(attempts):
        try:
            return await asyncio.wait_for(
                provider.interpret(request),
                timeout=max(0.25, min(timeout_seconds, 15)),
            )
        except asyncio.TimeoutError as exc:
            error: LLMProviderError = ProviderTimeoutError(
                "The contextual provider timed out."
            )
            error.__cause__ = exc
        except ProviderInvalidOutputError:
            raise
        except ProviderAuthenticationError:
            raise
        except ProviderDisabledError:
            raise
        except LLMProviderError as exc:
            error = exc
        except Exception as exc:
            error = ProviderUnknownError(
                "The contextual provider failed unexpectedly."
            )
            error.__cause__ = exc
        if attempt + 1 >= attempts or not error.retryable:
            raise error
        await asyncio.sleep(min(0.25 * (2**attempt), 0.5))
    raise ProviderUnknownError("The contextual provider failed unexpectedly.")
