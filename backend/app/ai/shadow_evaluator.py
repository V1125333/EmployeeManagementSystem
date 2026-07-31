"""Compare deterministic behavior with observation-only contextual output."""

from __future__ import annotations

import re

from app.ai.contextual_schemas import (
    ContextualInterpretation,
    DeterministicObservation,
    ShadowEvaluationSummary,
)
from app.ai.leave_intent import parse_leave_goal
from app.schemas.ai import AIChatResponse


_TOOL_CAPABILITY = {
    "get_my_leave_balance": "leave.balance.read_self",
    "compare_my_leave_balance": "leave.balance.compare_self",
    "get_my_recent_leave_requests": "leave.requests.list_self",
    "get_my_leave_request_status": "leave.request.status_self",
    "get_my_leave_request_details": "leave.request.details_self",
    "explain_my_leave_decision": "leave.request.decision_explain_self",
    "check_my_leave_eligibility": "leave.eligibility.check_self",
    "prepare_my_leave_request": "leave.draft.prepare_self",
    "get_my_leave_request_draft": "leave.draft.read_self",
    "update_my_leave_request_draft": "leave.draft.update_self",
    "discard_my_leave_request_draft": "leave.draft.discard_self",
}
_INTENT_GOAL = {
    "balance": "check_leave_balance",
    "balance_comparison": "compare_leave_balance",
    "request_list": "list_leave_requests",
    "request_status": "check_leave_request_status",
    "request_details": "check_leave_request_status",
    "decision_explanation": "explain_leave_decision",
    "eligibility": "check_leave_eligibility",
    "working_days": "check_leave_eligibility",
    "holiday_overlap": "check_leave_eligibility",
    "request_overlap": "check_leave_eligibility",
    "draft_prepare": "prepare_leave_request",
    "draft_get": "review_leave_draft",
    "draft_update": "prepare_leave_request",
    "draft_discard": "discard_leave_draft",
    "draft_continue": "review_leave_draft",
    "submission_request": "submit_leave_request",
    "unsupported": "unknown",
}
_SECURITY_PATTERN = re.compile(
    r"(?:employee[_ -]?id|x-user-|/api/|\bselect\b.+\bfrom\b|"
    r"\bpretend\b.+\b(?:admin|ceo)\b|\bignore\b.+\binstruction)",
    re.IGNORECASE,
)


def _field_categories(goal) -> list[str]:
    fields: list[str] = []
    if goal.leave_type:
        fields.append("leave_type")
    if goal.start_date:
        fields.append("start_date")
    if goal.end_date:
        fields.append("end_date")
    if goal.reason:
        fields.append("reason")
    if goal.statuses:
        fields.append("status_filter")
    if goal.threshold is not None:
        fields.append("threshold")
    if goal.trusted_request_id:
        fields.append("request_reference")
    return fields


def build_deterministic_observation(
    message: str,
    response: AIChatResponse,
    *,
    active_workflow_type: str,
    trusted_today,
) -> DeterministicObservation:
    goal = parse_leave_goal(message, today=trusted_today)
    result_type = response.result.type if response.result else None
    actual_goal = _INTENT_GOAL.get(goal.intent, "unknown")
    if result_type and result_type.startswith("leave_intake"):
        actual_goal = "prepare_leave_request"
    elif result_type == "leave_request_draft":
        actual_goal = {
            "discard_my_leave_request_draft": "discard_leave_draft",
            "get_my_leave_request_draft": "review_leave_draft",
        }.get(response.tool_used, "prepare_leave_request")
    capability = _TOOL_CAPABILITY.get(response.tool_used)
    if result_type and result_type.startswith("leave_intake"):
        capability = "continue_leave_intake"
    return DeterministicObservation(
        response_status=response.status,
        result_type=result_type,
        goal=actual_goal,
        capability_id=capability,
        continued_active_workflow=bool(
            active_workflow_type != "none"
            and result_type
            and (
                result_type.startswith("leave_intake")
                or result_type == "leave_request_draft"
            )
        ),
        extracted_field_categories=_field_categories(goal),
    )


def _llm_field_categories(
    interpretation: ContextualInterpretation,
) -> list[str]:
    fields = interpretation.extracted_fields
    values = fields.model_dump()
    categories: list[str] = []
    for name, value in values.items():
        if value not in (None, False, [], ""):
            categories.append(name)
    return categories


def compare_interpretations(
    deterministic: DeterministicObservation,
    interpretation: ContextualInterpretation,
    *,
    active_workflow_type: str,
    message: str,
    approved_capabilities: set[str],
) -> ShadowEvaluationSummary:
    proposed = set(interpretation.proposed_capabilities)
    unsafe = bool(proposed - approved_capabilities)
    llm_fields = _llm_field_categories(interpretation)
    if unsafe:
        outcome = "unsafe_llm_proposal"
    elif (
        active_workflow_type != "none"
        and interpretation.workflow_action in {"continue", "modify", "resume"}
        and not deterministic.continued_active_workflow
    ):
        outcome = "llm_identifies_workflow_continuation"
    elif (
        deterministic.continued_active_workflow
        and interpretation.workflow_action
        not in {"continue", "modify", "resume"}
    ):
        outcome = "deterministic_identifies_workflow_continuation"
    elif deterministic.goal != interpretation.goal:
        outcome = "routing_disagreement"
    elif set(deterministic.extracted_field_categories) != set(llm_fields):
        outcome = "extraction_disagreement"
    elif (
        deterministic.capability_id
        and deterministic.capability_id
        in interpretation.proposed_capabilities
    ):
        outcome = "exact_agreement"
    else:
        outcome = "compatible_agreement"

    segment = (
        "security_adversarial"
        if _SECURITY_PATTERN.search(message)
        else "topic_switch"
        if active_workflow_type != "none"
        and interpretation.workflow_action in {"pause", "switch_goal", "cancel"}
        else "active_workflow_follow_up"
        if active_workflow_type != "none"
        else "standalone"
    )
    return ShadowEvaluationSummary(
        comparison_outcome=outcome,
        segment=segment,
        schema_validation_status="valid",
        extracted_field_categories=llm_fields,
    )
