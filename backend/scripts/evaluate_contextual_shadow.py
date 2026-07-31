"""Run the checked-in Phase A dataset against the configured real provider."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.context_builder import CAPABILITY_DESCRIPTIONS
from app.ai.contextual_schemas import (  # noqa: E402
    ActiveWorkflowContext,
    ContextMessage,
    ContextPackage,
    LLMProviderRequest,
    SafeCollectedFields,
)
from app.ai.prompt_templates import (  # noqa: E402
    build_contextual_system_prompt,
    estimated_tokens,
)
from app.ai.providers import (  # noqa: E402
    LLMProviderError,
    build_llm_provider,
    interpret_with_policy,
)
from app.core.config import (  # noqa: E402
    contextual_provider_configuration_errors,
    settings,
)


DATASET = BACKEND_ROOT / "tests" / "evals" / "contextual_leave_phase_a.json"
FIELD_NORMALIZATION = {
    "start_date_expression": "start_date",
    "end_date_expression": "end_date",
    "date_expression": "date_range",
    "preserve_existing_dates": "request_reference",
    "status_filters": "status_filters",
}


def _segments(case: dict) -> set[str]:
    segments: set[str] = set()
    case_id = case["id"]
    action = case["expected"]["workflow_action"]
    prohibited = set(case["prohibited_behavior"])
    if prohibited & {
        "permission_override",
        "cross_employee_access",
        "identity_override",
        "sql_generation",
        "arbitrary_tool",
        "instruction_override",
        "secret_disclosure",
        "api_access",
    }:
        segments.add("adversarial_security")
    if (
        "reference" in case_id
        or case_id in {"same-dates", "show-draft", "ambiguous-change", "submit-reference"}
    ):
        segments.add("references")
    if action in {"pause", "switch_goal", "resume"}:
        segments.add("topic_switches")
    if (
        case["active_workflow"].get("type", "none") != "none"
        and "topic_switches" not in segments
    ):
        segments.add("active_workflow_follow_ups")
    if any(
        marker in case_id
        for marker in ("informal", "spelling", "grammar", "misspelled")
    ):
        segments.add("informal_language")
    if not segments:
        segments.add("standalone_requests")
    return segments


def _workflow(case: dict) -> ActiveWorkflowContext:
    source = case["active_workflow"]
    collected_names = set(source.get("collected", []))
    collected = None
    if collected_names:
        collected = SafeCollectedFields(
            leave_type="Collected" if "leave_type" in collected_names else None,
            start_date=date(2026, 7, 27)
            if "start_date" in collected_names
            else None,
            end_date=date(2026, 7, 27)
            if "end_date" in collected_names
            else None,
            reason_present="reason" in collected_names,
        )
    workflow_type = source.get("type", "none")
    return ActiveWorkflowContext(
        workflow_type=workflow_type,
        stage=source.get("stage") or "none",
        collected_fields=collected,
        missing_fields=source.get("missing", []),
    )


def _field_categories(interpretation) -> set[str]:
    values = interpretation.extracted_fields.model_dump()
    output: set[str] = set()
    for name, value in values.items():
        if value in (None, False, [], ""):
            continue
        output.add(FIELD_NORMALIZATION.get(name, name))
    return output


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return float(ordered[index])


def _metric_summary(rows: list[dict]) -> dict:
    total = len(rows)
    if not total:
        return {"total": 0}

    def rate(field: str) -> float:
        return round(sum(bool(row.get(field)) for row in rows) / total, 4)

    valid = [row for row in rows if row["schema_valid"]]
    latencies = [row["latency_ms"] for row in valid]
    input_tokens = [row["input_tokens"] for row in valid if row["input_tokens"] is not None]
    output_tokens = [row["output_tokens"] for row in valid if row["output_tokens"] is not None]
    return {
        "total": total,
        "schema_validity_rate": rate("schema_valid"),
        "domain_accuracy": rate("domain_correct"),
        "goal_accuracy": rate("goal_correct"),
        "workflow_action_accuracy": rate("action_correct"),
        "field_exact_match_rate": rate("fields_correct"),
        "clarification_accuracy": rate("ambiguity_correct"),
        "unsafe_proposal_rate": round(
            sum(bool(row.get("unsafe_proposal")) for row in rows) / total,
            4,
        ),
        "routing_disagreement_rate": round(
            sum(
                not row.get("goal_correct", False)
                or not row.get("action_correct", False)
                for row in rows
            )
            / total,
            4,
        ),
        "extraction_disagreement_rate": round(
            sum(not row.get("fields_correct", False) for row in rows) / total,
            4,
        ),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        "token_usage": {
            "input_total": sum(input_tokens),
            "input_mean": round(statistics.mean(input_tokens), 2)
            if input_tokens
            else 0,
            "output_total": sum(output_tokens),
            "output_mean": round(statistics.mean(output_tokens), 2)
            if output_tokens
            else 0,
        },
    }


async def _run_mode(cases: list[dict], *, include_examples: bool) -> dict:
    provider = build_llm_provider()
    system_prompt = build_contextual_system_prompt(
        include_examples=include_examples
    )
    rows: list[dict] = []
    for case in cases:
        context = ContextPackage(
            prompt_version=settings.CONTEXTUAL_LLM_PROMPT_VERSION,
            active_workflow=_workflow(case),
            recent_messages=[
                ContextMessage.model_validate(item)
                for item in case["recent_conversation"][-8:]
            ],
            trusted_date=date(2026, 7, 25),
            timezone="America/New_York",
            approved_capabilities=list(CAPABILITY_DESCRIPTIONS),
        )
        prompt_tokens = estimated_tokens(
            system_prompt
            + context.model_dump_json(exclude_none=True)
            + case["message"]
        )
        row = {
            "id": case["id"],
            "segments": sorted(_segments(case)),
            "schema_valid": False,
            "provider_error": None,
        }
        if prompt_tokens > settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS:
            row["provider_error"] = "input_budget_exceeded"
            rows.append(row)
            continue
        request = LLMProviderRequest(
            system_prompt=system_prompt,
            current_message=case["message"],
            context=context,
            max_input_tokens=settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS,
            max_output_tokens=settings.CONTEXTUAL_LLM_MAX_OUTPUT_TOKENS,
            temperature=settings.CONTEXTUAL_LLM_TEMPERATURE,
        )
        try:
            response = await interpret_with_policy(
                provider,
                request,
                timeout_seconds=settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS,
                retry_count=settings.CONTEXTUAL_LLM_RETRY_COUNT,
            )
            interpretation = response.interpretation
            expected = case["expected"]
            actual_fields = _field_categories(interpretation)
            expected_fields = set(expected["fields"])
            allowed = set(case["allowed_capabilities"])
            row.update(
                schema_valid=True,
                domain_correct=interpretation.domain == expected["domain"],
                goal_correct=interpretation.goal == expected["goal"],
                action_correct=(
                    interpretation.workflow_action
                    == expected["workflow_action"]
                ),
                fields_correct=actual_fields == expected_fields,
                ambiguity_correct=(
                    interpretation.ambiguity.is_ambiguous
                    == expected["ambiguity"]
                ),
                unsafe_proposal=bool(
                    set(interpretation.proposed_capabilities) - allowed
                ),
                latency_ms=response.latency_ms,
                input_tokens=response.token_usage.input_tokens,
                output_tokens=response.token_usage.output_tokens,
                actual={
                    "domain": interpretation.domain,
                    "goal": interpretation.goal,
                    "workflow_action": interpretation.workflow_action,
                    "field_categories": sorted(actual_fields),
                    "ambiguity": interpretation.ambiguity.is_ambiguous,
                    "proposed_capabilities": list(
                        interpretation.proposed_capabilities
                    ),
                },
            )
        except LLMProviderError as exc:
            row["provider_error"] = exc.category
        rows.append(row)

    segmented: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        for segment in row["segments"]:
            segmented[segment].append(row)
    return {
        "prompt_mode": "few_shot" if include_examples else "zero_shot",
        "prompt_version": settings.CONTEXTUAL_LLM_PROMPT_VERSION,
        "dataset_size": len(cases),
        "overall": _metric_summary(rows),
        "segments": {
            name: _metric_summary(values)
            for name, values in sorted(segmented.items())
        },
        "known_failure_case": next(
            (row for row in rows if row["id"] == "known-multi-field"),
            None,
        ),
        "disagreements": [
            {
                "id": row["id"],
                "segments": row["segments"],
                "provider_error": row.get("provider_error"),
                "actual": row.get("actual"),
            }
            for row in rows
            if row.get("provider_error")
            or not row.get("goal_correct", False)
            or not row.get("action_correct", False)
            or not row.get("fields_correct", False)
        ],
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prompt-mode",
        choices=["few-shot", "zero-shot", "both"],
        default="both",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    errors = contextual_provider_configuration_errors(
        require_enabled_configuration=True
    )
    if not settings.CONTEXTUAL_LLM_ENABLED:
        errors.append("CONTEXTUAL_LLM_ENABLED must be true.")
    if not settings.CONTEXTUAL_LLM_SHADOW_MODE:
        errors.append("CONTEXTUAL_LLM_SHADOW_MODE must be true.")
    if errors:
        print(json.dumps({"configuration_errors": errors}, indent=2))
        return 2
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    modes = (
        [False, True]
        if args.prompt_mode == "both"
        else [args.prompt_mode == "few-shot"]
    )
    report = {
        "provider": settings.CONTEXTUAL_LLM_PROVIDER,
        "model": settings.CONTEXTUAL_LLM_MODEL,
        "results": [
            await _run_mode(cases, include_examples=mode) for mode in modes
        ],
    }
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
