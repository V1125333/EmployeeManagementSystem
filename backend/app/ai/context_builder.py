"""Build the bounded, redacted, read-only context used by shadow interpretation."""

from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.contextual_schemas import (
    ActiveWorkflowContext,
    CapabilityDescription,
    ContextMessage,
    ContextPackage,
    SafeCollectedFields,
)
from app.core.authentication import AuthenticatedPrincipal
from app.core.config import settings
from app.models.ai_workflow import (
    AIConversationMessage,
    AILeaveIntakeState,
    AILeaveRequestDraft,
)
from app.models.employee import Employee
from app.services.leave_eligibility_service import local_now


_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_HEADER = re.compile(
    r"\b(?:authorization|x-user-id|x-user-email|cookie)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def redact_context_text(value: str, *, limit: int = 1000) -> str:
    text = _BEARER.sub("[REDACTED_TOKEN]", value)
    text = _HEADER.sub("[REDACTED_HEADER]", text)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _UUID.sub("[REDACTED_REFERENCE]", text)
    return " ".join(text.strip().split())[:limit]


CAPABILITY_DESCRIPTIONS = (
    CapabilityDescription(
        capability_id="start_leave_intake",
        description="Recognize starting leave intake; observation only.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="continue_leave_intake",
        description="Continue the current leave intake with validated fields.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="update_leave_intake_dates",
        description="Recognize a date correction in active leave intake.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="update_leave_intake_type",
        description="Recognize a leave-type correction in active intake.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="resume_leave_intake",
        description="Recognize returning to a paused leave intake.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="request_leave_submission",
        description="Recognize submission intent; unavailable in Phase A.",
        risk="confirmation_only",
    ),
    CapabilityDescription(
        capability_id="leave.balance.read_self",
        description="Read the signed-in employee's own leave balances.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.balance.compare_self",
        description="Compare the signed-in employee's own leave balances.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.requests.list_self",
        description="List the signed-in employee's own leave requests.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.request.status_self",
        description="Read one owner-scoped leave request status.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.request.details_self",
        description="Read one owner-scoped leave request's details.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.request.decision_explain_self",
        description="Explain a recorded owner-scoped leave decision.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.eligibility.check_self",
        description="Assess the employee's own proposed leave against current rules.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.draft.prepare_self",
        description="Prepare an AI-only leave draft; never submit it.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="leave.draft.read_self",
        description="Read the current owner-scoped AI leave draft.",
        risk="read",
    ),
    CapabilityDescription(
        capability_id="leave.draft.update_self",
        description="Propose updating the current owner-scoped AI leave draft.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="leave.draft.discard_self",
        description="Propose discarding the current owner-scoped AI leave draft.",
        risk="prepare",
    ),
    CapabilityDescription(
        capability_id="leave.request.submit_confirmed_self",
        description="Recognize a submission request; unavailable for execution in Phase A.",
        risk="confirmation_only",
    ),
)


def _json_list(value: str | None) -> list[str]:
    try:
        loaded = json.loads(value or "[]")
        return [str(item)[:50] for item in loaded] if isinstance(loaded, list) else []
    except (TypeError, ValueError):
        return []


def _intake_context(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
    now: datetime,
) -> ActiveWorkflowContext | None:
    row = db.query(AILeaveIntakeState).filter(
        AILeaveIntakeState.owner_employee_id == principal.employee_id,
        AILeaveIntakeState.conversation_id == conversation_id,
        AILeaveIntakeState.expires_at > now.replace(tzinfo=None),
    ).first()
    if not row:
        return None
    try:
        fields = json.loads(row.collected_fields or "{}")
    except (TypeError, ValueError):
        fields = {}
    return ActiveWorkflowContext(
        workflow_type="leave_intake",
        stage="collecting_information",
        collected_fields=SafeCollectedFields(
            leave_type=fields.get("leave_type"),
            start_date=fields.get("start_date"),
            end_date=fields.get("end_date"),
            duration_days=fields.get("duration_days"),
            reason_present=bool(fields.get("reason")),
            reason_skipped=bool(fields.get("reason_skipped")),
            supporting_information_present=bool(
                fields.get("supporting_information")
            ),
        ),
        missing_fields=_json_list(row.missing_required_fields),
        optional_fields=_json_list(row.optional_fields),
        expires_at=row.expires_at,
    )


def _draft_context(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
    now: datetime,
) -> ActiveWorkflowContext | None:
    row = db.query(AILeaveRequestDraft).filter(
        AILeaveRequestDraft.owner_employee_id == principal.employee_id,
        AILeaveRequestDraft.conversation_id == conversation_id,
        AILeaveRequestDraft.status.notin_(["discarded", "expired", "submitted", "completed"]),
        AILeaveRequestDraft.expires_at > now.replace(tzinfo=None),
    ).order_by(AILeaveRequestDraft.updated_at.desc()).first()
    if not row:
        return None
    return ActiveWorkflowContext(
        workflow_type="leave_draft",
        stage=row.status,
        collected_fields=SafeCollectedFields(
            leave_type=row.leave_type_code,
            start_date=row.start_date,
            end_date=row.end_date,
            reason_present=bool(row.reason),
        ),
        version=row.version,
        expires_at=row.expires_at,
    )


def _recent_messages(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
    *,
    current_message: str,
    correlation_id: str,
) -> list[ContextMessage]:
    rows = db.query(AIConversationMessage).filter(
        AIConversationMessage.owner_employee_id == principal.employee_id,
        AIConversationMessage.conversation_id == conversation_id,
    ).order_by(AIConversationMessage.created_at.desc()).limit(10).all()
    rows.reverse()
    if rows and rows[-1].role == "assistant" and rows[-1].correlation_id == correlation_id:
        rows.pop()
    if rows and rows[-1].role == "user" and rows[-1].content.strip() == current_message.strip():
        rows.pop()
    return [
        ContextMessage(
            role=row.role,
            content=redact_context_text(row.content),
        )
        for row in rows[-8:]
        if row.role in {"user", "assistant"} and row.content.strip()
    ]


def build_context_package(
    db: Session,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
    *,
    current_message: str,
    correlation_id: str,
) -> ContextPackage:
    employee = db.query(Employee).filter(
        Employee.id == principal.employee_id
    ).first()
    if employee:
        trusted_now, timezone_name = local_now(db, employee)
    else:
        trusted_now, timezone_name = datetime.utcnow(), "UTC"
    workflow = (
        _intake_context(db, principal, conversation_id, trusted_now)
        or _draft_context(db, principal, conversation_id, trusted_now)
        or ActiveWorkflowContext(workflow_type="none", stage="none")
    )
    return ContextPackage(
        prompt_version=settings.CONTEXTUAL_LLM_PROMPT_VERSION,
        active_workflow=workflow,
        recent_messages=_recent_messages(
            db,
            principal,
            conversation_id,
            current_message=current_message,
            correlation_id=correlation_id,
        ),
        trusted_date=trusted_now.date(),
        timezone=timezone_name,
        approved_capabilities=list(CAPABILITY_DESCRIPTIONS),
    )
