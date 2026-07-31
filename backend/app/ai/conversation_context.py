"""Short-lived, process-local references; never a source of business truth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from threading import Lock


@dataclass(frozen=True)
class ConversationReference:
    principal_id: str
    request_id: str
    expires_at: datetime


@dataclass(frozen=True)
class EligibilityReference:
    principal_id: str
    leave_type: str
    start_date: date
    end_date: date
    expires_at: datetime


@dataclass(frozen=True)
class DraftReference:
    principal_id: str
    draft_id: str
    version: int
    expires_at: datetime


_references: dict[str, ConversationReference] = {}
_eligibility_references: dict[str, EligibilityReference] = {}
_draft_references: dict[str, DraftReference] = {}
_lock = Lock()
_TTL = timedelta(minutes=15)


def remember_request(
    conversation_id: str, principal_id: str, request_id: str
) -> None:
    with _lock:
        _references[conversation_id] = ConversationReference(
            principal_id=principal_id,
            request_id=request_id,
            expires_at=datetime.now(timezone.utc) + _TTL,
        )


def resolve_request_reference(
    conversation_id: str | None, principal_id: str
) -> str | None:
    if not conversation_id:
        return None
    with _lock:
        reference = _references.get(conversation_id)
        if not reference:
            return None
        if (
            reference.principal_id != principal_id
            or reference.expires_at <= datetime.now(timezone.utc)
        ):
            _references.pop(conversation_id, None)
            return None
        return reference.request_id


def remember_eligibility(
    conversation_id: str,
    principal_id: str,
    leave_type: str,
    start_date: date,
    end_date: date,
) -> None:
    with _lock:
        _eligibility_references[conversation_id] = EligibilityReference(
            principal_id=principal_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            expires_at=datetime.now(timezone.utc) + _TTL,
        )


def resolve_eligibility_reference(
    conversation_id: str | None, principal_id: str
) -> EligibilityReference | None:
    if not conversation_id:
        return None
    with _lock:
        reference = _eligibility_references.get(conversation_id)
        if not reference:
            return None
        if (
            reference.principal_id != principal_id
            or reference.expires_at <= datetime.now(timezone.utc)
        ):
            _eligibility_references.pop(conversation_id, None)
            return None
        return reference


def remember_draft(
    conversation_id: str, principal_id: str, draft_id: str, version: int
) -> None:
    with _lock:
        _draft_references[conversation_id] = DraftReference(
            principal_id=principal_id,
            draft_id=draft_id,
            version=version,
            expires_at=datetime.now(timezone.utc) + _TTL,
        )


def resolve_draft_reference(
    conversation_id: str | None, principal_id: str
) -> DraftReference | None:
    if not conversation_id:
        return None
    with _lock:
        reference = _draft_references.get(conversation_id)
        if not reference:
            return None
        if (
            reference.principal_id != principal_id
            or reference.expires_at <= datetime.now(timezone.utc)
        ):
            _draft_references.pop(conversation_id, None)
            return None
        return reference


def reset_conversation_context_for_tests() -> None:
    with _lock:
        _references.clear()
        _eligibility_references.clear()
        _draft_references.clear()
