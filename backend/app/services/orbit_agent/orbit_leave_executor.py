from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.authentication import (
    AuthenticatedActor,
    LEAVE_BALANCE_SELF_PERMISSION,
    LEAVE_REQUEST_SELF_PERMISSION,
)
from app.models.leave_attendance import LeaveType
from app.schemas.ai import GetMyLeaveRequestStatusInput
from app.schemas.leave import MyLeaveRequestQuery
from app.services.audit_service import log_audit
from app.services.leave_service import (
    LeaveServiceError,
    get_my_leave_balances,
    list_my_leave_requests,
    resolve_leave_type_reference,
)
from app.ai.leave_request_tools import (
    AIToolException,
    get_my_leave_request_status,
)
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage


class OrbitLeaveOperation(str, Enum):
    LEAVE_BALANCE = "leave_balance"
    LEAVE_HISTORY = "leave_history"
    LEAVE_STATUS = "leave_status"
    LEAVE_USED = "leave_used"
    UNKNOWN_LEAVE_QUERY = "unknown_leave_query"
    WRITE_REQUEST = "write_request"


@dataclass(frozen=True)
class OrbitLeaveResult:
    operation: OrbitLeaveOperation
    message: str


_LEAVE_TYPE_ALIASES = {
    "casual": "casual leave",
    "sick": "sick leave",
    "earned": "earned leave",
    "comp off": "compensatory off",
    "compensatory": "compensatory off",
    "lop": "loss of pay",
    "optional": "optional holiday",
    "floating": "floating holiday",
}
_WRITE_PATTERNS = (
    r"\bapply\b",
    r"\bsubmit\b",
    r"\bcancel\b",
    r"\bwithdraw\b",
    r"\bdelete\b",
    r"\bedit\b",
    r"\bchange\b",
    r"\bmodify\b",
    r"\bupdate\b",
    r"\bapprove\b",
    r"\breject\b",
    r"\bbook\b",
    r"\brequest\b.*\bleave\b",
)
_STATUS_WORDS = ("pending", "approved", "rejected", "cancelled", "withdrawn", "draft", "submitted")
_FOLLOWUP_PREFIXES = (
    "and ",
    "what about",
    "how about",
    "what happened",
    "that one",
    "that request",
    "that leave",
    "it ",
    "its ",
)
_THIRD_PARTY_PATTERNS = (
    r"\banother employee\b",
    r"\bsomeone else\b",
    r"\bsomebody else\b",
    r"\bhis leave\b",
    r"\bher leave\b",
    r"\btheir leave\b",
    r"\bemployee_id\b",
)


def _normalize(value: str) -> str:
    return " ".join(
        re.sub(r"[^\w\s'-]", " ", value.strip().lower())
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def _format_day_count(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    return f"{float(value):g} day(s)"


def _format_short_date(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}, {value.year}"


def _format_date_range(start: date, end: date) -> str:
    if start == end:
        return _format_short_date(start)
    return f"{_format_short_date(start)} to {_format_short_date(end)}"


def _is_followup(text: str) -> bool:
    if not text:
        return False
    return text.startswith(_FOLLOWUP_PREFIXES) or text in {
        "what about last year",
        "what about this year",
        "what about now",
        "and mine",
        "and my leave",
    }


def _has_third_party_reference(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _THIRD_PARTY_PATTERNS)


def _extract_year(text: str, today: date) -> int | None:
    if "last year" in text:
        return today.year - 1
    if "this year" in text or "current year" in text:
        return today.year
    match = re.search(r"\b(20\d{2})\b", text)
    if not match:
        return None
    return int(match.group(1))


def _extract_statuses(text: str) -> list[str]:
    return [status for status in _STATUS_WORDS if re.search(rf"\b{re.escape(status)}\b", text)]


def _extract_leave_type_name(db: Session, text: str) -> str | None:
    if not text:
        return None

    active_types = db.query(LeaveType).filter(LeaveType.is_active == True).all()
    candidates: list[tuple[int, str]] = []
    for leave_type in active_types:
        variants = {
            _normalize(leave_type.name),
            _normalize(leave_type.code),
            _normalize(leave_type.name).removesuffix(" leave"),
        }
        for alias, canonical in _LEAVE_TYPE_ALIASES.items():
            if canonical == _normalize(leave_type.name):
                variants.add(alias)
        for variant in variants:
            if not variant:
                continue
            if re.search(rf"\b{re.escape(variant)}\b", text):
                candidates.append((len(variant), leave_type.name))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]

    for alias, canonical in _LEAVE_TYPE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            matched = resolve_leave_type_reference(db, canonical)
            if matched:
                return matched.name
    return None


def _resolve_operation_from_text(text: str) -> OrbitLeaveOperation:
    if any(re.search(pattern, text) for pattern in _WRITE_PATTERNS):
        return OrbitLeaveOperation.WRITE_REQUEST
    if any(token in text for token in ("history", "recent leave", "recent leaves", "recent requests", "leave requests", "my requests")):
        return OrbitLeaveOperation.LEAVE_HISTORY
    if (
        "status" in text
        or "what happened" in text
        or "where is my leave request" in text
        or "decision" in text
        or any(re.search(rf"\b{status}\b", text) for status in _STATUS_WORDS)
    ):
        return OrbitLeaveOperation.LEAVE_STATUS
    if any(token in text for token in ("how much did i use", "leave used", "used leave", "taken", "have i used")):
        return OrbitLeaveOperation.LEAVE_USED
    if any(token in text for token in ("balance", "remaining", "available", "how many leaves do i have", "how much leave do i have", "leave do i have")):
        return OrbitLeaveOperation.LEAVE_BALANCE
    return OrbitLeaveOperation.UNKNOWN_LEAVE_QUERY


def _recent_user_messages(recent_context: list[OrbitContextMessage] | None) -> list[str]:
    if not recent_context:
        return []
    return [
        _normalize(item.content)
        for item in recent_context
        if item.role == "user" and item.content.strip()
    ]


def _resolve_operation(
    message_text: str,
    *,
    recent_context: list[OrbitContextMessage] | None,
) -> OrbitLeaveOperation:
    direct = _resolve_operation_from_text(message_text)
    if direct is not OrbitLeaveOperation.UNKNOWN_LEAVE_QUERY:
        return direct

    if not _is_followup(message_text):
        return direct

    for prior in reversed(_recent_user_messages(recent_context)):
        prior_operation = _resolve_operation_from_text(prior)
        if prior_operation is not OrbitLeaveOperation.UNKNOWN_LEAVE_QUERY:
            return prior_operation
    return direct


def _resolve_leave_type(
    db: Session,
    message_text: str,
    *,
    recent_context: list[OrbitContextMessage] | None,
) -> str | None:
    direct = _extract_leave_type_name(db, message_text)
    if direct:
        return direct
    for prior in reversed(_recent_user_messages(recent_context)):
        resolved = _extract_leave_type_name(db, prior)
        if resolved:
            return resolved
    return None


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, AIToolException):
        if exc.error.code == "AMBIGUOUS_LEAVE_REQUEST":
            return "I found more than one matching leave request. Please mention the leave type or date."
        return exc.error.message
    if isinstance(exc, LeaveServiceError):
        if exc.code == "LEAVE_TYPE_NOT_FOUND":
            return exc.message
        return exc.message
    return "Your leave information is temporarily unavailable."


def _log_leave_audit(
    db: Session,
    actor: AuthenticatedActor,
    *,
    operation: OrbitLeaveOperation,
    message: str,
    request: Request | None,
    success: bool,
) -> None:
    log_audit(
        db,
        actor.employee,
        action="orbit.leave.read",
        entity_type="orbit_leave_query",
        entity_id=actor.employee.id,
        reason=f"Orbit handled {operation.value}.",
        metadata={
            "operation": operation.value,
            "success": success,
            "message_length": len(message.strip()),
        },
        source="orbit",
        request=request,
    )


def _format_balance_message(snapshot, leave_type_name: str | None) -> str:
    balances = snapshot.balances
    if leave_type_name:
        balances = [item for item in balances if item.type == leave_type_name]
        if not balances:
            return f"No effective {leave_type_name} balance is available."
    if not balances:
        return "Your leave balances are currently unavailable."
    if len(balances) == 1:
        item = balances[0]
        return (
            f"Your {item.type} balance for {snapshot.year} is {_format_day_count(item.available)} available, "
            f"{_format_day_count(item.used)} used, and {_format_day_count(item.pending)} pending "
            f"out of {_format_day_count(item.total)} total."
        )
    summary = "; ".join(
        f"{item.type}: {_format_day_count(item.available)} available"
        for item in balances[:4]
    )
    if len(balances) > 4:
        summary += f"; plus {len(balances) - 4} more leave type(s)"
    return f"Your leave balances for {snapshot.year}: {summary}."


def _format_used_message(snapshot, leave_type_name: str | None) -> str:
    balances = snapshot.balances
    if leave_type_name:
        balances = [item for item in balances if item.type == leave_type_name]
        if not balances:
            return f"No effective {leave_type_name} balance is available."
    if not balances:
        return "Your leave balances are currently unavailable."
    if len(balances) == 1:
        item = balances[0]
        return (
            f"You've used {_format_day_count(item.used)} of {item.type} in {snapshot.year}. "
            f"You still have {_format_day_count(item.available)} available and {_format_day_count(item.pending)} pending."
        )
    total_used = sum(float(item.used) for item in balances)
    summary = "; ".join(
        f"{item.type}: {_format_day_count(item.used)} used"
        for item in balances[:4]
    )
    if len(balances) > 4:
        summary += f"; plus {len(balances) - 4} more leave type(s)"
    return f"You've used {_format_day_count(total_used)} across your leave balances in {snapshot.year}. {summary}."


def _format_history_message(snapshot) -> str:
    if snapshot.total_matches == 0:
        return "You don't have any matching leave requests."
    items = []
    for request in snapshot.requests[:4]:
        items.append(
            f"{request.leave_type} ({request.status}, {_format_date_range(request.start_date, request.end_date)}, {_format_day_count(request.total_days)})"
        )
    summary = "; ".join(items)
    extra = f" I found {snapshot.total_matches} matching request(s)." if snapshot.total_matches > len(snapshot.requests[:4]) else ""
    return f"Your recent leave requests: {summary}.{extra}"


def _format_status_message(output) -> str:
    request = output.request
    sentence = (
        f"Your latest matching leave request is {request.status}: {request.leave_type} for "
        f"{_format_date_range(request.start_date, request.end_date)} "
        f"({_format_day_count(request.total_days)})."
    )
    if request.status in {"submitted", "pending"} and request.approver:
        sentence += f" It is currently pending with {request.approver}."
    elif request.decided_by:
        sentence += f" It was reviewed by {request.decided_by}."
    return sentence


async def execute_leave_read(
    *,
    db: Session,
    actor: AuthenticatedActor,
    query: str,
    conversation_context: list[OrbitContextMessage] | None = None,
    request: Request | None = None,
) -> OrbitLeaveResult:
    normalized = _normalize(query)
    today = date.today()
    operation = _resolve_operation(normalized, recent_context=conversation_context)

    if _has_third_party_reference(normalized):
        result = OrbitLeaveResult(
            operation=OrbitLeaveOperation.UNKNOWN_LEAVE_QUERY,
            message="Orbit can currently access only your own leave information.",
        )
        _log_leave_audit(db, actor, operation=result.operation, message=query, request=request, success=False)
        return result

    if operation is OrbitLeaveOperation.WRITE_REQUEST:
        result = OrbitLeaveResult(
            operation=operation,
            message="Orbit can currently read your leave information, but it can't create, submit, cancel, or change leave requests yet.",
        )
        _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    leave_type_name = _resolve_leave_type(db, normalized, recent_context=conversation_context)
    year = _extract_year(normalized, today)

    if operation in {OrbitLeaveOperation.LEAVE_BALANCE, OrbitLeaveOperation.LEAVE_USED}:
        if not actor.principal.has_permission(LEAVE_BALANCE_SELF_PERMISSION):
            result = OrbitLeaveResult(operation=operation, message="You do not have permission to view this balance.")
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result
        if year is not None and year != today.year:
            result = OrbitLeaveResult(
                operation=operation,
                message="Orbit can currently show your current leave balances only. Historical year-specific balances aren't available here yet.",
            )
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result
        if leave_type_name and not resolve_leave_type_reference(db, leave_type_name):
            result = OrbitLeaveResult(
                operation=operation,
                message=f"'{leave_type_name}' is not a supported leave type.",
            )
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result
        try:
            snapshot = get_my_leave_balances(db, actor.employee)
            message = (
                _format_used_message(snapshot, leave_type_name)
                if operation is OrbitLeaveOperation.LEAVE_USED
                else _format_balance_message(snapshot, leave_type_name)
            )
            result = OrbitLeaveResult(operation=operation, message=message)
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=True)
            return result
        except Exception as exc:
            result = OrbitLeaveResult(operation=operation, message=_safe_error_message(exc))
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result

    if operation is OrbitLeaveOperation.LEAVE_HISTORY:
        if not actor.principal.has_permission(LEAVE_REQUEST_SELF_PERMISSION):
            result = OrbitLeaveResult(operation=operation, message="You do not have permission to view leave requests.")
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result
        created_from = date(year, 1, 1) if year else None
        created_to = date(year, 12, 31) if year else None
        try:
            snapshot = list_my_leave_requests(
                db,
                actor.employee,
                MyLeaveRequestQuery(
                    statuses=_extract_statuses(normalized),
                    leave_type=leave_type_name,
                    created_from=created_from,
                    created_to=created_to,
                    limit=4,
                ),
            )
            result = OrbitLeaveResult(operation=operation, message=_format_history_message(snapshot))
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=True)
            return result
        except Exception as exc:
            result = OrbitLeaveResult(operation=operation, message=_safe_error_message(exc))
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result

    if operation is OrbitLeaveOperation.LEAVE_STATUS:
        if not actor.principal.has_permission(LEAVE_REQUEST_SELF_PERMISSION):
            result = OrbitLeaveResult(operation=operation, message="You do not have permission to view leave requests.")
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result
        try:
            output = get_my_leave_request_status(
                db,
                actor.principal,
                GetMyLeaveRequestStatusInput(
                    leave_type=leave_type_name,
                    status=_extract_statuses(normalized)[0] if _extract_statuses(normalized) else None,
                    latest=True,
                ),
            )
            result = OrbitLeaveResult(operation=operation, message=_format_status_message(output))
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=True)
            return result
        except Exception as exc:
            result = OrbitLeaveResult(operation=operation, message=_safe_error_message(exc))
            _log_leave_audit(db, actor, operation=operation, message=query, request=request, success=False)
            return result

    result = OrbitLeaveResult(
        operation=OrbitLeaveOperation.UNKNOWN_LEAVE_QUERY,
        message="I can currently help with your leave balance, used leave, recent leave requests, and leave request status.",
    )
    _log_leave_audit(db, actor, operation=result.operation, message=query, request=request, success=False)
    return result
