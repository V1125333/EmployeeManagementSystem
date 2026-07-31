"""Durable, owner-scoped AI leave preparation without official submission."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.ai_workflow import AILeaveRequestDraft
from app.models.employee import Employee
from app.models.leave_attendance import LeaveType
from app.schemas.ai import (
    CheckMyLeaveEligibilityOutput,
    LeaveEligibilityIssue,
    LeaveRequestDraftOutput,
)
from app.services.leave_approver_service import (
    LeaveApproverResolution,
    ResolvedLeaveApprover,
    resolve_leave_approver_with_reason,
)
from app.services.leave_eligibility_service import check_my_leave_eligibility
from app.services.leave_service import (
    LeaveServiceError,
    normalize_leave_reason,
    resolve_leave_type_reference,
)


DRAFT_TTL = timedelta(minutes=30)
TERMINAL_STATUSES = {"discarded", "expired"}


@dataclass
class LeaveDraftError(Exception):
    code: str
    message: str
    details: dict | None = None

    def __str__(self) -> str:
        return self.message


def validate_leave_reason(reason: str | None) -> str | None:
    try:
        return normalize_leave_reason(reason, required=False)
    except LeaveServiceError as exc:
        raise LeaveDraftError("INVALID_REASON", exc.message) from exc


def _now() -> datetime:
    return datetime.utcnow()


def _hash_payload(
    *,
    owner_id: str,
    leave_type_id: str,
    start_date: date,
    end_date: date,
    reason: str | None,
    version: int,
) -> str:
    canonical = json.dumps(
        {
            "owner": owner_id,
            "capability": "leave_request",
            "leave_type": leave_type_id,
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "reason": reason,
            "version": version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _status(eligibility: CheckMyLeaveEligibilityOutput, has_approver: bool) -> str:
    if eligibility.eligibility_status == "not_eligible":
        return "not_eligible"
    if eligibility.eligibility_status == "requires_information" or not has_approver:
        return "requires_information"
    return "ready_for_review"


def _approver_issue(
    resolution: LeaveApproverResolution,
) -> LeaveEligibilityIssue | None:
    if resolution.is_resolved:
        return None
    return LeaveEligibilityIssue(
        code=resolution.failure_code or "APPROVER_NOT_FOUND",
        message=resolution.failure_message
        or "An approver could not be resolved from the employee approval configuration.",
        field="approver",
    )


def _stored_blocking_reasons(
    draft: AILeaveRequestDraft,
    fallback: list[LeaveEligibilityIssue],
) -> list[LeaveEligibilityIssue]:
    try:
        stored = json.loads(draft.blocking_reasons)
        return [LeaveEligibilityIssue.model_validate(item) for item in stored]
    except (TypeError, ValueError):
        return fallback


def _draft_approver_resolution(
    db: Session,
    draft: AILeaveRequestDraft,
    employee: Employee,
) -> LeaveApproverResolution:
    if not draft.approver_id:
        return resolve_leave_approver_with_reason(db, employee)
    approver = db.query(Employee).filter(
        Employee.id == draft.approver_id
    ).first()
    if not approver:
        return LeaveApproverResolution(
            approver=None,
            failure_code="APPROVER_MANAGER_REFERENCE_INVALID",
            failure_message=(
                "The approver captured by this draft no longer matches an employee "
                "record. The draft must be refreshed after the approval route is corrected."
            ),
        )
    return LeaveApproverResolution(
        approver=ResolvedLeaveApprover(
            employee_id=approver.id,
            display_name=f"{approver.first_name} {approver.last_name}".strip(),
            source="draft_snapshot",
        )
    )


def _serialize(
    draft: AILeaveRequestDraft,
    *,
    tool: str,
    leave_type: LeaveType,
    approver_name: str | None,
    approver_issue: LeaveEligibilityIssue | None = None,
) -> LeaveRequestDraftOutput:
    snapshot = CheckMyLeaveEligibilityOutput.model_validate(
        json.loads(draft.eligibility_snapshot)
    )
    blocking_reasons = _stored_blocking_reasons(
        draft, list(snapshot.blocking_reasons)
    )
    if approver_issue and not any(
        item.code == approver_issue.code for item in blocking_reasons
    ):
        blocking_reasons.append(approver_issue)
    return LeaveRequestDraftOutput(
        tool=tool,
        draft_id=draft.id,
        status=draft.status,
        leave_type=leave_type.name,
        leave_type_code=draft.leave_type_code,
        start_date=draft.start_date,
        end_date=draft.end_date,
        calendar_day_count=snapshot.calendar_day_count,
        working_day_count=float(draft.working_day_count),
        reason=draft.reason,
        eligibility_status=snapshot.eligibility_status,
        required_leave_units=snapshot.required_leave_units,
        available_leave_balance=snapshot.available_leave_balance,
        balance_source=draft.balance_source,
        approver=approver_name,
        approver_resolution="resolved" if draft.approver_id else "missing",
        blocking_reasons=blocking_reasons,
        warnings=[item for item in snapshot.warnings],
        expires_at=draft.expires_at,
        version=draft.version,
        correlation_id=draft.correlation_id,
    )


def _employee(db: Session, owner_id: str) -> Employee:
    employee = db.query(Employee).filter(
        Employee.id == owner_id,
        Employee.is_active == True,
        Employee.employment_status == "active",
    ).first()
    if not employee:
        raise LeaveDraftError("PERMISSION_DENIED", "An active employee profile is required.")
    return employee


def _draft_by_id(
    db: Session, owner_id: str, draft_id: str
) -> AILeaveRequestDraft:
    draft = db.query(AILeaveRequestDraft).filter(
        AILeaveRequestDraft.id == draft_id,
        AILeaveRequestDraft.owner_employee_id == owner_id,
        AILeaveRequestDraft.capability == "leave_request",
    ).with_for_update().first()
    if not draft:
        raise LeaveDraftError("DRAFT_NOT_FOUND", "No matching leave request draft was found.")
    if draft.status == "discarded":
        raise LeaveDraftError("DRAFT_NOT_FOUND", "That leave request draft was discarded.")
    if draft.status == "expired" or (
        draft.status not in TERMINAL_STATUSES and draft.expires_at <= _now()
    ):
        draft.status = "expired"
        draft.updated_at = _now()
        db.commit()
        raise LeaveDraftError("DRAFT_EXPIRED", "That leave request draft has expired.")
    return draft


def current_leave_request_draft(
    db: Session, owner_id: str, conversation_id: str | None = None
) -> AILeaveRequestDraft:
    query = db.query(AILeaveRequestDraft).filter(
        AILeaveRequestDraft.owner_employee_id == owner_id,
        AILeaveRequestDraft.capability == "leave_request",
        AILeaveRequestDraft.status.notin_(TERMINAL_STATUSES),
    )
    if conversation_id:
        scoped = query.filter(
            AILeaveRequestDraft.conversation_id == conversation_id
        ).order_by(AILeaveRequestDraft.updated_at.desc()).first()
        if scoped:
            return _draft_by_id(db, owner_id, scoped.id)
    draft = query.order_by(AILeaveRequestDraft.updated_at.desc()).first()
    if not draft:
        raise LeaveDraftError("DRAFT_NOT_FOUND", "You do not have an active leave request draft.")
    return _draft_by_id(db, owner_id, draft.id)


def prepare_my_leave_request(
    db: Session,
    employee: Employee,
    leave_type_reference: str,
    start_date: date,
    end_date: date,
    reason: str | None,
    *,
    correlation_id: str,
    conversation_id: str | None,
    draft_id: str | None = None,
    expected_version: int | None = None,
    continue_to_confirmation: bool = False,
) -> LeaveRequestDraftOutput:
    leave_type = resolve_leave_type_reference(db, leave_type_reference)
    if not leave_type:
        raise LeaveDraftError(
            "UNSUPPORTED_LEAVE_TYPE",
            f"'{leave_type_reference}' is not a supported leave type.",
        )
    try:
        eligibility_result = check_my_leave_eligibility(
            db, employee, leave_type.name, start_date, end_date
        )
    except LeaveServiceError as exc:
        raise LeaveDraftError(exc.code, exc.message, {"field": exc.field}) from exc
    eligibility = CheckMyLeaveEligibilityOutput.model_validate(
        {"tool": "check_my_leave_eligibility", **eligibility_result.model_dump()}
    )
    normalized_reason = validate_leave_reason(reason)
    approver_resolution = resolve_leave_approver_with_reason(db, employee)
    approver = approver_resolution.approver
    status = _status(eligibility, approver_resolution.is_resolved)
    if continue_to_confirmation and status == "ready_for_review":
        status = "ready_for_confirmation"

    now = _now()
    if draft_id:
        draft = _draft_by_id(db, employee.id, draft_id)
        if expected_version is None or draft.version != expected_version:
            raise LeaveDraftError(
                "DRAFT_VERSION_CONFLICT",
                "This draft changed elsewhere. Please review the latest version.",
                {"current_version": draft.version},
            )
        draft.version += 1
    else:
        draft = AILeaveRequestDraft(
            owner_employee_id=employee.id,
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            version=1,
        )
        db.add(draft)

    draft.leave_type_id = leave_type.id
    draft.leave_type_code = (leave_type.code or "").upper()
    draft.start_date = start_date
    draft.end_date = end_date
    draft.reason = normalized_reason
    draft.eligibility_snapshot = json.dumps(
        eligibility.model_dump(mode="json"), sort_keys=True
    )
    draft.working_day_count = eligibility.working_day_count
    draft.balance_source = eligibility.balance_source
    draft.approver_id = approver.employee_id if approver else None
    blocking_reasons = list(eligibility.blocking_reasons)
    approver_blocker = _approver_issue(approver_resolution)
    if approver_blocker:
        blocking_reasons.append(approver_blocker)
    draft.blocking_reasons = json.dumps(
        [item.model_dump(mode="json") for item in blocking_reasons]
    )
    draft.warnings = json.dumps(
        [item.model_dump(mode="json") for item in eligibility.warnings]
    )
    draft.status = status
    draft.correlation_id = correlation_id
    draft.conversation_id = conversation_id
    draft.expires_at = now + DRAFT_TTL
    draft.updated_at = now
    draft.payload_hash = _hash_payload(
        owner_id=employee.id,
        leave_type_id=leave_type.id,
        start_date=start_date,
        end_date=end_date,
        reason=normalized_reason,
        version=draft.version,
    )
    db.commit()
    db.refresh(draft)
    return _serialize(
        draft,
        tool="prepare_my_leave_request" if not draft_id else "update_my_leave_request_draft",
        leave_type=leave_type,
        approver_name=approver.display_name if approver else None,
        approver_issue=approver_blocker,
    )


def get_my_leave_request_draft(
    db: Session,
    employee: Employee,
    *,
    conversation_id: str | None,
    draft_id: str | None = None,
) -> LeaveRequestDraftOutput:
    draft = (
        _draft_by_id(db, employee.id, draft_id)
        if draft_id
        else current_leave_request_draft(db, employee.id, conversation_id)
    )
    leave_type = db.query(LeaveType).filter(LeaveType.id == draft.leave_type_id).first()
    employee = _employee(db, draft.owner_employee_id)
    approver_resolution = _draft_approver_resolution(db, draft, employee)
    approver = approver_resolution.approver
    return _serialize(
        draft,
        tool="get_my_leave_request_draft",
        leave_type=leave_type,
        approver_name=approver.display_name if approver else None,
        approver_issue=_approver_issue(approver_resolution),
    )


def discard_my_leave_request_draft(
    db: Session,
    employee: Employee,
    *,
    draft_id: str,
    expected_version: int,
) -> LeaveRequestDraftOutput:
    draft = _draft_by_id(db, employee.id, draft_id)
    if draft.version != expected_version:
        raise LeaveDraftError(
            "DRAFT_VERSION_CONFLICT",
            "This draft changed elsewhere. Please review the latest version.",
            {"current_version": draft.version},
        )
    draft.status = "discarded"
    draft.version += 1
    draft.updated_at = _now()
    db.commit()
    leave_type = db.query(LeaveType).filter(LeaveType.id == draft.leave_type_id).first()
    employee = _employee(db, draft.owner_employee_id)
    approver_resolution = _draft_approver_resolution(db, draft, employee)
    approver = approver_resolution.approver
    return _serialize(
        draft,
        tool="discard_my_leave_request_draft",
        leave_type=leave_type,
        approver_name=approver.display_name if approver else None,
        approver_issue=_approver_issue(approver_resolution),
    )
