"""Isolated adapter for providers implementing OpenAI-compatible chat JSON."""

from __future__ import annotations

import json
import time

import httpx

from app.ai.contextual_schemas import (
    ContextualInterpretation,
    LLMProviderRequest,
    LLMProviderResponse,
    TokenUsage,
)
from app.ai.providers.base import (
    ProviderAuthenticationError,
    ProviderInvalidOutputError,
    ProviderTimeoutError,
    ProviderTransportError,
    parse_structured_interpretation,
)


class OpenAICompatibleLLMProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ):
        if not model.strip():
            raise ProviderTransportError("A contextual model is required.")
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
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "ACTIVE_WORKFLOW": request.context.active_workflow.model_dump(
                                mode="json"
                            ),
                            "RECENT_MESSAGES": [
                                item.model_dump(mode="json")
                                for item in request.context.recent_messages
                            ],
                            "TRUSTED_DATE": request.context.trusted_date.isoformat(),
                            "TIMEZONE": request.context.timezone,
                            "APPROVED_CAPABILITIES": [
                                item.model_dump(mode="json")
                                for item in request.context.approved_capabilities
                            ],
                            "CURRENT_UNTRUSTED_MESSAGE": request.current_message,
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "orbit_contextual_interpretation",
                    "strict": True,
                    "schema": ContextualInterpretation.model_json_schema(),
                },
            },
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "The contextual provider timed out."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderTransportError(
                "The contextual provider transport failed."
            ) from exc
        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError(
                "The contextual provider rejected its credential."
            )
        if response.status_code >= 400:
            raise ProviderTransportError(
                f"The contextual provider returned HTTP {response.status_code}."
            )
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            interpretation = parse_structured_interpretation(content)
            usage = body.get("usage") or {}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderInvalidOutputError(
                "The contextual provider response shape was invalid."
            ) from exc
        return LLMProviderResponse(
            interpretation=interpretation,
            provider=self.name,
            model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            token_usage=TokenUsage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            ),
        )
