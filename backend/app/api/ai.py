"""Secure, bounded gateway for the allowlisted Orbit AI capability."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.ai.orchestrator import run_leave_balance_chat
from app.ai.tool_registry import AI_TOOLS
from app.ai.rate_limit import (
    consume_ai_rate_limit,
    release_ai_slot,
    try_acquire_ai_slot,
)
from app.core.authentication import AuthenticatedPrincipal, get_authenticated_principal
from app.core.config import settings
from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    AIConversationCreate,
    AIConversationDetail,
    AIConversationListResponse,
    AIConversationSummary,
)
from app.ai.contextual_schemas import (
    ContextualProviderStatusResponse,
    ShadowDiagnosticsResponse,
)
from app.services.ai_conversation_service import (
    ConversationNotActive,
    ConversationNotFound,
    append_message,
    archive_conversation,
    close_conversation,
    conversation_detail,
    conversation_summary,
    create_conversation,
    delete_conversation,
    ensure_active_conversation,
    get_owned_conversation,
    list_conversations,
    restore_conversation,
    update_conversation_from_response,
)
from app.services.audit_service import log_audit
from app.services.contextual_shadow_service import (
    contextual_provider_status,
    run_shadow_evaluation_background,
    shadow_diagnostics,
    shadow_enabled,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["orbit-ai-secure"])


def _correlation_id(request: Request) -> str:
    supplied = request.headers.get("x-correlation-id", "").strip()
    if supplied and len(supplied) <= 64 and supplied.replace("-", "").replace("_", "").isalnum():
        return supplied
    return str(uuid.uuid4())


def _error(status_code: int, code: str, message: str, correlation_id: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "correlation_id": correlation_id},
    )


def _audit(
    db: Session,
    request: Request,
    principal: AuthenticatedPrincipal,
    response: AIChatResponse | None,
    *,
    outcome: str,
    latency_ms: int,
    correlation_id: str,
) -> None:
    try:
        actor = db.query(Employee).filter(Employee.id == principal.employee_id).first()
        eligibility = (
            response.result.eligibility
            if response and response.result
            and response.result.type == "leave_eligibility"
            else None
        )
        draft = (
            response.result.draft
            if response and response.result
            and response.result.type == "leave_request_draft"
            else None
        )
        intake = (
            response.result.intake
            if response and response.result
            and response.result.type in {
                "leave_intake_question",
                "leave_intake_summary",
            }
            else None
        )
        log_audit(
            db,
            actor,
            action="ai.leave_agent.chat",
            entity_type="ai_chat",
            entity_id=response.conversation_id if response else None,
            reason=outcome,
            metadata={
                "correlation_id": correlation_id,
                "capability": (
                    "leave_request_preparation_phase_3"
                    if draft
                    else "leave_intake_phase_3_5"
                    if intake
                    else
                    "leave_eligibility_phase_2"
                    if eligibility
                    else "leave_agent_phase_1"
                ),
                "tool": response.tool_used if response else None,
                "tool_execution_status": (
                    "succeeded"
                    if response and response.tool_used and response.status == "completed"
                    else "failed"
                    if response and response.tool_used
                    else "not_selected"
                ),
                "outcome": outcome,
                "permission_decision": "allowed",
                "status": response.status if response else "failed",
                "error_category": response.error.code if response and response.error else None,
                "latency_ms": latency_ms,
                "result_type": (
                    response.result.type if response and response.result else None
                ),
                "normalized_leave_type": (
                    draft.leave_type_code if draft else
                    eligibility.leave_type_code if eligibility else None
                ),
                "normalized_start_date": (
                    draft.start_date.isoformat() if draft else
                    eligibility.start_date.isoformat() if eligibility else None
                ),
                "normalized_end_date": (
                    draft.end_date.isoformat() if draft else
                    eligibility.end_date.isoformat() if eligibility else None
                ),
                "eligibility_category": (
                    draft.eligibility_status if draft else
                    eligibility.eligibility_status if eligibility else None
                ),
                "balance_source": (
                    draft.balance_source if draft else
                    eligibility.balance_source if eligibility else None
                ),
                "blocking_reason_categories": (
                    [item.code for item in (
                        draft.blocking_reasons if draft
                        else eligibility.blocking_reasons if eligibility
                        else []
                    )]
                ),
                "draft_action": response.tool_used if draft else None,
                "draft_reference_hash": (
                    hashlib.sha256(draft.draft_id.encode()).hexdigest()[:16]
                    if draft else None
                ),
                "draft_status": draft.status if draft else None,
                "draft_version": draft.version if draft else None,
                "approver_resolution": draft.approver_resolution if draft else None,
            },
            source="ai",
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist Orbit AI audit event.")


def _audit_lifecycle(
    db: Session,
    request: Request,
    principal: AuthenticatedPrincipal,
    *,
    action: str,
    conversation_id: str,
    status: str,
) -> None:
    try:
        actor = db.query(Employee).filter(
            Employee.id == principal.employee_id
        ).first()
        log_audit(
            db,
            actor,
            action=f"ai.conversation.{action}",
            entity_type="ai_conversation",
            entity_id=conversation_id,
            reason=status,
            metadata={
                "owner_scope": "authenticated_principal",
                "conversation_status": status,
            },
            source="ai",
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist Orbit AI conversation audit event.")


def _conversation_or_404(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
):
    try:
        return get_owned_conversation(db, principal, conversation_id)
    except ConversationNotFound as exc:
        raise HTTPException(
            status_code=404, detail="Conversation not found."
        ) from exc


@router.post("/conversations", response_model=AIConversationSummary)
def start_conversation(
    _payload: AIConversationCreate,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> AIConversationSummary:
    conversation = create_conversation(db, principal)
    _audit_lifecycle(
        db,
        request,
        principal,
        action="create",
        conversation_id=conversation.id,
        status=conversation.status,
    )
    return conversation_summary(conversation)


@router.get("/conversations", response_model=AIConversationListResponse)
def conversation_history(
    include_archived: bool = True,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> AIConversationListResponse:
    return AIConversationListResponse(
        conversations=[
            conversation_summary(row)
            for row in list_conversations(
                db, principal, include_archived=include_archived
            )
        ]
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=AIConversationDetail,
)
def get_conversation(
    conversation_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> AIConversationDetail:
    conversation = _conversation_or_404(db, principal, conversation_id)
    detail = conversation_detail(db, principal, conversation)
    _audit_lifecycle(
        db,
        request,
        principal,
        action="open",
        conversation_id=conversation.id,
        status=conversation.status,
    )
    return detail


@router.post(
    "/conversations/{conversation_id}/close",
    response_model=AIConversationSummary,
)
def deactivate_conversation(
    conversation_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> AIConversationSummary:
    conversation = _conversation_or_404(db, principal, conversation_id)
    close_conversation(db, conversation)
    _audit_lifecycle(
        db,
        request,
        principal,
        action="close",
        conversation_id=conversation.id,
        status=conversation.status,
    )
    return conversation_summary(conversation)


@router.post(
    "/conversations/{conversation_id}/archive",
    response_model=AIConversationSummary,
)
def archive_owned_conversation(
    conversation_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> AIConversationSummary:
    conversation = _conversation_or_404(db, principal, conversation_id)
    archive_conversation(db, conversation)
    _audit_lifecycle(
        db,
        request,
        principal,
        action="archive",
        conversation_id=conversation.id,
        status=conversation.status,
    )
    return conversation_summary(conversation)


@router.post(
    "/conversations/{conversation_id}/restore",
    response_model=AIConversationDetail,
)
def restore_owned_conversation(
    conversation_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> AIConversationDetail:
    conversation = _conversation_or_404(db, principal, conversation_id)
    restore_conversation(db, conversation)
    detail = conversation_detail(db, principal, conversation)
    _audit_lifecycle(
        db,
        request,
        principal,
        action="restore",
        conversation_id=conversation.id,
        status=conversation.status,
    )
    return detail


@router.delete("/conversations/{conversation_id}")
def delete_owned_conversation(
    conversation_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    conversation = _conversation_or_404(db, principal, conversation_id)
    delete_conversation(db, conversation)
    _audit_lifecycle(
        db,
        request,
        principal,
        action="delete",
        conversation_id=conversation_id,
        status="deleted",
    )
    return {"deleted": True}


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    payload: AIChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> AIChatResponse:
    correlation_id = _correlation_id(request)
    request.state.correlation_id = correlation_id
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings.AI_CHAT_MAX_REQUEST_BYTES:
        _audit(
            db, request, principal, None, outcome="request_too_large",
            latency_ms=0, correlation_id=correlation_id,
        )
        raise _error(413, "REQUEST_TOO_LARGE", "The request is too large.", correlation_id)

    rate_key = principal.employee_id
    if not consume_ai_rate_limit(
        scope="ai_chat_minute",
        key=rate_key,
        limit=settings.AI_CHAT_REQUESTS_PER_MINUTE,
        window_seconds=60,
    ) or not consume_ai_rate_limit(
        scope="ai_chat_day",
        key=rate_key,
        limit=settings.AI_CHAT_REQUESTS_PER_DAY,
        window_seconds=86400,
    ):
        _audit(
            db, request, principal, None, outcome="rate_limited",
            latency_ms=0, correlation_id=correlation_id,
        )
        raise _error(429, "RATE_LIMITED", "Too many requests. Please try again later.", correlation_id)
    if not try_acquire_ai_slot(rate_key, maximum=2):
        _audit(
            db, request, principal, None, outcome="concurrency_limited",
            latency_ms=0, correlation_id=correlation_id,
        )
        raise _error(429, "CONCURRENCY_LIMITED", "Two Orbit AI requests are already running.", correlation_id)

    started = time.perf_counter()
    response: AIChatResponse | None = None
    conversation = None
    try:
        try:
            conversation = ensure_active_conversation(
                db, principal, payload.conversation_id
            )
        except ConversationNotFound as exc:
            raise _error(
                404,
                "CONVERSATION_NOT_FOUND",
                "Conversation not found.",
                correlation_id,
            ) from exc
        except ConversationNotActive as exc:
            raise _error(
                409,
                "CONVERSATION_NOT_ACTIVE",
                "Reopen this conversation before continuing it.",
                correlation_id,
            ) from exc
        append_message(
            db,
            conversation,
            role="user",
            content=payload.message,
        )
        response = await asyncio.wait_for(
            run_leave_balance_chat(
                db,
                principal,
                payload.message,
                conversation.id,
                correlation_id,
            ),
            timeout=settings.AI_CHAT_TIMEOUT_SECONDS,
        )
        if response.conversation_id != conversation.id:
            response = response.model_copy(
                update={"conversation_id": conversation.id}
            )
        completed_control_result = bool(
            response.result
            and response.result.type in {
                "leave_intake_summary",
                "leave_intake_cancelled",
            }
        )
        if response.status == "completed" and not completed_control_result and (
            response.tool_used not in AI_TOOLS or response.result is None
        ):
            logger.error("Grounding validation rejected an untooled leave response.")
            raise _error(
                502,
                "UNGROUNDED_RESPONSE_REJECTED",
                "Orbit AI could not produce a verified answer.",
                correlation_id,
            )
        if response.result and response.result.type == "leave_eligibility":
            if response.tool_used != "check_my_leave_eligibility":
                raise _error(
                    502,
                    "UNGROUNDED_RESPONSE_REJECTED",
                    "Orbit AI could not produce a verified eligibility answer.",
                    correlation_id,
                )
            eligibility = response.result.eligibility
            if (
                eligibility.eligibility_status == "eligible"
                and eligibility.blocking_reasons
            ):
                raise _error(
                    502,
                    "UNGROUNDED_RESPONSE_REJECTED",
                    "Orbit AI could not validate the eligibility result.",
                    correlation_id,
                )
        if response.result and response.result.type == "leave_request_draft":
            draft_tools = {
                "prepare_my_leave_request",
                "get_my_leave_request_draft",
                "update_my_leave_request_draft",
                "discard_my_leave_request_draft",
            }
            if response.tool_used not in draft_tools:
                raise _error(
                    502,
                    "UNGROUNDED_RESPONSE_REJECTED",
                    "Orbit AI could not validate the leave draft.",
                    correlation_id,
                )
            if response.result.draft.tool != response.tool_used:
                raise _error(
                    502,
                    "UNGROUNDED_RESPONSE_REJECTED",
                    "Orbit AI could not validate the leave draft action.",
                    correlation_id,
                )
        encoded_size = len(json.dumps(response.model_dump(mode="json")).encode("utf-8"))
        if encoded_size > settings.AI_CHAT_MAX_RESPONSE_BYTES:
            raise _error(502, "RESPONSE_TOO_LARGE", "The response could not be returned safely.", correlation_id)
        append_message(
            db,
            conversation,
            role="assistant",
            content=response.message.content,
            response=response,
        )
        update_conversation_from_response(db, conversation, response)
        if shadow_enabled():
            # The deterministic result is already complete and remains the
            # response. The background task opens its own session and can only
            # persist safe shadow-evaluation metadata.
            background_tasks.add_task(
                run_shadow_evaluation_background,
                principal,
                conversation_id=conversation.id,
                message=payload.message,
                correlation_id=correlation_id,
                deterministic_response_payload=response.model_dump(mode="json"),
            )
        return response
    except asyncio.TimeoutError:
        raise _error(504, "AI_TIMEOUT", "Orbit AI timed out. Please try again.", correlation_id)
    finally:
        release_ai_slot(rate_key)
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "orbit_ai_request correlation_id=%s actor_id=%s status=%s tool=%s latency_ms=%s",
            correlation_id,
            principal.employee_id,
            response.status if response else "failed",
            response.tool_used if response else "none",
            latency_ms,
        )
        _audit(
            db,
            request,
            principal,
            response,
            outcome=response.status if response else "timeout_or_error",
            latency_ms=latency_ms,
            correlation_id=correlation_id,
        )


@router.get(
    "/shadow-diagnostics",
    response_model=ShadowDiagnosticsResponse,
    include_in_schema=False,
)
def contextual_shadow_diagnostics(
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
) -> ShadowDiagnosticsResponse:
    """Development-only structured diagnostics aggregated for administrators."""
    if settings.APP_ENV.strip().lower() not in {"development", "dev", "test"}:
        raise HTTPException(status_code=404, detail="Not found.")
    if principal.role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Developer diagnostics are restricted.")
    return shadow_diagnostics(db, principal, limit=limit)


@router.get(
    "/shadow-provider-status",
    response_model=ContextualProviderStatusResponse,
)
def contextual_shadow_provider_status(
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: Session = Depends(get_db),
) -> ContextualProviderStatusResponse:
    """Safe admin-only configuration and recent shadow health metadata."""
    if principal.role not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=403,
            detail="Contextual provider status is restricted.",
        )
    return contextual_provider_status(db, principal)
