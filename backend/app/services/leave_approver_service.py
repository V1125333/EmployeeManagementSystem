"""Canonical backend-only leave approver resolution."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.employee import Employee


@dataclass(frozen=True)
class ResolvedLeaveApprover:
    employee_id: str
    display_name: str
    source: str


@dataclass(frozen=True)
class LeaveApproverResolution:
    approver: ResolvedLeaveApprover | None
    failure_code: str | None = None
    failure_message: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.approver is not None


def _normalize_reference(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _display_name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


def _failure(code: str, message: str) -> LeaveApproverResolution:
    return LeaveApproverResolution(
        approver=None,
        failure_code=code,
        failure_message=message,
    )


def resolve_leave_approver_with_reason(
    db: Session, employee: Employee
) -> LeaveApproverResolution:
    """Resolve an approver without accepting any client- or model-supplied identity."""
    if employee.manager_id:
        if employee.manager_id == employee.id:
            return _failure(
                "APPROVER_SELF_REFERENCE",
                "Your reporting-manager record points to your own employee profile. "
                "A different active approver must be configured before this draft can be confirmed.",
            )
        manager = db.query(Employee).filter(Employee.id == employee.manager_id).first()
        if not manager:
            return _failure(
                "APPROVER_MANAGER_REFERENCE_INVALID",
                "Your reporting-manager reference does not match an employee record. "
                "An administrator must correct it before this draft can be confirmed.",
            )
        if not manager.is_active or manager.employment_status != "active":
            return _failure(
                "APPROVER_MANAGER_INACTIVE",
                "Your assigned reporting manager is not an active employee. "
                "An active approver must be configured before this draft can be confirmed.",
            )
        return LeaveApproverResolution(
            approver=ResolvedLeaveApprover(
                employee_id=manager.id,
                display_name=_display_name(manager),
                source="manager_id",
            )
        )

    legacy = _normalize_reference(employee.reporting_manager)
    if not legacy:
        return _failure(
            "APPROVER_MANAGER_NOT_ASSIGNED",
            "No reporting manager or policy-defined alternate approver is configured "
            "for your employee profile. An administrator must configure the approval "
            "route before this draft can be confirmed.",
        )

    own_references = {
        "self",
        _normalize_reference(employee.work_email),
        _normalize_reference(_display_name(employee)),
    }
    if legacy in own_references:
        return _failure(
            "APPROVER_SELF_REFERENCE",
            "Your legacy reporting-manager value points to yourself. A different active "
            "approver must be configured before this draft can be confirmed.",
        )

    candidates = db.query(Employee).filter(Employee.id != employee.id).all()
    matches = [
        candidate
        for candidate in candidates
        if legacy
        in {
            _normalize_reference(candidate.work_email),
            _normalize_reference(_display_name(candidate)),
        }
    ]
    active_matches = [
        candidate
        for candidate in matches
        if candidate.is_active and candidate.employment_status == "active"
    ]
    if len(active_matches) > 1:
        return _failure(
            "APPROVER_LEGACY_REFERENCE_AMBIGUOUS",
            "The legacy reporting-manager value matches more than one active employee. "
            "An administrator must assign a normalized reporting manager before this "
            "draft can be confirmed.",
        )
    if len(active_matches) == 1:
        manager = active_matches[0]
        return LeaveApproverResolution(
            approver=ResolvedLeaveApprover(
                employee_id=manager.id,
                display_name=_display_name(manager),
                source="legacy_reporting_manager",
            )
        )
    if matches:
        return _failure(
            "APPROVER_MANAGER_INACTIVE",
            "The employee referenced by the legacy reporting-manager value is inactive. "
            "An active approver must be configured before this draft can be confirmed.",
        )
    return _failure(
        "APPROVER_LEGACY_REFERENCE_NOT_FOUND",
        "The legacy reporting-manager value does not match an active employee. "
        "An administrator must assign a normalized reporting manager before this "
        "draft can be confirmed.",
    )


def resolve_leave_approver(
    db: Session, employee: Employee
) -> ResolvedLeaveApprover | None:
    """Backward-compatible convenience wrapper for existing leave callers."""
    return resolve_leave_approver_with_reason(db, employee).approver
