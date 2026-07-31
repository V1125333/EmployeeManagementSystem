"""Phase A shadow runner: observe, validate, compare, and store safe metadata."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.context_builder import build_context_package, redact_context_text
from app.ai.contextual_schemas import (
    ContextualProviderStatusResponse,
    DeterministicObservation,
    LLMProviderRequest,
    ShadowDiagnosticItem,
    ShadowDiagnosticsResponse,
)
from app.ai.prompt_templates import (
    build_contextual_system_prompt,
    estimated_tokens,
    prompt_example_count,
)
from app.ai.providers import (
    LLMProvider,
    LLMProviderError,
    ProviderInputBudgetError,
    build_llm_provider,
    interpret_with_policy,
)
from app.ai.shadow_evaluator import (
    build_deterministic_observation,
    compare_interpretations,
)
from app.core.authentication import AuthenticatedPrincipal
from app.core.config import (
    contextual_provider_configuration_errors,
    settings,
)
from app.core.database import SessionLocal
from app.models.ai_workflow import AIContextualShadowEvaluation
from app.schemas.ai import AIChatResponse

logger = logging.getLogger(__name__)


def shadow_enabled() -> bool:
    return bool(
        settings.CONTEXTUAL_LLM_ENABLED
        and settings.CONTEXTUAL_LLM_SHADOW_MODE
    )


def _json_list(value: str) -> list[str]:
    try:
        loaded = json.loads(value or "[]")
        return [str(item) for item in loaded] if isinstance(loaded, list) else []
    except (TypeError, ValueError):
        return []


def _store(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
    correlation_id: str,
    active_workflow_type: str,
    deterministic: DeterministicObservation,
    provider: str,
    model: str,
    latency_ms: int,
    comparison_outcome: str,
    segment: str,
    schema_validation_status: str,
    interpretation=None,
    extracted_field_categories: list[str] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_category: str | None = None,
    error_message: str | None = None,
    error_code: str | None = None,
    error_http_status: int | None = None,
    provider_request_id: str | None = None,
    error_retryable: bool | None = None,
) -> AIContextualShadowEvaluation:
    row = AIContextualShadowEvaluation(
        actor_employee_id=principal.employee_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        active_workflow_type=active_workflow_type,
        deterministic_goal=deterministic.goal,
        deterministic_capability=deterministic.capability_id,
        deterministic_result_category=(
            deterministic.result_type or deterministic.response_status
        ),
        llm_domain=interpretation.domain if interpretation else None,
        llm_goal=interpretation.goal if interpretation else None,
        llm_workflow_action=(
            interpretation.workflow_action if interpretation else None
        ),
        proposed_capabilities=json.dumps(
            list(interpretation.proposed_capabilities) if interpretation else []
        ),
        # Store category names only. Free-text reasons and field values are
        # deliberately excluded from evaluation persistence.
        extracted_field_categories=json.dumps(
            extracted_field_categories or []
        ),
        ambiguity=(
            str(interpretation.ambiguity.is_ambiguous).lower()
            if interpretation
            else None
        ),
        comparison_outcome=comparison_outcome,
        segment=segment,
        schema_validation_status=schema_validation_status,
        provider=provider[:40],
        model=model[:120],
        latency_ms=max(0, latency_ms),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error_category=error_category,
        error_message=error_message,
        error_code=error_code,
        error_http_status=error_http_status,
        provider_request_id=provider_request_id,
        error_retryable=error_retryable,
        prompt_version=settings.CONTEXTUAL_LLM_PROMPT_VERSION,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


async def run_shadow_evaluation(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    conversation_id: str,
    message: str,
    correlation_id: str,
    deterministic_response: AIChatResponse,
    provider: LLMProvider | None = None,
) -> AIContextualShadowEvaluation | None:
    if not shadow_enabled():
        return None
    context = build_context_package(
        db,
        principal,
        conversation_id,
        current_message=message,
        correlation_id=correlation_id,
    )
    deterministic = build_deterministic_observation(
        message,
        deterministic_response,
        active_workflow_type=context.active_workflow.workflow_type,
        trusted_today=context.trusted_date,
    )
    selected_provider = provider
    started = time.perf_counter()
    try:
        selected_provider = selected_provider or build_llm_provider()
        system_prompt = build_contextual_system_prompt()
        redacted_message = redact_context_text(message)
        estimated_input = estimated_tokens(
            system_prompt
            + redacted_message
            + context.model_dump_json(exclude_none=True)
        )
        if estimated_input > settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS:
            raise ProviderInputBudgetError(
                "The contextual provider input budget was exceeded."
            )
        request = LLMProviderRequest(
            system_prompt=system_prompt,
            current_message=redacted_message,
            context=context,
            max_input_tokens=settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS,
            max_output_tokens=settings.CONTEXTUAL_LLM_MAX_OUTPUT_TOKENS,
            temperature=settings.CONTEXTUAL_LLM_TEMPERATURE,
        )
        provider_response = await interpret_with_policy(
            selected_provider,
            request,
            timeout_seconds=settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS,
            retry_count=settings.CONTEXTUAL_LLM_RETRY_COUNT,
        )
        approved = {
            item.capability_id for item in context.approved_capabilities
        }
        comparison = compare_interpretations(
            deterministic,
            provider_response.interpretation,
            active_workflow_type=context.active_workflow.workflow_type,
            message=message,
            approved_capabilities=approved,
        )
        return _store(
            db,
            principal=principal,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            active_workflow_type=context.active_workflow.workflow_type,
            deterministic=deterministic,
            provider=provider_response.provider,
            model=provider_response.model,
            latency_ms=provider_response.latency_ms,
            comparison_outcome=comparison.comparison_outcome,
            segment=comparison.segment,
            schema_validation_status=comparison.schema_validation_status,
            interpretation=provider_response.interpretation,
            extracted_field_categories=comparison.extracted_field_categories,
            input_tokens=provider_response.token_usage.input_tokens,
            output_tokens=provider_response.token_usage.output_tokens,
            provider_request_id=provider_response.request_id,
        )
    except LLMProviderError as exc:
        category = exc.category
        outcome = (
            "timeout"
            if category == "provider_timeout"
            else "invalid_structured_output"
            if category
            in {"provider_invalid_response", "provider_structured_output"}
            else "provider_failure"
        )
        provider_name = getattr(
            selected_provider,
            "name",
            settings.CONTEXTUAL_LLM_PROVIDER,
        )
        model_name = getattr(
            selected_provider,
            "model",
            settings.CONTEXTUAL_LLM_MODEL,
        )
        return _store(
            db,
            principal=principal,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            active_workflow_type=context.active_workflow.workflow_type,
            deterministic=deterministic,
            provider=provider_name or "unknown",
            model=model_name or "unknown",
            latency_ms=int((time.perf_counter() - started) * 1000),
            comparison_outcome=outcome,
            segment=(
                "active_workflow_follow_up"
                if context.active_workflow.workflow_type != "none"
                else "standalone"
            ),
            schema_validation_status=(
                "invalid" if outcome == "invalid_structured_output" else "not_run"
            ),
            error_category=category,
            error_message=exc.safe_message,
            error_code=exc.code,
            error_http_status=exc.http_status,
            provider_request_id=exc.request_id,
            error_retryable=exc.retryable,
        )


async def run_shadow_evaluation_background(
    principal: AuthenticatedPrincipal,
    *,
    conversation_id: str,
    message: str,
    correlation_id: str,
    deterministic_response_payload: dict,
) -> None:
    """Run after the HTTP response; all exceptions are employee-invisible."""
    db = SessionLocal()
    try:
        response = AIChatResponse.model_validate(deterministic_response_payload)
        await run_shadow_evaluation(
            db,
            principal,
            conversation_id=conversation_id,
            message=message,
            correlation_id=correlation_id,
            deterministic_response=response,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Contextual LLM shadow evaluation failed correlation_id=%s",
            correlation_id,
        )
    finally:
        db.close()


def _metrics(rows: list[AIContextualShadowEvaluation]) -> dict:
    total = len(rows)
    if not total:
        return {
            "total": 0,
            "domain_accuracy": 0.0,
            "goal_accuracy": 0.0,
            "workflow_action_accuracy": 0.0,
            "multi_field_extraction_precision": 0.0,
            "multi_field_extraction_recall": 0.0,
            "clarification_accuracy": 0.0,
            "reference_resolution_accuracy": 0.0,
            "unsafe_proposal_rate": 0.0,
            "structured_output_validity_rate": 0.0,
            "timeout_rate": 0.0,
            "deterministic_llm_disagreement_rate": 0.0,
            "segments": {},
        }
    valid = [row for row in rows if row.schema_validation_status == "valid"]
    agreement = {"exact_agreement", "compatible_agreement"}
    by_segment: dict[str, list[AIContextualShadowEvaluation]] = defaultdict(list)
    for row in rows:
        by_segment[row.segment].append(row)

    def rate(predicate, values=rows):
        return round(
            sum(1 for item in values if predicate(item)) / max(1, len(values)),
            4,
        )

    # Runtime shadow metrics use the deterministic system as the comparison
    # baseline. Dataset metrics provide independently reviewed accuracy.
    metrics = {
        "total": total,
        "domain_accuracy": rate(lambda row: row.llm_domain == "leave", valid),
        "goal_accuracy": rate(
            lambda row: row.llm_goal == row.deterministic_goal, valid
        ),
        "workflow_action_accuracy": rate(
            lambda row: row.comparison_outcome in agreement
            or row.comparison_outcome
            == "llm_identifies_workflow_continuation",
            valid,
        ),
        "multi_field_extraction_precision": rate(
            lambda row: row.comparison_outcome != "extraction_disagreement",
            valid,
        ),
        "multi_field_extraction_recall": rate(
            lambda row: row.comparison_outcome != "extraction_disagreement",
            valid,
        ),
        "clarification_accuracy": rate(
            lambda row: row.comparison_outcome not in {
                "routing_disagreement",
                "unsafe_llm_proposal",
            },
            valid,
        ),
        "reference_resolution_accuracy": rate(
            lambda row: row.comparison_outcome not in {
                "routing_disagreement",
                "unsafe_llm_proposal",
            },
            valid,
        ),
        "unsafe_proposal_rate": rate(
            lambda row: row.comparison_outcome == "unsafe_llm_proposal"
        ),
        "structured_output_validity_rate": rate(
            lambda row: row.schema_validation_status == "valid"
        ),
        "timeout_rate": rate(lambda row: row.comparison_outcome == "timeout"),
        "deterministic_llm_disagreement_rate": rate(
            lambda row: row.comparison_outcome
            in {
                "routing_disagreement",
                "extraction_disagreement",
                "llm_identifies_workflow_continuation",
                "deterministic_identifies_workflow_continuation",
            }
        ),
        "segments": {
            segment: {
                "count": len(values),
                "validity_rate": rate(
                    lambda row: row.schema_validation_status == "valid",
                    values,
                ),
                "disagreement_rate": rate(
                    lambda row: row.comparison_outcome
                    not in agreement,
                    values,
                ),
            }
            for segment, values in by_segment.items()
        },
    }
    return metrics


def shadow_diagnostics(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    limit: int = 50,
) -> ShadowDiagnosticsResponse:
    query = db.query(AIContextualShadowEvaluation)
    if principal.role not in {"admin", "super_admin"}:
        query = query.filter(
            AIContextualShadowEvaluation.actor_employee_id
            == principal.employee_id
        )
    rows = query.order_by(AIContextualShadowEvaluation.created_at.desc()).limit(
        max(1, min(limit, 100))
    ).all()
    return ShadowDiagnosticsResponse(
        evaluations=[
            ShadowDiagnosticItem(
                id=row.id,
                conversation_id=row.conversation_id,
                correlation_id=row.correlation_id,
                active_workflow_type=row.active_workflow_type,
                deterministic_goal=row.deterministic_goal,
                deterministic_capability=row.deterministic_capability,
                llm_domain=row.llm_domain,
                llm_goal=row.llm_goal,
                llm_workflow_action=row.llm_workflow_action,
                proposed_capabilities=_json_list(row.proposed_capabilities),
                extracted_field_categories=_json_list(
                    row.extracted_field_categories
                ),
                ambiguity=(
                    row.ambiguity == "true" if row.ambiguity is not None else None
                ),
                comparison_outcome=row.comparison_outcome,
                segment=row.segment,
                schema_validation_status=row.schema_validation_status,
                provider=row.provider,
                model=row.model,
                latency_ms=row.latency_ms,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                error_category=row.error_category,
                error_message=row.error_message,
                error_code=row.error_code,
                error_http_status=row.error_http_status,
                provider_request_id=row.provider_request_id,
                error_retryable=row.error_retryable,
                prompt_version=row.prompt_version,
                created_at=row.created_at,
            )
            for row in rows
        ],
        metrics=_metrics(rows),
    )


def contextual_provider_status(
    db: Session,
    principal: AuthenticatedPrincipal,
) -> ContextualProviderStatusResponse:
    """Return safe aggregate status; never return or probe credentials."""
    errors = contextual_provider_configuration_errors()
    query = db.query(AIContextualShadowEvaluation)
    if principal.role not in {"admin", "super_admin"}:
        query = query.filter(
            AIContextualShadowEvaluation.actor_employee_id
            == principal.employee_id
        )
    rows = query.order_by(
        AIContextualShadowEvaluation.created_at.desc()
    ).limit(100).all()
    last = rows[0] if rows else None
    return ContextualProviderStatusResponse(
        enabled=settings.CONTEXTUAL_LLM_ENABLED,
        shadow_mode=settings.CONTEXTUAL_LLM_SHADOW_MODE,
        provider=settings.CONTEXTUAL_LLM_PROVIDER.strip().lower()
        or "disabled",
        model=settings.CONTEXTUAL_LLM_MODEL.strip() or "not_configured",
        credential_configured=bool(
            settings.CONTEXTUAL_LLM_API_KEY.strip()
        ),
        configuration_valid=not errors,
        configuration_errors=errors,
        prompt_version=settings.CONTEXTUAL_LLM_PROMPT_VERSION,
        prompt_examples=prompt_example_count(),
        recent_evaluations=len(rows),
        last_outcome=last.comparison_outcome if last else None,
        last_error_category=last.error_category if last else None,
        last_error_message=last.error_message if last else None,
        last_error_code=last.error_code if last else None,
        last_error_http_status=last.error_http_status if last else None,
        last_provider_request_id=last.provider_request_id if last else None,
        last_error_retryable=last.error_retryable if last else None,
    )
