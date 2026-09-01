from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.authentication import AuthenticatedActor, get_authenticated_actor
from app.core.config import settings
from app.core.database import get_db
from app.schemas.orbit import OrbitChatRequest, OrbitChatResponse
from app.services.ai_conversation_service import (
    ConversationNotActive,
    ConversationNotFound,
    append_message,
    ensure_active_conversation,
    list_recent_messages,
    update_last_resolved_intent,
)
from app.services.orbit_agent.hermes_client import (
    HermesClient,
    HermesClientError,
    get_hermes_client,
)
from app.services.orbit_agent.orbit_capabilities import (
    OrbitExecutor,
    OrbitIntent,
    get_orbit_capability,
)
from app.services.orbit_agent.orbit_classifier import (
    OrbitContextMessage,
    classify_orbit_message,
    orbit_classifier_confidence_threshold,
)
from app.services.orbit_agent.orbit_attendance_executor import execute_attendance_read
from app.services.orbit_agent.orbit_employee_executor import execute_employee_read
from app.services.orbit_agent.orbit_leave_executor import execute_leave_read
from app.services.orbit_agent.orbit_timesheet_executor import execute_timesheet_read
from app.services.orbit_agent.orbit_router import route_orbit_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orbit", tags=["Orbit AI"])


def _correlation_id(request: Request) -> str:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    return str(correlation_id)[:120]


def _error(status_code: int, code: str, message: str, correlation_id: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        },
    )


def _log_route(
    *,
    source: str,
    intent: OrbitIntent,
    executor: OrbitExecutor,
    confidence: float,
    correlation_id: str,
    conversation_id: str,
    context_message_count: int,
    context_followup_resolved: bool = False,
) -> None:
    logger.debug(
        "orbit_route_source=%s orbit_intent=%s orbit_executor=%s orbit_confidence=%s correlation_id=%s conversation_id=%s context_message_count=%s context_followup_resolved=%s",
        source,
        intent.value,
        executor.value,
        confidence,
        correlation_id,
        conversation_id,
        context_message_count,
        context_followup_resolved,
    )


def _disabled_capability_response(intent: OrbitIntent) -> str | None:
    capability = get_orbit_capability(intent)
    if capability is None or capability.enabled:
        return None
    return capability.unavailable_message


def _meaningful_intent(intent: OrbitIntent) -> bool:
    return intent in {
        OrbitIntent.EMS_LEAVE,
        OrbitIntent.EMS_ATTENDANCE,
        OrbitIntent.EMS_TIMESHEET,
        OrbitIntent.EMS_ALLOCATION,
        OrbitIntent.EMS_EMPLOYEE,
        OrbitIntent.DRAFTING,
        OrbitIntent.GENERAL_REASONING,
    }


def _recent_context_messages(rows: list) -> list[OrbitContextMessage]:
    return [
        OrbitContextMessage(role=row.role, content=row.content)
        for row in rows
        if row.role in {"user", "assistant"} and row.content.strip()
    ]


def _recent_hermes_history(rows: list) -> list[dict[str, str]]:
    return [
        {"role": row.role, "content": row.content}
        for row in rows
        if row.role in {"user", "assistant"} and row.content.strip()
    ]


def _resolved_followup_intent(
    classified_intent: OrbitIntent,
    *,
    previous_intent: OrbitIntent | None,
) -> tuple[OrbitIntent, bool]:
    if classified_intent is not OrbitIntent.CONTEXT_FOLLOWUP:
        return classified_intent, False
    if previous_intent and _meaningful_intent(previous_intent):
        return previous_intent, True
    return classified_intent, False


async def _execute_ems_tool(
    *,
    intent: OrbitIntent,
    db: Session,
    actor: AuthenticatedActor,
    query: str,
    context_rows: list[OrbitContextMessage],
    request: Request,
) -> str | None:
    handlers = {
        OrbitIntent.EMS_LEAVE: lambda: execute_leave_read(
            db=db,
            actor=actor,
            query=query,
            conversation_context=context_rows,
            request=request,
        ),
        OrbitIntent.EMS_ATTENDANCE: lambda: execute_attendance_read(
            db=db,
            actor=actor,
            query=query,
            recent_context=context_rows,
            request=request,
        ),
        OrbitIntent.EMS_EMPLOYEE: lambda: execute_employee_read(
            db=db,
            actor=actor,
            query=query,
            recent_context=context_rows,
            request=request,
        ),
        OrbitIntent.EMS_TIMESHEET: lambda: execute_timesheet_read(
            db=db,
            actor=actor,
            query=query,
            recent_context=context_rows,
            request=request,
        ),
    }
    handler = handlers.get(intent)
    if handler is None:
        return None
    return (await handler()).message


@router.post("/chat", response_model=OrbitChatResponse)
async def orbit_chat(
    payload: OrbitChatRequest,
    request: Request,
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
    hermes: HermesClient = Depends(get_hermes_client),
    db: Session = Depends(get_db),
) -> OrbitChatResponse:
    correlation_id = _correlation_id(request)
    try:
        conversation = ensure_active_conversation(
            db,
            actor.principal,
            str(payload.conversation_id) if payload.conversation_id else None,
            title="Orbit AI conversation",
            domain="orbit",
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

    try:
        context_rows = list_recent_messages(
            db,
            actor.principal,
            conversation,
            limit=settings.ORBIT_CONTEXT_MAX_MESSAGES,
        )
    except Exception:
        logger.warning(
            "Orbit context load failed correlation_id=%s conversation_id=%s",
            correlation_id,
            conversation.id,
        )
        context_rows = []
    context_count = len(context_rows)
    route_result = route_orbit_message(payload.message, actor)
    if route_result.handled and route_result.message:
        append_message(db, conversation, role="user", content=payload.message)
        append_message(db, conversation, role="assistant", content=route_result.message)
        _log_route(
            source="deterministic",
            intent=route_result.intent,
            executor=route_result.executor,
            confidence=route_result.confidence,
            correlation_id=correlation_id,
            conversation_id=conversation.id,
            context_message_count=context_count,
        )
        return OrbitChatResponse(message=route_result.message, conversation_id=conversation.id)

    classification = await classify_orbit_message(
        payload.message,
        recent_context=_recent_context_messages(context_rows),
    )
    previous_intent = None
    if conversation.last_resolved_intent:
        try:
            previous_intent = OrbitIntent(conversation.last_resolved_intent)
        except ValueError:
            previous_intent = None
    resolved_intent, followup_resolved = _resolved_followup_intent(
        classification.intent,
        previous_intent=previous_intent,
    )
    threshold = orbit_classifier_confidence_threshold()
    if classification.confidence >= threshold:
        capability = get_orbit_capability(resolved_intent)
        if (
            capability is not None
            and capability.enabled
            and capability.executor is OrbitExecutor.EMS_TOOL
        ):
            ems_result_message = await _execute_ems_tool(
                intent=resolved_intent,
                db=db,
                actor=actor,
                query=payload.message,
                context_rows=_recent_context_messages(context_rows),
                request=request,
            )

            if ems_result_message is not None:
                append_message(db, conversation, role="user", content=payload.message)
                append_message(db, conversation, role="assistant", content=ems_result_message)
                if _meaningful_intent(resolved_intent):
                    update_last_resolved_intent(db, conversation, resolved_intent.value)
                _log_route(
                    source="ems_tool",
                    intent=resolved_intent,
                    executor=capability.executor,
                    confidence=classification.confidence,
                    correlation_id=correlation_id,
                    conversation_id=conversation.id,
                    context_message_count=context_count,
                    context_followup_resolved=followup_resolved,
                )
                return OrbitChatResponse(message=ems_result_message, conversation_id=conversation.id)

        unavailable_message = _disabled_capability_response(resolved_intent)
        if unavailable_message:
            append_message(db, conversation, role="user", content=payload.message)
            append_message(db, conversation, role="assistant", content=unavailable_message)
            if _meaningful_intent(resolved_intent):
                update_last_resolved_intent(db, conversation, resolved_intent.value)
            _log_route(
                source="classifier",
                intent=resolved_intent,
                executor=capability.executor if capability else OrbitExecutor.LOCAL,
                confidence=classification.confidence,
                correlation_id=correlation_id,
                conversation_id=conversation.id,
                context_message_count=context_count,
                context_followup_resolved=followup_resolved,
            )
            return OrbitChatResponse(message=unavailable_message, conversation_id=conversation.id)

    _log_route(
        source="hermes_fallback",
        intent=resolved_intent,
        executor=OrbitExecutor.HERMES,
        confidence=classification.confidence,
        correlation_id=correlation_id,
        conversation_id=conversation.id,
        context_message_count=context_count,
        context_followup_resolved=followup_resolved,
    )
    try:
        assistant_message = await hermes.chat(
            payload.message,
            history=_recent_hermes_history(context_rows),
        )
    except HermesClientError as exc:
        logger.warning(
            "Orbit Hermes chat failed status=%s correlation_id=%s",
            exc.status_code,
            correlation_id,
        )
        code = (
            "ORBIT_AI_TIMEOUT"
            if exc.status_code == 504
            else "ORBIT_AI_UNAVAILABLE"
        )
        raise _error(exc.status_code, code, exc.message, correlation_id) from exc

    append_message(db, conversation, role="user", content=payload.message)
    append_message(db, conversation, role="assistant", content=assistant_message)
    if _meaningful_intent(resolved_intent):
        update_last_resolved_intent(db, conversation, resolved_intent.value)

    return OrbitChatResponse(message=assistant_message, conversation_id=conversation.id)
