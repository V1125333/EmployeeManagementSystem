"""Official OpenAI Python SDK adapter for Phase A structured shadow output."""

from __future__ import annotations

import socket
import ssl
import time

import openai
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.ai.contextual_schemas import (
    ContextualInterpretation,
    LLMProviderRequest,
    LLMProviderResponse,
    TokenUsage,
)
from app.ai.providers.base import (
    ProviderAuthenticationError,
    ProviderBadRequestError,
    ProviderConnectionError,
    ProviderDNSError,
    ProviderInvalidOutputError,
    ProviderModelNotFoundError,
    ProviderPermissionError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderStructuredOutputError,
    ProviderTLSError,
    ProviderTimeoutError,
    ProviderUnknownError,
    safe_provider_identifier,
)


def _error_body(exc: openai.APIStatusError) -> dict:
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return {}
    nested = body.get("error")
    return nested if isinstance(nested, dict) else body


def _status_metadata(exc: openai.APIStatusError) -> dict:
    body = _error_body(exc)
    error_type = body.get("type")
    code = body.get("code") or getattr(exc, "code", None) or error_type
    return {
        "code": code,
        "http_status": getattr(exc, "status_code", None),
        "request_id": getattr(exc, "request_id", None),
    }


def _safe_parameter(exc: openai.APIStatusError) -> str | None:
    body = _error_body(exc)
    return safe_provider_identifier(
        body.get("param") or getattr(exc, "param", None),
        max_length=80,
    )


def _status_error(exc: openai.APIStatusError):
    metadata = _status_metadata(exc)
    body = _error_body(exc)
    status = metadata["http_status"]
    code = str(metadata["code"] or "").lower()
    param = (_safe_parameter(exc) or "").lower()
    message = str(body.get("message") or "").lower()

    if status == 401:
        return ProviderAuthenticationError(
            "The contextual provider rejected its credential.",
            **metadata,
        )
    if status == 403:
        return ProviderPermissionError(
            "The contextual provider denied access to this model or project.",
            **metadata,
        )
    if status == 404:
        return ProviderModelNotFoundError(
            "The configured contextual model was not found or is unavailable.",
            **metadata,
        )
    if status == 429:
        if "quota" in code or "quota" in message or "billing" in message:
            return ProviderQuotaError(
                "The contextual provider quota or billing allowance is unavailable.",
                **metadata,
            )
        return ProviderRateLimitError(
            "The contextual provider rate limit was reached.",
            **metadata,
        )
    if status is not None and status >= 500:
        return ProviderServerError(
            "The contextual provider returned a server error.",
            **metadata,
        )
    if (
        "schema" in code
        or "schema" in param
        or "structured" in code
        or "structured" in message
        or "response_format" in param
        or "text.format" in param
    ):
        return ProviderStructuredOutputError(
            "The contextual provider rejected the structured-output schema.",
            **metadata,
        )
    parameter_message = (
        f"The contextual provider rejected parameter '{param}'."
        if param
        else "The contextual provider rejected the request."
    )
    return ProviderBadRequestError(parameter_message, **metadata)


def _connection_error(exc: openai.APIConnectionError):
    current: BaseException | None = exc
    chain: list[BaseException] = []
    while current is not None and len(chain) < 8:
        chain.append(current)
        current = current.__cause__ or current.__context__
    combined = " ".join(str(item).lower() for item in chain)
    if any(isinstance(item, socket.gaierror) for item in chain) or any(
        marker in combined
        for marker in ("name resolution", "nodename nor servname", "getaddrinfo")
    ):
        return ProviderDNSError(
            "The contextual provider hostname could not be resolved."
        )
    if any(isinstance(item, ssl.SSLError) for item in chain) or any(
        marker in combined
        for marker in ("certificate verify", "ssl:", "tls")
    ):
        return ProviderTLSError(
            "The contextual provider TLS connection could not be verified."
        )
    return ProviderConnectionError(
        "The contextual provider connection could not be established."
    )


class OpenAILLMProvider:
    """Structured-output provider with no tools and no provider-side storage."""

    name = "openai"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ):
        if not model.strip():
            raise ProviderBadRequestError("A contextual model is required.")
        if not api_key.strip():
            raise ProviderAuthenticationError(
                "A contextual provider credential is required."
            )
        self.model = model.strip()
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def interpret(
        self, request: LLMProviderRequest
    ) -> LLMProviderResponse:
        started = time.perf_counter()
        try:
            async with AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
                max_retries=0,
            ) as client:
                # Some current Responses API models reject `temperature`
                # entirely, including a value of zero. Phase A does not need a
                # sampling override, so the official adapter deliberately
                # leaves this optional control unset.
                response = await client.responses.parse(
                    model=self.model,
                    instructions=request.system_prompt,
                    input=request.current_message
                    + "\n\nSERVER_CONTEXT_JSON="
                    + request.context.model_dump_json(
                        exclude_none=True,
                        exclude_defaults=True,
                    ),
                    text_format=ContextualInterpretation,
                    max_output_tokens=request.max_output_tokens,
                    store=False,
                )
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(
                "The contextual provider timed out."
            ) from exc
        except openai.APIConnectionError as exc:
            raise _connection_error(exc) from exc
        except openai.APIStatusError as exc:
            raise _status_error(exc) from exc
        except (openai.APIResponseValidationError, ValidationError) as exc:
            raise ProviderInvalidOutputError(
                "The contextual provider returned an invalid response shape."
            ) from exc
        except ProviderInvalidOutputError:
            raise
        except Exception as exc:
            raise ProviderUnknownError(
                "The contextual provider failed unexpectedly."
            ) from exc

        request_id = safe_provider_identifier(
            getattr(response, "_request_id", None)
            or getattr(response, "request_id", None),
            max_length=120,
        )
        interpretation = response.output_parsed
        if not isinstance(interpretation, ContextualInterpretation):
            raise ProviderInvalidOutputError(
                "The contextual provider returned no valid structured output.",
                request_id=request_id,
            )
        usage = response.usage
        return LLMProviderResponse(
            interpretation=interpretation,
            provider=self.name,
            model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            token_usage=TokenUsage(
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
            ),
            request_id=request_id,
        )
