"""Durable, principal-bound conversational leave intake state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.ai_workflow import AILeaveIntakeState
from app.schemas.ai import LeaveIntakeCollectedFields, LeaveIntakeStateOutput


INTAKE_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class LeaveIntakeRequirements:
    reason_required: bool = False
    supporting_information_required: bool = False


@dataclass
class LeaveIntakeError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def get_leave_intake_requirements(
    _db: Session,
    _leave_type: str | None,
) -> LeaveIntakeRequirements:
    """Return current backend policy requirements.

    The current LeaveType schema has no reason/attachment requirement fields,
    and Phase 3 draft preparation permits an omitted reason. Keep those
    existing rules instead of inventing policy in the AI layer.
    """
    return LeaveIntakeRequirements()


def _now() -> datetime:
    return datetime.utcnow()


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _load_fields(row: AILeaveIntakeState) -> LeaveIntakeCollectedFields:
    return LeaveIntakeCollectedFields.model_validate(
        json.loads(row.collected_fields or "{}")
    )


def _state(row: AILeaveIntakeState) -> LeaveIntakeStateOutput:
    return LeaveIntakeStateOutput(
        goal="prepare_leave_request",
        collected_fields=_load_fields(row),
        missing_required_fields=json.loads(row.missing_required_fields or "[]"),
        optional_fields=json.loads(row.optional_fields or "[]"),
        source_confidence=json.loads(row.source_confidence or "{}"),
        conversation_id=row.conversation_id,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def _missing_and_optional(
    fields: LeaveIntakeCollectedFields,
    requirements: LeaveIntakeRequirements,
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    # Dates come first because the conversational flow asks one focused
    # question at a time in the order requested by the product.
    if not fields.start_date or not fields.end_date:
        missing.append("date_range")
    if not fields.leave_type:
        missing.append("leave_type")
    if requirements.reason_required and not fields.reason:
        missing.append("reason")
    if (
        requirements.supporting_information_required
        and not fields.supporting_information
    ):
        missing.append("supporting_information")

    optional: list[str] = []
    if (
        not requirements.reason_required
        and not fields.reason
        and not fields.reason_skipped
    ):
        optional.append("reason")
    if not requirements.supporting_information_required:
        optional.append("supporting_information")
    return missing, optional


def get_leave_intake(
    db: Session,
    owner_employee_id: str,
    conversation_id: str | None,
) -> AILeaveIntakeState | None:
    if not conversation_id:
        return None
    row = db.query(AILeaveIntakeState).filter(
        AILeaveIntakeState.owner_employee_id == owner_employee_id,
        AILeaveIntakeState.conversation_id == conversation_id,
    ).first()
    if not row:
        return None
    if row.expires_at <= _now():
        db.delete(row)
        db.commit()
        raise LeaveIntakeError(
            "INTAKE_EXPIRED",
            "That leave intake expired. Please start the request again.",
        )
    return row


def save_leave_intake(
    db: Session,
    owner_employee_id: str,
    conversation_id: str,
    fields: LeaveIntakeCollectedFields,
    source_confidence: dict[str, str],
    requirements: LeaveIntakeRequirements,
) -> LeaveIntakeStateOutput:
    row = db.query(AILeaveIntakeState).filter(
        AILeaveIntakeState.owner_employee_id == owner_employee_id,
        AILeaveIntakeState.conversation_id == conversation_id,
    ).with_for_update().first()
    now = _now()
    missing, optional = _missing_and_optional(fields, requirements)
    if not row:
        row = AILeaveIntakeState(
            owner_employee_id=owner_employee_id,
            conversation_id=conversation_id,
            goal="prepare_leave_request",
            created_at=now,
        )
        db.add(row)
    row.collected_fields = _json(fields.model_dump(mode="json"))
    row.missing_required_fields = _json(missing)
    row.optional_fields = _json(optional)
    row.source_confidence = _json(source_confidence)
    row.expires_at = now + INTAKE_TTL
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return _state(row)


def intake_state(row: AILeaveIntakeState) -> LeaveIntakeStateOutput:
    return _state(row)


def clear_leave_intake(
    db: Session,
    owner_employee_id: str,
    conversation_id: str | None,
) -> bool:
    if not conversation_id:
        return False
    deleted = db.query(AILeaveIntakeState).filter(
        AILeaveIntakeState.owner_employee_id == owner_employee_id,
        AILeaveIntakeState.conversation_id == conversation_id,
    ).delete(synchronize_session=False)
    db.commit()
    return bool(deleted)
