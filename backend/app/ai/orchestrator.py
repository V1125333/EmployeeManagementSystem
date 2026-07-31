"""Deterministic, typed, tool-grounded orchestrator for Leave Agent Phase 1."""

from __future__ import annotations

import re
import uuid
from datetime import date

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.conversation_context import (
    remember_draft,
    remember_eligibility,
    remember_request,
    resolve_draft_reference,
    resolve_eligibility_reference,
    resolve_request_reference,
)
from app.ai.leave_draft_tools import TrustedDraftReference
from app.ai.leave_intake import (
    extract_intake_slots,
    is_informal_leave_request,
    is_intake_follow_up,
)
from app.ai.leave_balance_tool import AIToolException
from app.ai.leave_intent import parse_leave_goal
from app.ai.tool_registry import AI_TOOLS
from app.core.authentication import AuthenticatedPrincipal
from app.schemas.ai import (
    AIChatResponse,
    AIMessage,
    AIToolError,
    AmbiguousLeaveRequestCard,
    CompareMyLeaveBalanceInput,
    CompareMyLeaveBalanceOutput,
    CheckMyLeaveEligibilityInput,
    DiscardMyLeaveRequestDraftInput,
    ExplainMyLeaveDecisionInput,
    GetMyLeaveBalanceInput,
    GetMyLeaveRequestDetailsInput,
    GetMyLeaveRequestStatusInput,
    GetMyRecentLeaveRequestsInput,
    GetMyLeaveRequestDraftInput,
    LeaveBalanceComparisonCard,
    LeaveBalanceResultCard,
    LeaveEligibilityClarificationCard,
    LeaveEligibilityResultCard,
    LeaveIntakeCancelledCard,
    LeaveIntakeCollectedFields,
    LeaveIntakeQuestionCard,
    LeaveIntakeStateOutput,
    LeaveRequestDraftCard,
    LeaveRequestListCard,
    LeaveRequestStatusCard,
    LeaveRequestToolItem,
    RejectionExplanationCard,
    PrepareMyLeaveRequestInput,
    UpdateMyLeaveRequestDraftInput,
)
from app.models.employee import Employee
from app.services.leave_eligibility_service import local_now
from app.services import leave_intake_service as intake_service

_OTHER_PERSON_PATTERNS = (
    r"\b(employee|user|manager)\s*[_-]?id\b",
    r"\bx-user-(id|email)\b",
    r"\banother employee\b",
    r"\bsomeone else\b",
    r"\bfor\s+[\w.+-]+@[\w.-]+\b",
    r"\b(their|his|her)\s+leave\b",
    r"\b(?!my\b)[A-Za-z]+['’]s\s+leave\b",
    r"\bcan\s+[A-Z][a-z]+\s+take\s+leave\b",
    r"\bprepare\b.*\bleave\s+for\s+(?!next\b|this\b|today\b|tomorrow\b|20\d{2}\b)[a-z]+\b",
    r"\b(?:approver|manager|recipient)\s+(?:is\s+)?[a-z]+\b",
    r"\bsend\s+(?:it\s+)?to\s+(?:approver|manager)\b",
)
_DANGEROUS_INPUT_PATTERNS = (
    r"\b(select|insert|update|delete|drop|alter)\s+.+\b(from|into|table|where)\b",
    r"/api/",
    r"\btool[_ -]?name\b",
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
)


def _unsafe_scope(message: str) -> bool:
    return any(
        re.search(pattern, message, flags=re.IGNORECASE)
        for pattern in (*_OTHER_PERSON_PATTERNS, *_DANGEROUS_INPUT_PATTERNS)
    )


def _number(value: float) -> str:
    return f"{value:g}"


def _balance_answer(output) -> str:
    if len(output.balances) == 1:
        item = output.balances[0]
        available = (
            item.available
            if isinstance(item.available, str)
            else f"{_number(item.available)} days"
        )
        return (
            f"You have {available} of {item.leave_type} available. "
            f"Used: {_number(item.used)} days; pending: {_number(item.pending)} days."
        )
    return (
        f"I found {len(output.balances)} leave balances for {output.year}. "
        "The verified values are shown below."
    )


def _status_answer(item: LeaveRequestToolItem) -> str:
    dates = (
        item.start_date.strftime("%b %d, %Y")
        if item.start_date == item.end_date
        else f"{item.start_date:%b %d, %Y} to {item.end_date:%b %d, %Y}"
    )
    if item.status in {"pending", "submitted"}:
        owner = f" with {item.approver}" if item.approver else ""
        duration = (
            f" for {item.pending_duration_days} day(s)"
            if item.pending_duration_days is not None
            else ""
        )
        return (
            f"Your {item.leave_type} request for {dates} is officially "
            f"{item.status}{owner}{duration}."
        )
    if item.status == "approved":
        decided = f" by {item.decided_by}" if item.decided_by else ""
        return f"Your {item.leave_type} request for {dates} was approved{decided}."
    if item.status == "rejected":
        return f"Your {item.leave_type} request for {dates} was rejected."
    return (
        f"Your {item.leave_type} request for {dates} is officially {item.status}."
    )


def _eligibility_answer(output, intent: str) -> str:
    dates = (
        output.start_date.strftime("%b %d, %Y")
        if output.start_date == output.end_date
        else f"{output.start_date:%b %d, %Y} to {output.end_date:%b %d, %Y}"
    )
    if intent == "working_days":
        return (
            f"{dates} uses {_number(output.working_day_count)} working day(s) "
            f"for {output.leave_type}."
        )
    if intent == "holiday_overlap":
        holidays = ", ".join(
            f"{item.label or 'Company holiday'} ({item.date:%b %d})"
            for item in output.company_holidays_excluded
        )
        weekends = len(output.weekend_dates_excluded)
        if holidays:
            return f"This period overlaps {holidays}; {weekends} weekend day(s) are excluded."
        return f"No company holiday overlaps this period; {weekends} weekend day(s) are excluded."
    if intent == "request_overlap":
        count = len(output.existing_overlaps)
        return (
            f"You have {count} pending or approved leave request(s) overlapping "
            f"{dates}."
        )
    if output.eligibility_status in {"eligible", "eligible_with_warnings"}:
        warning = " with policy warnings" if output.warnings else ""
        return (
            f"You are eligible{warning} for {output.leave_type} from {dates}. "
            f"It uses {_number(output.required_leave_units)} leave day(s), with "
            f"{output.available_leave_balance} available."
        )
    if output.eligibility_status == "requires_information":
        reasons = "; ".join(item.message for item in output.blocking_reasons)
        return f"I need more information to confirm eligibility: {reasons}"
    reasons = "; ".join(item.message for item in output.blocking_reasons)
    return f"You are not eligible for this date range: {reasons}"


def _draft_answer(output) -> str:
    dates = (
        output.start_date.strftime("%b %d, %Y")
        if output.start_date == output.end_date
        else f"{output.start_date:%b %d, %Y} to {output.end_date:%b %d, %Y}"
    )
    if output.status == "discarded":
        return "I discarded your AI leave draft. No official leave request was changed."
    if output.status == "ready_for_confirmation":
        return (
            f"Your {output.leave_type} draft for {dates} is ready for confirmation. "
            "It has not been submitted."
        )
    if output.status == "not_eligible":
        return (
            f"I prepared a non-submittable draft for {output.leave_type} on {dates}. "
            "The verified blockers are shown below."
        )
    if output.status == "requires_information":
        reasons = "; ".join(item.message for item in output.blocking_reasons)
        return (
            f"I saved your {output.leave_type} draft for {dates}, but it still "
            "needs information before confirmation."
            + (f" {reasons}" if reasons else "")
        )
    return (
        f"I prepared your {output.leave_type} draft for {dates}. "
        f"It uses {_number(output.working_day_count)} working day(s) and has not been submitted."
    )


def _tool_error_response(
    exc: AIToolException,
    conversation_id: str,
    correlation_id: str,
    tool_name: str,
) -> AIChatResponse:
    if exc.error.code == "AMBIGUOUS_LEAVE_REQUEST":
        candidates = [
            LeaveRequestToolItem.model_validate(item)
            for item in exc.error.details.get("candidates", [])
        ]
        return AIChatResponse(
            conversation_id=conversation_id,
            status="needs_clarification",
            message=AIMessage(
                content="I found multiple matching requests. Please choose one by its leave type and dates."
            ),
            result=AmbiguousLeaveRequestCard(candidates=candidates),
            error=exc.error,
            tool_used=tool_name,
            correlation_id=correlation_id,
        )
    return AIChatResponse(
        conversation_id=conversation_id,
        status="failed",
        message=AIMessage(content=exc.error.message),
        error=exc.error,
        tool_used=tool_name,
        correlation_id=correlation_id,
    )


def _intake_question(
    state: LeaveIntakeStateOutput,
    *,
    prompt: str | None = None,
    field: str | None = None,
) -> tuple[str, str]:
    fields = state.collected_fields
    if field:
        return field, prompt or "Please provide the missing information."
    if "date_range" in state.missing_required_fields:
        if fields.duration_days:
            duration_label = (
                "two" if fields.duration_days == 2 else str(fields.duration_days)
            )
            return (
                "date_range",
                f"What date should your {duration_label}-day leave start?",
            )
        return "date_range", "What dates do you need leave for?"
    if "leave_type" in state.missing_required_fields:
        return "leave_type", "Which leave type would you like to use?"
    if "reason" in state.missing_required_fields:
        return (
            "reason",
            "A reason is required by the current leave policy. What reason should I add?",
        )
    if "supporting_information" in state.missing_required_fields:
        return (
            "supporting_information",
            "This leave type requires supporting information. Please provide it before I create the draft.",
        )
    return "reason", "Would you like to add a reason? It is optional."


def _intake_response(
    state: LeaveIntakeStateOutput,
    conversation_id: str,
    correlation_id: str,
    *,
    prompt: str | None = None,
    field: str | None = None,
) -> AIChatResponse:
    question_field, question = _intake_question(
        state, prompt=prompt, field=field
    )
    return AIChatResponse(
        conversation_id=conversation_id,
        status="needs_clarification",
        message=AIMessage(content=question),
        result=LeaveIntakeQuestionCard(
            field=question_field,
            prompt=question,
            intake=state,
        ),
        correlation_id=correlation_id,
    )


def _run_leave_intake(
    db: Session,
    principal: AuthenticatedPrincipal,
    message: str,
    conversation_id: str,
    correlation_id: str,
    *,
    today,
    existing,
) -> AIChatResponse:
    current = (
        intake_service.intake_state(existing).collected_fields
        if existing
        else LeaveIntakeCollectedFields()
    )
    confidence = (
        dict(intake_service.intake_state(existing).source_confidence)
        if existing
        else {}
    )
    update = extract_intake_slots(message, today=today, current=current)
    if update.start_over:
        intake_service.clear_leave_intake(
            db, principal.employee_id, conversation_id
        )
        return AIChatResponse(
            conversation_id=conversation_id,
            status="completed",
            message=AIMessage(
                content="I cleared the leave intake. No leave request or draft was created."
            ),
            result=LeaveIntakeCancelledCard(
                message="Your collected leave details were cleared."
            ),
            correlation_id=correlation_id,
        )

    values = current.model_dump()
    if update.leave_type:
        values["leave_type"] = update.leave_type
    if update.start_date and update.end_date and not update.ambiguous_dates:
        values["start_date"] = update.start_date
        values["end_date"] = update.end_date
    if update.duration_days:
        values["duration_days"] = update.duration_days
    if update.reason:
        values["reason"] = update.reason
        values["reason_skipped"] = False
    if update.supporting_information:
        values["supporting_information"] = update.supporting_information
    if update.skip_reason:
        values["reason"] = None
        values["reason_skipped"] = True
    fields = LeaveIntakeCollectedFields.model_validate(values)
    confidence.update(update.confidence)
    requirements = intake_service.get_leave_intake_requirements(
        db, fields.leave_type
    )
    state = intake_service.save_leave_intake(
        db,
        principal.employee_id,
        conversation_id,
        fields,
        confidence,
        requirements,
    )

    if update.ambiguous_dates:
        return _intake_response(
            state,
            conversation_id,
            correlation_id,
            field="date_range",
            prompt=(
                "“Next week” could mean different dates. Which exact day or "
                "date range do you need?"
            ),
        )
    if state.missing_required_fields:
        return _intake_response(state, conversation_id, correlation_id)

    fields = state.collected_fields
    if (
        not requirements.reason_required
        and not fields.reason
        and not fields.reason_skipped
    ):
        if not fields.reason_prompted:
            fields = fields.model_copy(update={"reason_prompted": True})
            state = intake_service.save_leave_intake(
                db,
                principal.employee_id,
                conversation_id,
                fields,
                confidence,
                requirements,
            )
        return _intake_response(state, conversation_id, correlation_id)

    tool_name = "prepare_my_leave_request"
    try:
        output = AI_TOOLS[tool_name](
            db,
            principal,
            PrepareMyLeaveRequestInput(
                leave_type=fields.leave_type,
                start_date=fields.start_date,
                end_date=fields.end_date,
                reason=fields.reason,
            ),
            correlation_id=correlation_id,
            conversation_id=conversation_id,
        )
        intake_service.clear_leave_intake(
            db, principal.employee_id, conversation_id
        )
        remember_draft(
            conversation_id,
            principal.employee_id,
            output.draft_id,
            output.version,
        )
        return AIChatResponse(
            conversation_id=conversation_id,
            status="completed",
            message=AIMessage(content=_draft_answer(output)),
            result=LeaveRequestDraftCard(draft=output),
            tool_used=tool_name,
            correlation_id=correlation_id,
        )
    except AIToolException as exc:
        return _tool_error_response(
            exc, conversation_id, correlation_id, tool_name
        )


async def run_leave_balance_chat(
    db: Session,
    principal: AuthenticatedPrincipal,
    message: str,
    conversation_id: str | None,
    correlation_id: str,
) -> AIChatResponse:
    resolved_conversation_id = conversation_id or str(uuid.uuid4())
    if _unsafe_scope(message):
        return AIChatResponse(
            conversation_id=resolved_conversation_id,
            status="unsupported",
            message=AIMessage(
                content=(
                    "I can only read the signed-in user's own leave records. "
                    "Identity, SQL, API paths, and tool selection cannot be supplied in chat."
                )
            ),
            correlation_id=correlation_id,
        )

    trusted_request_id = resolve_request_reference(
        conversation_id, principal.employee_id
    )
    employee = db.query(Employee).filter(Employee.id == principal.employee_id).first()
    trusted_now, _ = local_now(db, employee) if employee else (None, None)
    try:
        intake = intake_service.get_leave_intake(
            db, principal.employee_id, conversation_id
        )
    except intake_service.LeaveIntakeError as exc:
        return AIChatResponse(
            conversation_id=resolved_conversation_id,
            status="needs_clarification",
            message=AIMessage(content=exc.message),
            result=LeaveIntakeCancelledCard(
                title="Leave intake expired",
                message="The expired intake was cleared. Please start again.",
            ),
            error=AIToolError(code="INTAKE_EXPIRED", message=exc.message),
            correlation_id=correlation_id,
        )
    eligibility_reference = resolve_eligibility_reference(
        conversation_id, principal.employee_id
    )
    draft_reference = resolve_draft_reference(
        conversation_id, principal.employee_id
    )
    try:
        goal = parse_leave_goal(
            message,
            trusted_request_id=trusted_request_id,
            today=trusted_now.date() if trusted_now else None,
        )
    except (ValueError, ValidationError):
        goal = None
    if (
        goal
        and draft_reference
        and goal.intent == "eligibility"
        and goal.eligibility_follow_up in {"extend_one_day", "move_next_week"}
        and not re.search(r"\bwhat\s+if\b", message, re.IGNORECASE)
    ):
        goal = goal.model_copy(
            update={
                "intent": "draft_update",
                "draft_update": goal.eligibility_follow_up,
            }
        )
    if goal and goal.intent == "submission_request":
        return AIChatResponse(
            conversation_id=resolved_conversation_id,
            status="unsupported",
            message=AIMessage(
                content=(
                    "Submission is not available in this phase. I can prepare or "
                    "update a draft for your review, but no official leave request was created."
                )
            ),
            error=AIToolError(
                code="SUBMISSION_NOT_AVAILABLE_IN_PHASE_3",
                message="Official leave submission is not available in Phase 3.",
            ),
            correlation_id=correlation_id,
        )

    uses_eligibility_reference = bool(
        goal
        and (
            goal.eligibility_follow_up == "same"
            or re.search(r"\bdates we (?:just )?checked\b", message, re.IGNORECASE)
        )
        and eligibility_reference
    )
    intake_goal = bool(
        goal
        and goal.intent == "draft_prepare"
        and not uses_eligibility_reference
        and (
            is_informal_leave_request(message)
            or not goal.leave_type
            or not goal.start_date
            or not goal.end_date
            or goal.confidence == "low"
        )
    )
    intake_follow_up = bool(
        intake
        and (
            (goal and goal.intent in {"draft_prepare", "draft_update", "unsupported"})
            or (
                not goal
                and is_intake_follow_up(
                    message,
                    trusted_now.date() if trusted_now else date.today(),
                )
            )
        )
    )
    if intake_goal or intake_follow_up:
        return _run_leave_intake(
            db,
            principal,
            message,
            resolved_conversation_id,
            correlation_id,
            today=trusted_now.date() if trusted_now else date.today(),
            existing=intake,
        )

    if not goal or goal.intent == "unsupported":
        return AIChatResponse(
            conversation_id=resolved_conversation_id,
            status="unsupported",
            message=AIMessage(
                content=(
                    "I can help with your own leave balances, comparisons, request "
                    "history, request status, details, and recorded decisions, or "
                    "prepare a leave draft for your review."
                )
            ),
            correlation_id=correlation_id,
        )

    draft_intents = {
        "draft_prepare",
        "draft_get",
        "draft_update",
        "draft_discard",
        "draft_continue",
    }
    if goal.intent in draft_intents:
        try:
            trusted = (
                TrustedDraftReference(
                    draft_id=draft_reference.draft_id,
                    version=draft_reference.version,
                )
                if draft_reference
                else None
            )
            if goal.intent == "draft_prepare":
                leave_type = goal.leave_type
                start_date, end_date = goal.start_date, goal.end_date
                if goal.eligibility_follow_up == "same" or re.search(
                    r"\bdates we (?:just )?checked\b", message, re.IGNORECASE
                ):
                    if eligibility_reference:
                        leave_type = leave_type or eligibility_reference.leave_type
                        start_date = start_date or eligibility_reference.start_date
                        end_date = end_date or eligibility_reference.end_date
                missing = []
                if not leave_type:
                    missing.append("leave_type")
                if not start_date or not end_date or goal.confidence == "low":
                    missing.append("date_range")
                if missing:
                    prompt = (
                        "Tell me the leave type and exact dates to prepare."
                        if len(missing) == 2
                        else "Which leave type should I use?"
                        if missing == ["leave_type"]
                        else "Which exact dates should I use?"
                    )
                    return AIChatResponse(
                        conversation_id=resolved_conversation_id,
                        status="needs_clarification",
                        message=AIMessage(content=prompt),
                        result=LeaveEligibilityClarificationCard(
                            missing_fields=missing, prompt=prompt
                        ),
                        correlation_id=correlation_id,
                    )
                tool_name = "prepare_my_leave_request"
                output = AI_TOOLS[tool_name](
                    db,
                    principal,
                    PrepareMyLeaveRequestInput(
                        leave_type=leave_type,
                        start_date=start_date,
                        end_date=end_date,
                        reason=goal.reason,
                    ),
                    correlation_id=correlation_id,
                    conversation_id=resolved_conversation_id,
                )
            elif goal.intent == "draft_get":
                tool_name = "get_my_leave_request_draft"
                output = AI_TOOLS[tool_name](
                    db,
                    principal,
                    GetMyLeaveRequestDraftInput(),
                    conversation_id=resolved_conversation_id,
                    trusted_reference=trusted,
                )
            else:
                if not trusted:
                    current = AI_TOOLS["get_my_leave_request_draft"](
                        db,
                        principal,
                        GetMyLeaveRequestDraftInput(),
                        conversation_id=resolved_conversation_id,
                        trusted_reference=None,
                    )
                    trusted = TrustedDraftReference(
                        draft_id=current.draft_id, version=current.version
                    )
                if goal.intent == "draft_discard":
                    tool_name = "discard_my_leave_request_draft"
                    output = AI_TOOLS[tool_name](
                        db,
                        principal,
                        DiscardMyLeaveRequestDraftInput(
                            expected_version=trusted.version
                        ),
                        conversation_id=resolved_conversation_id,
                        trusted_reference=trusted,
                    )
                else:
                    from datetime import timedelta
                    start_date, end_date = goal.start_date, goal.end_date
                    if goal.draft_update in {"extend_one_day", "move_next_week"}:
                        current = AI_TOOLS["get_my_leave_request_draft"](
                            db,
                            principal,
                            GetMyLeaveRequestDraftInput(),
                            conversation_id=resolved_conversation_id,
                            trusted_reference=trusted,
                        )
                        start_date, end_date = current.start_date, current.end_date
                        if goal.draft_update == "extend_one_day":
                            end_date += timedelta(days=1)
                        else:
                            from app.ai.leave_intent import resolve_eligibility_dates
                            start_date, end_date, _ = resolve_eligibility_dates(
                                "next week", trusted_now.date()
                            )
                    tool_name = "update_my_leave_request_draft"
                    output = AI_TOOLS[tool_name](
                        db,
                        principal,
                        UpdateMyLeaveRequestDraftInput(
                            leave_type=goal.leave_type,
                            start_date=start_date,
                            end_date=end_date,
                            reason=goal.reason,
                            remove_reason=goal.draft_update == "remove_reason",
                            continue_to_confirmation=goal.intent == "draft_continue",
                            expected_version=trusted.version,
                        ),
                        correlation_id=correlation_id,
                        conversation_id=resolved_conversation_id,
                        trusted_reference=trusted,
                    )
            remember_draft(
                resolved_conversation_id,
                principal.employee_id,
                output.draft_id,
                output.version,
            )
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="completed",
                message=AIMessage(content=_draft_answer(output)),
                result=LeaveRequestDraftCard(draft=output),
                tool_used=tool_name,
                correlation_id=correlation_id,
            )
        except AIToolException as exc:
            return _tool_error_response(
                exc, resolved_conversation_id, correlation_id, tool_name
            )
        except Exception:
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="failed",
                message=AIMessage(
                    content="Your leave draft is temporarily unavailable. Please try again."
                ),
                error=AIToolError(
                    code="TOOL_UNAVAILABLE",
                    message="Your leave draft is temporarily unavailable.",
                ),
                tool_used=locals().get("tool_name"),
                correlation_id=correlation_id,
            )
    if re.search(r"\b(that|it|this)\s+(leave|request)\b", message, re.IGNORECASE) and not goal.trusted_request_id:
        if goal.intent in {
            "eligibility", "working_days", "holiday_overlap", "request_overlap"
        } and eligibility_reference:
            pass
        else:
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="needs_clarification",
                message=AIMessage(
                    content="Which leave request do you mean? Please include the leave type or date."
                ),
                correlation_id=correlation_id,
            )

    eligibility_intents = {
        "eligibility", "working_days", "holiday_overlap", "request_overlap"
    }
    if goal.intent in eligibility_intents:
        leave_type = goal.leave_type
        start_date = goal.start_date
        end_date = goal.end_date
        if goal.eligibility_follow_up:
            if not eligibility_reference:
                return AIChatResponse(
                    conversation_id=resolved_conversation_id,
                    status="needs_clarification",
                    message=AIMessage(
                        content="Which leave should I reassess? Please provide the leave type and dates."
                    ),
                    result=LeaveEligibilityClarificationCard(
                        missing_fields=["leave_type", "date_range"],
                        prompt="Tell me the leave type and date range.",
                    ),
                    correlation_id=correlation_id,
                )
            leave_type = eligibility_reference.leave_type
            start_date = eligibility_reference.start_date
            end_date = eligibility_reference.end_date
            if goal.eligibility_follow_up == "extend_one_day":
                from datetime import timedelta
                end_date += timedelta(days=1)
            elif goal.eligibility_follow_up == "move_next_week":
                from app.ai.leave_intent import resolve_eligibility_dates
                start_date, end_date, _ = resolve_eligibility_dates(
                    "next week", trusted_now.date()
                )
        missing = []
        if not leave_type:
            missing.append("leave_type")
        if not start_date or not end_date:
            missing.append("date_range")
        if goal.confidence == "low" and "date_range" not in missing:
            missing.append("date_range")
        if missing:
            prompt = (
                "Which leave type should I check?"
                if missing == ["leave_type"]
                else "What leave type and exact date range should I check?"
                if len(missing) == 2
                else "Which exact dates should I check?"
            )
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="needs_clarification",
                message=AIMessage(content=prompt),
                result=LeaveEligibilityClarificationCard(
                    missing_fields=missing,
                    prompt=prompt,
                ),
                correlation_id=correlation_id,
            )
        tool_name = "check_my_leave_eligibility"
        try:
            output = AI_TOOLS[tool_name](
                db,
                principal,
                CheckMyLeaveEligibilityInput(
                    leave_type=leave_type,
                    start_date=start_date,
                    end_date=end_date,
                ),
            )
            if output.eligibility_status == "eligible" and output.blocking_reasons:
                raise RuntimeError("Grounding invariant violated")
            remember_eligibility(
                resolved_conversation_id,
                principal.employee_id,
                output.leave_type,
                output.start_date,
                output.end_date,
            )
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="completed",
                message=AIMessage(content=_eligibility_answer(output, goal.intent)),
                result=LeaveEligibilityResultCard(eligibility=output),
                tool_used=tool_name,
                correlation_id=correlation_id,
            )
        except AIToolException as exc:
            return _tool_error_response(
                exc, resolved_conversation_id, correlation_id, tool_name
            )
        except Exception:
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="failed",
                message=AIMessage(
                    content="Your leave eligibility is temporarily unavailable. Please try again."
                ),
                error=AIToolError(
                    code="TOOL_UNAVAILABLE",
                    message="Your leave eligibility is temporarily unavailable.",
                ),
                tool_used=tool_name,
                correlation_id=correlation_id,
            )

    tool_name = {
        "balance": "get_my_leave_balance",
        "balance_comparison": "compare_my_leave_balance",
        "request_list": "get_my_recent_leave_requests",
        "request_status": "get_my_leave_request_status",
        "request_details": "get_my_leave_request_details",
        "decision_explanation": "explain_my_leave_decision",
    }[goal.intent]
    try:
        if tool_name == "get_my_leave_balance":
            output = AI_TOOLS[tool_name](
                db, principal, GetMyLeaveBalanceInput(leave_type=goal.leave_type)
            )
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="completed",
                message=AIMessage(content=_balance_answer(output)),
                result=LeaveBalanceResultCard(
                    title="My leave balance",
                    as_of=output.as_of,
                    balances=output.balances,
                ),
                tool_used=tool_name,
                correlation_id=correlation_id,
            )
        if tool_name == "compare_my_leave_balance":
            comparison_input = CompareMyLeaveBalanceInput(
                leave_type=goal.leave_type,
                comparison=goal.comparison or "highest",
                threshold=goal.threshold,
            )
            if comparison_input.comparison == "at_least":
                # Preserve the original balance tool as the single authoritative
                # read for threshold questions, then shape that verified result.
                balance_output = AI_TOOLS["get_my_leave_balance"](
                    db,
                    principal,
                    GetMyLeaveBalanceInput(leave_type=comparison_input.leave_type),
                )
                item = balance_output.balances[0]
                available = item.available if isinstance(item.available, float) else None
                output = CompareMyLeaveBalanceOutput(
                    as_of=balance_output.as_of,
                    comparison="at_least",
                    balances=balance_output.balances,
                    threshold=comparison_input.threshold,
                    meets_threshold=(
                        available is not None
                        and available >= float(comparison_input.threshold or 0)
                    ),
                )
                executed_tool = "get_my_leave_balance"
            else:
                output = AI_TOOLS[tool_name](db, principal, comparison_input)
                executed_tool = tool_name
            if output.comparison == "highest" and output.highest:
                answer = (
                    f"{output.highest.leave_type} has your highest available balance "
                    f"at {_number(output.highest.available)} days."
                )
            else:
                qualifier = "do" if output.meets_threshold else "do not"
                answer = (
                    f"You {qualifier} have at least {_number(output.threshold)} "
                    f"days of {output.balances[0].leave_type} available."
                )
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="completed",
                message=AIMessage(content=answer),
                result=LeaveBalanceComparisonCard(
                    title="Leave balance comparison",
                    **output.model_dump(exclude={"tool"}),
                ),
                tool_used=executed_tool,
                correlation_id=correlation_id,
            )
        if tool_name == "get_my_recent_leave_requests":
            output = AI_TOOLS[tool_name](
                db,
                principal,
                GetMyRecentLeaveRequestsInput(
                    statuses=goal.statuses,
                    leave_type=goal.leave_type,
                    on_date=goal.on_date,
                    limit=25 if goal.history else 12,
                ),
            )
            answer = (
                "You have no matching leave requests."
                if not output.requests
                else f"I found {output.total_matches} matching leave request(s)."
            )
            if len(output.requests) == 1:
                remember_request(
                    resolved_conversation_id,
                    principal.employee_id,
                    output.requests[0].request_id,
                )
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="completed",
                message=AIMessage(content=answer),
                result=LeaveRequestListCard(
                    title="My leave history" if goal.history else "My leave requests",
                    **output.model_dump(exclude={"tool"}),
                ),
                tool_used=tool_name,
                correlation_id=correlation_id,
            )

        common = dict(
            request_id=goal.trusted_request_id,
            leave_type=goal.leave_type,
            on_date=goal.on_date,
            status=goal.statuses[0] if goal.statuses else None,
            latest=goal.latest,
        )
        input_type = {
            "get_my_leave_request_status": GetMyLeaveRequestStatusInput,
            "get_my_leave_request_details": GetMyLeaveRequestDetailsInput,
            "explain_my_leave_decision": ExplainMyLeaveDecisionInput,
        }[tool_name]
        output = AI_TOOLS[tool_name](db, principal, input_type(**common))
        remember_request(
            resolved_conversation_id, principal.employee_id, output.request.request_id
        )
        if tool_name == "explain_my_leave_decision":
            return AIChatResponse(
                conversation_id=resolved_conversation_id,
                status="completed",
                message=AIMessage(content=output.explanation),
                result=RejectionExplanationCard(
                    title="Leave decision",
                    **output.model_dump(exclude={"tool"}),
                ),
                tool_used=tool_name,
                correlation_id=correlation_id,
            )
        return AIChatResponse(
            conversation_id=resolved_conversation_id,
            status="completed",
            message=AIMessage(content=_status_answer(output.request)),
            result=LeaveRequestStatusCard(
                title=(
                    "Leave request details"
                    if tool_name == "get_my_leave_request_details"
                    else "Leave request status"
                ),
                as_of=output.as_of,
                request=output.request,
            ),
            tool_used=tool_name,
            correlation_id=correlation_id,
        )
    except AIToolException as exc:
        return _tool_error_response(
            exc, resolved_conversation_id, correlation_id, tool_name
        )
    except Exception:
        return AIChatResponse(
            conversation_id=resolved_conversation_id,
            status="failed",
            message=AIMessage(
                content="Your leave information is temporarily unavailable. Please try again."
            ),
            error=AIToolError(
                code="TOOL_UNAVAILABLE",
                message="Your leave information is temporarily unavailable.",
            ),
            tool_used=tool_name,
            correlation_id=correlation_id,
        )
    resolve_draft_reference,
