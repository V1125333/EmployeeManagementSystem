"""Explicit no-provider adapter used by the safe default configuration."""

from app.ai.contextual_schemas import LLMProviderRequest, LLMProviderResponse
from app.ai.providers.base import ProviderDisabledError


class DisabledLLMProvider:
    name = "disabled"
    model = "disabled"

    async def interpret(
        self, _request: LLMProviderRequest
    ) -> LLMProviderResponse:
        raise ProviderDisabledError("No contextual LLM provider is configured.")
