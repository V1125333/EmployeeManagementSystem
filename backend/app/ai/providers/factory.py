"""Construct a contextual provider from server-only configuration."""

from app.ai.providers.base import LLMProvider, ProviderBadRequestError
from app.ai.providers.disabled import DisabledLLMProvider
from app.ai.providers.openai_compatible import OpenAICompatibleLLMProvider
from app.ai.providers.openai_provider import OpenAILLMProvider
from app.core.config import settings


def build_llm_provider() -> LLMProvider:
    name = settings.CONTEXTUAL_LLM_PROVIDER.strip().lower()
    if name in {"", "disabled", "none"}:
        return DisabledLLMProvider()
    if name == "openai":
        return OpenAILLMProvider(
            model=settings.CONTEXTUAL_LLM_MODEL,
            api_key=settings.CONTEXTUAL_LLM_API_KEY,
            base_url=settings.CONTEXTUAL_LLM_BASE_URL,
            timeout_seconds=settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS,
        )
    if name == "openai_compatible":
        return OpenAICompatibleLLMProvider(
            model=settings.CONTEXTUAL_LLM_MODEL,
            api_key=settings.CONTEXTUAL_LLM_API_KEY,
            base_url=settings.CONTEXTUAL_LLM_BASE_URL,
            timeout_seconds=settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS,
        )
    raise ProviderBadRequestError(
        f"Unsupported contextual provider configuration: {name!r}."
    )
