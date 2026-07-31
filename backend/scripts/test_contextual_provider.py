"""Make one synthetic, non-business Phase A provider health request."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.contextual_schemas import (  # noqa: E402
    ActiveWorkflowContext,
    CapabilityDescription,
    ContextPackage,
    ContextualInterpretation,
    LLMProviderRequest,
)
from app.ai.prompt_templates import build_contextual_system_prompt  # noqa: E402
from app.ai.providers import (  # noqa: E402
    LLMProviderError,
    build_llm_provider,
    interpret_with_policy,
)
from app.core.config import (  # noqa: E402
    contextual_provider_configuration_errors,
    settings,
)


def _synthetic_request() -> LLMProviderRequest:
    context = ContextPackage(
        prompt_version=settings.CONTEXTUAL_LLM_PROMPT_VERSION,
        active_workflow=ActiveWorkflowContext(
            workflow_type="none",
            stage="none",
        ),
        recent_messages=[],
        trusted_date=date(2026, 1, 15),
        timezone="UTC",
        approved_capabilities=[
            CapabilityDescription(
                capability_id="leave.balance.read_self",
                description="Read the authenticated user's leave balance.",
                risk="read",
            )
        ],
    )
    return LLMProviderRequest(
        system_prompt=build_contextual_system_prompt(),
        current_message="Check my leave balance.",
        context=context,
        max_input_tokens=settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS,
        max_output_tokens=settings.CONTEXTUAL_LLM_MAX_OUTPUT_TOKENS,
        temperature=settings.CONTEXTUAL_LLM_TEMPERATURE,
    )


async def _run_once() -> tuple[dict, int]:
    errors = contextual_provider_configuration_errors()
    if errors:
        return (
            {
                "success": False,
                "safe_error_category": "provider_configuration",
                "configuration_errors": errors,
                "model": settings.CONTEXTUAL_LLM_MODEL or "not_configured",
                "latency_ms": 0,
                "schema_valid": False,
                "request_id": None,
                "can_affect_production": False,
            },
            2,
        )

    provider = build_llm_provider()
    started = time.perf_counter()
    try:
        response = await interpret_with_policy(
            provider,
            _synthetic_request(),
            timeout_seconds=settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS,
            # This health command is intentionally exactly one provider call.
            retry_count=0,
        )
        return (
            {
                "success": True,
                "safe_error_category": None,
                "model": response.model,
                "latency_ms": response.latency_ms,
                "schema_valid": isinstance(
                    response.interpretation, ContextualInterpretation
                ),
                "request_id": response.request_id,
                "can_affect_production": False,
            },
            0,
        )
    except LLMProviderError as exc:
        return (
            {
                "success": False,
                "safe_error_category": exc.category,
                "safe_error_message": exc.safe_message,
                "error_code": exc.code,
                "http_status": exc.http_status,
                "retryable": exc.retryable,
                "model": getattr(
                    provider, "model", settings.CONTEXTUAL_LLM_MODEL
                ),
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "schema_valid": False,
                "request_id": exc.request_id,
                "can_affect_production": False,
            },
            1,
        )


def main() -> int:
    result, exit_code = asyncio.run(_run_once())
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
