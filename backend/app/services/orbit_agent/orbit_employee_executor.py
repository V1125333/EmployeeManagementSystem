from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.authentication import (
    EMPLOYEE_DIRECTORY_READ_PERMISSION,
    EMPLOYEE_MANAGER_SELF_PERMISSION,
    AuthenticatedActor,
)
from app.services.audit_service import log_audit
from app.services.employee_directory_service import (
    EmployeeDirectoryProfile,
    EmployeeManagerStatus,
    get_employee_directory_self_profile,
    get_my_reporting_manager,
    search_employee_directory,
)
from app.services.orbit_agent.orbit_classifier import OrbitContextMessage


class OrbitEmployeeOperation(str, Enum):
    EMPLOYEE_SEARCH = "employee_search"
    EMPLOYEE_PROFILE = "employee_profile"
    EMPLOYEE_DEPARTMENT = "employee_department"
    EMPLOYEE_TITLE = "employee_title"
    EMPLOYEE_MANAGER = "employee_manager"
    EMPLOYEE_DIRECTORY_SEARCH = "employee_directory_search"
    UNKNOWN_EMPLOYEE_QUERY = "unknown_employee_query"
    WRITE_REQUEST = "write_request"
    SENSITIVE_FIELD_REQUEST = "sensitive_field_request"


@dataclass(frozen=True)
class OrbitEmployeeResult:
    operation: OrbitEmployeeOperation
    message: str


_WRITE_PATTERNS = (
    r"\bchange\b",
    r"\bupdate\b",
    r"\bedit\b",
    r"\bmodify\b",
    r"\bdeactivate\b",
    r"\bactivate\b",
    r"\bdelete\b",
    r"\bremove\b",
    r"\bmake\b.*\badmin\b",
    r"\bmove\b",
    r"\bset\b.*\bmanager\b",
)
_SENSITIVE_PATTERNS = (
    r"\bsalary\b",
    r"\bcompensation\b",
    r"\bbonus\b",
    r"\bhome address\b",
    r"\bpersonal email\b",
    r"\bpersonal phone\b",
    r"\bmobile number\b",
    r"\bdate of birth\b",
    r"\bdob\b",
    r"\bssn\b",
    r"\bsocial security\b",
    r"\bbank\b",
    r"\bemergency contact\b",
    r"\bmedical\b",
    r"\bhr notes\b",
    r"\bperformance\b",
    r"\bdisciplinary\b",
    r"\bpermissions\b",
)
_SELF_PROFILE_PATTERNS = (
    r"\bwho am i\b",
    r"\bshow my employee profile\b",
    r"\bshow my profile\b",
    r"\bwhat department am i in\b",
    r"\bwhat is my job title\b",
)
_SELF_MANAGER_PATTERNS = (
    r"\bwho is my manager\b",
    r"\bwho do i report to\b",
    r"\bwhat is my manager'?s name\b",
    r"\bwho is my reporting manager\b",
)
_DIRECTORY_MANAGER_PATTERNS = (
    r"\bwho is the (?P<department>[a-z][a-z\s&-]+?) manager\b",
    r"\bwho is the manager for (?P<department>[a-z][a-z\s&-]+)\b",
)
_FOLLOWUP_PRONOUN_PATTERNS = (
    r"\bhis\b",
    r"\bher\b",
    r"\btheir\b",
)


def _normalize(value: str) -> str:
    return " ".join(
        re.sub(r"[^\w\s'&-]", " ", value.strip().lower())
        .replace("_", " ")
        .split()
    )


def _recent_user_messages(recent_context: list[OrbitContextMessage] | None) -> list[str]:
    if not recent_context:
        return []
    return [
        item.content.strip()
        for item in recent_context
        if item.role == "user" and item.content.strip()
    ]


def _has_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _extract_named_reference(text: str) -> str | None:
    pronouns = {"he", "she", "they", "him", "her", "them", "his", "their"}
    patterns = (
        r"\bfind (?P<name>[a-z][a-z\s&-]+)$",
        r"\bshow me (?P<name>[a-z][a-z\s&-]+)$",
        r"\blook up (?P<name>[a-z][a-z\s&-]+)$",
        r"\bsearch for (?P<name>[a-z][a-z\s&-]+)$",
        r"\bwho is (?P<name>[a-z][a-z\s&-]+)$",
        r"\btell me about (?P<name>[a-z][a-z\s&-]+)$",
        r"\bwhat department is (?P<name>[a-z][a-z\s&-]+?) in\b",
        r"\bwhat is (?P<name>[a-z][a-z\s&-]+?)(?:'s| s) job title\b",
        r"\bwhat is (?P<name>[a-z][a-z\s&-]+?)(?:'s| s) title\b",
        r"\bwho is (?P<name>[a-z][a-z\s&-]+?)(?:'s| s) manager\b",
        r"\bwhat is (?P<name>[a-z][a-z\s&-]+?)(?:'s| s) work email\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        name = " ".join(match.group("name").split())
        first_token = name.split()[0] if name.split() else ""
        if (
            name in {"my manager", "the engineering manager"}
            or name in pronouns
            or first_token in pronouns
        ):
            continue
        return name
    return None


def _resolve_operation(text: str) -> OrbitEmployeeOperation:
    if _has_pattern(text, _WRITE_PATTERNS):
        return OrbitEmployeeOperation.WRITE_REQUEST
    if _has_pattern(text, _SENSITIVE_PATTERNS):
        return OrbitEmployeeOperation.SENSITIVE_FIELD_REQUEST
    if _has_pattern(text, _SELF_MANAGER_PATTERNS) or "manager" in text:
        if any(re.search(pattern, text) for pattern in _DIRECTORY_MANAGER_PATTERNS):
            return OrbitEmployeeOperation.EMPLOYEE_DIRECTORY_SEARCH
        return OrbitEmployeeOperation.EMPLOYEE_MANAGER
    if any(token in text for token in ("what department is", "department am i in", "department is he in", "department is she in")):
        return OrbitEmployeeOperation.EMPLOYEE_DEPARTMENT
    if any(token in text for token in ("job title", "title")):
        return OrbitEmployeeOperation.EMPLOYEE_TITLE
    if _has_pattern(text, _SELF_PROFILE_PATTERNS) or any(token in text for token in ("find ", "show me ", "who is ", "tell me about ", "look up ")):
        return OrbitEmployeeOperation.EMPLOYEE_PROFILE
    return OrbitEmployeeOperation.UNKNOWN_EMPLOYEE_QUERY


def _find_followup_reference(
    recent_context: list[OrbitContextMessage] | None,
) -> str | None:
    for previous in reversed(_recent_user_messages(recent_context)):
        named = _extract_named_reference(_normalize(previous))
        if named:
            return named
    return None


def _format_disambiguation(matches: list[EmployeeDirectoryProfile]) -> str:
    lines = [
        f"- {item.display_name} — {item.department or 'Unassigned'}"
        + (f", {item.job_title}" if item.job_title else "")
        for item in matches[:5]
    ]
    return "I found multiple matches:\n" + "\n".join(lines)


def _format_profile(profile: EmployeeDirectoryProfile, *, self_view: bool = False) -> str:
    subject = "You are" if self_view else f"{profile.display_name} is"
    details = []
    if profile.job_title:
        details.append(profile.job_title)
    if profile.department:
        details.append(f"in the {profile.department} department")
    if not details:
        return f"{subject} in the employee directory."
    return f"{subject} {' '.join(details)}."


def _format_directory_result(matches: list[EmployeeDirectoryProfile], department: str | None) -> str:
    if not matches:
        label = department or "that team"
        return f"I couldn't find a matching manager in {label}."
    if len(matches) == 1:
        profile = matches[0]
        return _format_profile(profile) + (
            f" Work email: {profile.work_email}." if profile.work_email else ""
        )
    return _format_disambiguation(matches)


def _lookup_profiles(
    db: Session,
    *,
    reference: str,
    limit: int = 5,
) -> list[EmployeeDirectoryProfile]:
    return search_employee_directory(db, search=reference, limit=limit)


def _log_employee_audit(
    db: Session,
    actor: AuthenticatedActor,
    *,
    operation: OrbitEmployeeOperation,
    message: str,
    request: Request | None,
    success: bool,
) -> None:
    log_audit(
        db,
        actor.employee,
        action="orbit.employee.read",
        entity_type="orbit_employee_query",
        entity_id=actor.employee.id,
        reason=f"Orbit handled {operation.value}.",
        metadata={
            "operation": operation.value,
            "success": success,
            "message_length": len(message.strip()),
            "organization_scope": actor.principal.organization_scope,
        },
        source="orbit",
        request=request,
    )


async def execute_employee_read(
    *,
    db: Session,
    actor: AuthenticatedActor,
    query: str,
    recent_context: list[OrbitContextMessage] | None = None,
    request: Request | None = None,
) -> OrbitEmployeeResult:
    normalized = _normalize(query)
    operation = _resolve_operation(normalized)

    if not actor.principal.has_permission(EMPLOYEE_DIRECTORY_READ_PERMISSION):
        result = OrbitEmployeeResult(
            operation=operation,
            message="You do not have permission to view employee directory information.",
        )
        _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    if operation is OrbitEmployeeOperation.WRITE_REQUEST:
        result = OrbitEmployeeResult(
            operation=operation,
            message="I can currently look up employee information, but changing employee records through Orbit isn't enabled yet.",
        )
        _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    if operation is OrbitEmployeeOperation.SENSITIVE_FIELD_REQUEST:
        result = OrbitEmployeeResult(
            operation=operation,
            message="Orbit can currently help with directory information like department, title, manager, and work email, but it can't share that field.",
        )
        _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    if operation is OrbitEmployeeOperation.EMPLOYEE_DIRECTORY_SEARCH:
        department = None
        for pattern in _DIRECTORY_MANAGER_PATTERNS:
            match = re.search(pattern, normalized)
            if match:
                department = match.group("department")
                break
        matches = search_employee_directory(
            db,
            department=department,
            manager_only=True,
            limit=5,
        )
        result = OrbitEmployeeResult(
            operation=operation,
            message=_format_directory_result(matches, department),
        )
        _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=bool(matches))
        return result

    if _has_pattern(normalized, _SELF_MANAGER_PATTERNS):
        if not actor.principal.has_permission(EMPLOYEE_MANAGER_SELF_PERMISSION):
            result = OrbitEmployeeResult(
                operation=OrbitEmployeeOperation.EMPLOYEE_MANAGER,
                message="You do not have permission to view your manager information.",
            )
            _log_employee_audit(db, actor, operation=result.operation, message=query, request=request, success=False)
            return result
        manager = get_my_reporting_manager(db, actor.employee)
        if manager.status is EmployeeManagerStatus.AVAILABLE:
            message = f"Your manager is {manager.display_name}"
            if manager.job_title:
                message += f", {manager.job_title}"
            if manager.work_email:
                message += f". You can reach them at {manager.work_email}."
            else:
                message += "."
        elif manager.status is EmployeeManagerStatus.NOT_ASSIGNED:
            message = "A reporting manager is not currently assigned to your employee profile."
        else:
            message = "Your manager information is currently unavailable. Please contact HR or your administrator."
        result = OrbitEmployeeResult(operation=OrbitEmployeeOperation.EMPLOYEE_MANAGER, message=message)
        _log_employee_audit(db, actor, operation=result.operation, message=query, request=request, success=manager.status is EmployeeManagerStatus.AVAILABLE)
        return result

    self_profile = get_employee_directory_self_profile(db, actor.employee)
    if _has_pattern(normalized, _SELF_PROFILE_PATTERNS):
        if "department" in normalized:
            message = (
                f"You are in the {self_profile.department} department."
                if self_profile.department
                else "Your department is not currently assigned."
            )
            result = OrbitEmployeeResult(operation=OrbitEmployeeOperation.EMPLOYEE_DEPARTMENT, message=message)
        elif "job title" in normalized or re.search(r"\btitle\b", normalized):
            message = (
                f"Your job title is {self_profile.job_title}."
                if self_profile.job_title
                else "Your job title is not currently assigned."
            )
            result = OrbitEmployeeResult(operation=OrbitEmployeeOperation.EMPLOYEE_TITLE, message=message)
        else:
            result = OrbitEmployeeResult(operation=OrbitEmployeeOperation.EMPLOYEE_PROFILE, message=_format_profile(self_profile, self_view=True))
        _log_employee_audit(db, actor, operation=result.operation, message=query, request=request, success=True)
        return result

    reference = _extract_named_reference(normalized)
    if reference is None and _has_pattern(normalized, _FOLLOWUP_PRONOUN_PATTERNS):
        reference = _find_followup_reference(recent_context)
    if reference is None:
        result = OrbitEmployeeResult(
            operation=OrbitEmployeeOperation.UNKNOWN_EMPLOYEE_QUERY,
            message="I can currently help find employees, summarize a directory profile, and answer department, title, manager, or work-email questions.",
        )
        _log_employee_audit(db, actor, operation=result.operation, message=query, request=request, success=False)
        return result

    try:
        matches = _lookup_profiles(db, reference=reference)
    except Exception:
        result = OrbitEmployeeResult(
            operation=operation,
            message="I couldn't retrieve employee information right now.",
        )
        _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    if not matches:
        result = OrbitEmployeeResult(
            operation=operation,
            message=f'I couldn\'t find an employee matching "{reference}".',
        )
        _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    if len(matches) > 1:
        result = OrbitEmployeeResult(
            operation=operation,
            message=_format_disambiguation(matches),
        )
        _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=False)
        return result

    profile = matches[0]
    if operation is OrbitEmployeeOperation.EMPLOYEE_DEPARTMENT:
        message = (
            f"{profile.display_name} is in the {profile.department} department."
            if profile.department
            else f"{profile.display_name}'s department is not currently assigned."
        )
    elif operation is OrbitEmployeeOperation.EMPLOYEE_TITLE:
        message = (
            f"{profile.display_name}'s job title is {profile.job_title}."
            if profile.job_title
            else f"{profile.display_name}'s job title is not currently assigned."
        )
    elif operation is OrbitEmployeeOperation.EMPLOYEE_MANAGER:
        message = (
            f"{profile.display_name} reports to {profile.manager_name}."
            if profile.manager_name
            else f"{profile.display_name} does not have a visible manager assignment right now."
        )
    else:
        message = _format_profile(profile)
        if "work email" in normalized and profile.work_email:
            message += f" Work email: {profile.work_email}."
    result = OrbitEmployeeResult(operation=operation, message=message)
    _log_employee_audit(db, actor, operation=operation, message=query, request=request, success=True)
    return result
