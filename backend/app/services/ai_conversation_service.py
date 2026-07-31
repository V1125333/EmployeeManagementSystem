"""Secure principal-scoped persistence for Orbit AI conversations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.ai.conversation_context import remember_draft, remember_request
from app.core.authentication import AuthenticatedPrincipal
from app.core.config import settings
from app.models.ai_workflow import (
    AIConversation,
    AIConversationMessage,
    AILeaveRequestDraft,
)
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest
from app.schemas.ai import (
    AIChatResponse,
    AIConversationDetail,
    AIConversationMessageOutput,
    AIConversationSummary,
    AIConversationWorkflowState,
)
from app.services.leave_draft_service import (
    LeaveDraftError,
    get_my_leave_request_draft,
)

MAX_STORED_MESSAGE_CHARS = 8_000
TERMINAL_DRAFT_STATUSES = {"expired", "discarded", "submitted", "completed"}


class ConversationNotFound(Exception):
    """Intentionally does not reveal whether another owner has the ID."""


class ConversationNotActive(Exception):
    pass


def _now() -> datetime:
    return datetime.utcnow()


def _retention_expiry() -> datetime:
    days = max(1, min(settings.AI_CONVERSATION_RETENTION_DAYS, 365))
    return _now() + timedelta(days=days)


def _owner_query(db: Session, principal: AuthenticatedPrincipal):
    return db.query(AIConversation).filter(
        AIConversation.owner_employee_id == principal.employee_id,
        AIConversation.deleted_at.is_(None),
        AIConversation.retention_expires_at > _now(),
    )


def expire_retained_conversations(
    db: Session, principal: AuthenticatedPrincipal
) -> None:
    expired = db.query(AIConversation).filter(
        AIConversation.owner_employee_id == principal.employee_id,
        AIConversation.deleted_at.is_(None),
        AIConversation.retention_expires_at <= _now(),
    ).all()
    for conversation in expired:
        db.query(AIConversationMessage).filter(
            AIConversationMessage.conversation_id == conversation.id,
            AIConversationMessage.owner_employee_id == principal.employee_id,
        ).delete(synchronize_session=False)
        conversation.status = "deleted"
        conversation.deleted_at = _now()
        conversation.title = "Expired Orbit AI conversation"
        conversation.workflow_reference_id = None
    if expired:
        db.commit()


def create_conversation(
    db: Session, principal: AuthenticatedPrincipal
) -> AIConversation:
    row = AIConversation(
        owner_employee_id=principal.employee_id,
        title="New Orbit AI conversation",
        domain="leave",
        status="active",
        retention_expires_at=_retention_expiry(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_owned_conversation(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
    *,
    require_active: bool = False,
) -> AIConversation:
    expire_retained_conversations(db, principal)
    row = _owner_query(db, principal).filter(
        AIConversation.id == conversation_id
    ).first()
    if not row:
        raise ConversationNotFound
    if require_active and row.status != "active":
        raise ConversationNotActive
    return row


def ensure_active_conversation(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation_id: str | None,
) -> AIConversation:
    if not conversation_id:
        return create_conversation(db, principal)
    return get_owned_conversation(
        db, principal, conversation_id, require_active=True
    )


def list_conversations(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    include_archived: bool = True,
) -> list[AIConversation]:
    expire_retained_conversations(db, principal)
    query = _owner_query(db, principal)
    if not include_archived:
        query = query.filter(AIConversation.status != "archived")
    return query.order_by(
        AIConversation.updated_at.desc(), AIConversation.created_at.desc()
    ).limit(max(1, min(settings.AI_CONVERSATION_HISTORY_LIMIT, 100))).all()


def append_message(
    db: Session,
    conversation: AIConversation,
    *,
    role: str,
    content: str,
    response: AIChatResponse | None = None,
) -> AIConversationMessage:
    safe_content = content.strip()[:MAX_STORED_MESSAGE_CHARS]
    result_type = (
        response.result.type if response and response.result is not None else None
    )
    row = AIConversationMessage(
        conversation_id=conversation.id,
        owner_employee_id=conversation.owner_employee_id,
        role=role,
        content=safe_content,
        response_status=response.status if response else None,
        result_type=result_type,
        tool_name=response.tool_used if response else None,
        correlation_id=response.correlation_id if response else None,
    )
    now = _now()
    conversation.message_count = (conversation.message_count or 0) + 1
    conversation.last_message_at = now
    conversation.updated_at = now
    conversation.retention_expires_at = _retention_expiry()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _date_title(value) -> str:
    return f"{value.strftime('%b')} {value.day}" if hasattr(value, "strftime") else ""


def _deterministic_title(response: AIChatResponse) -> tuple[str, str | None]:
    result = response.result
    if not result:
        return "Orbit AI Conversation", response.tool_used
    if result.type == "leave_balance":
        if len(result.balances) == 1:
            return f"{result.balances[0].leave_type} Balance", result.type
        return "Leave Balance", result.type
    if result.type == "leave_balance_comparison":
        return "Leave Balance Comparison", result.type
    if result.type == "leave_request_list":
        return "Leave Request History", result.type
    if result.type in {"leave_request_status", "rejection_explanation"}:
        request = result.request
        return f"{request.status.title()} Leave Status", result.type
    if result.type == "leave_request_draft":
        draft = result.draft
        date_label = _date_title(draft.start_date)
        return (
            f"Prepare {draft.leave_type}{f' — {date_label}' if date_label else ''}",
            result.type,
        )
    if result.type.startswith("leave_intake"):
        intake = getattr(result, "intake", None)
        leave_type = (
            intake.collected_fields.leave_type if intake is not None else None
        )
        start_date = (
            intake.collected_fields.start_date if intake is not None else None
        )
        suffix = f" — {_date_title(start_date)}" if start_date else ""
        return f"Prepare {leave_type or 'Leave Request'}{suffix}", result.type
    if result.type == "leave_eligibility":
        return (
            f"{result.eligibility.leave_type} Eligibility",
            result.type,
        )
    return result.title[:160], result.type


def update_conversation_from_response(
    db: Session,
    conversation: AIConversation,
    response: AIChatResponse,
) -> None:
    title, capability = _deterministic_title(response)
    conversation.title = title[:160]
    conversation.capability = capability
    result = response.result
    if result and result.type == "leave_request_draft":
        conversation.workflow_kind = "leave_request_draft"
        conversation.workflow_reference_id = result.draft.draft_id
        conversation.workflow_status = result.draft.status
    elif result and result.type in {
        "leave_request_status",
        "rejection_explanation",
    }:
        conversation.workflow_kind = "leave_request"
        conversation.workflow_reference_id = result.request.request_id
        conversation.workflow_status = result.request.status
    db.commit()


def close_conversation(db: Session, conversation: AIConversation) -> None:
    if conversation.status == "active":
        conversation.status = "closed"
        conversation.updated_at = _now()
        db.commit()


def archive_conversation(db: Session, conversation: AIConversation) -> None:
    conversation.status = "archived"
    conversation.archived_at = _now()
    conversation.updated_at = _now()
    db.commit()


def restore_conversation(db: Session, conversation: AIConversation) -> None:
    conversation.status = "active"
    conversation.archived_at = None
    conversation.updated_at = _now()
    conversation.retention_expires_at = _retention_expiry()
    db.commit()


def delete_conversation(db: Session, conversation: AIConversation) -> None:
    db.query(AIConversationMessage).filter(
        AIConversationMessage.conversation_id == conversation.id,
        AIConversationMessage.owner_employee_id == conversation.owner_employee_id,
    ).delete(synchronize_session=False)
    conversation.status = "deleted"
    conversation.deleted_at = _now()
    conversation.title = "Deleted Orbit AI conversation"
    conversation.capability = None
    conversation.workflow_kind = None
    conversation.workflow_reference_id = None
    conversation.workflow_status = None
    conversation.message_count = 0
    conversation.updated_at = _now()
    db.commit()


def _summary(row: AIConversation) -> AIConversationSummary:
    return AIConversationSummary(
        id=row.id,
        title=row.title,
        domain=row.domain,
        capability=row.capability,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_message_at=row.last_message_at,
        message_count=row.message_count,
        workflow_status=row.workflow_status,
    )


def conversation_summary(row: AIConversation) -> AIConversationSummary:
    return _summary(row)


def _workflow_display(status: str) -> str:
    normalized = (status or "").lower()
    if normalized == "expired":
        return "expired"
    if normalized == "discarded":
        return "discarded"
    if normalized in {"submitted", "completed", "approved"}:
        return "completed"
    if normalized in {"cancelled", "withdrawn", "rejected"}:
        return "cancelled"
    return "active" if normalized else "unknown"


def _refresh_workflow(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation: AIConversation,
) -> AIConversationWorkflowState | None:
    now = _now()
    if (
        conversation.workflow_kind == "leave_request_draft"
        and conversation.workflow_reference_id
    ):
        draft = db.query(AILeaveRequestDraft).filter(
            AILeaveRequestDraft.id == conversation.workflow_reference_id,
            AILeaveRequestDraft.owner_employee_id == principal.employee_id,
        ).first()
        if not draft:
            return AIConversationWorkflowState(
                kind="leave_request_draft",
                status="missing",
                display_status="unknown",
                message="The referenced leave draft is no longer available.",
                refreshed_at=now,
            )
        status = draft.status
        if status not in TERMINAL_DRAFT_STATUSES and draft.expires_at <= now:
            status = "expired"
            draft.status = status
            draft.updated_at = now
            db.commit()
        conversation.workflow_status = status
        db.commit()
        if status not in TERMINAL_DRAFT_STATUSES:
            employee = db.query(Employee).filter(
                Employee.id == principal.employee_id
            ).first()
            if employee:
                try:
                    refreshed = get_my_leave_request_draft(
                        db,
                        employee,
                        conversation_id=conversation.id,
                        draft_id=draft.id,
                    )
                    conversation.workflow_status = refreshed.status
                    remember_draft(
                        conversation.id,
                        principal.employee_id,
                        refreshed.draft_id,
                        refreshed.version,
                    )
                    db.commit()
                    status = refreshed.status
                except LeaveDraftError:
                    status = draft.status
        display = _workflow_display(status)
        messages = {
            "expired": "This leave draft has expired. Start a new draft to continue.",
            "discarded": "This leave draft was discarded.",
            "completed": "This leave workflow is completed and cannot be edited here.",
        }
        return AIConversationWorkflowState(
            kind="leave_request_draft",
            status=status,
            display_status=display,
            message=messages.get(
                display,
                "The leave draft was refreshed from the current workflow record.",
            ),
            refreshed_at=now,
        )
    if (
        conversation.workflow_kind == "leave_request"
        and conversation.workflow_reference_id
    ):
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == conversation.workflow_reference_id,
            LeaveRequest.employee_id == principal.employee_id,
        ).first()
        if not leave_request:
            return AIConversationWorkflowState(
                kind="leave_request",
                status="missing",
                display_status="unknown",
                message="The referenced leave request is no longer available.",
                refreshed_at=now,
            )
        status = leave_request.status
        conversation.workflow_status = status
        db.commit()
        remember_request(
            conversation.id, principal.employee_id, leave_request.id
        )
        return AIConversationWorkflowState(
            kind="leave_request",
            status=status,
            display_status=_workflow_display(status),
            message="The leave request status was refreshed from the official record.",
            refreshed_at=now,
        )
    return None


def conversation_detail(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation: AIConversation,
) -> AIConversationDetail:
    workflow = _refresh_workflow(db, principal, conversation)
    rows: Iterable[AIConversationMessage] = db.query(
        AIConversationMessage
    ).filter(
        AIConversationMessage.conversation_id == conversation.id,
        AIConversationMessage.owner_employee_id == principal.employee_id,
    ).order_by(AIConversationMessage.created_at.asc()).limit(200).all()
    messages = [
        AIConversationMessageOutput(
            id=row.id,
            role=row.role,
            content=row.content,
            response_status=row.response_status,
            result_type=row.result_type,
            correlation_id=row.correlation_id,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return AIConversationDetail(
        conversation=_summary(conversation),
        messages=messages,
        workflow=workflow,
    )
