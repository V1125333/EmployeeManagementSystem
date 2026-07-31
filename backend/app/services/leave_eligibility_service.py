"""Canonical read-only enrichment over Orbit's existing leave assessment."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveType
from app.models.operations import CompanyHoliday
from app.models.settings import UserSettings
from app.models.user_preferences import UserPreferences
from app.schemas.leave import (
    LeaveAssessmentInput,
    LeaveBlockingReason,
    LeaveOverlapSummary,
    LeavePolicyCheck,
    MyLeaveEligibilityResult,
)
from app.services.leave_service import (
    LeaveServiceError,
    assess_my_leave_request,
    find_overlapping_leave_requests,
    resolve_leave_type_reference,
    serialize_leave_request,
)
from app.services.leave_approver_service import resolve_leave_approver
from app.services.work_calendar_service import employee_region, region_visible


POLICY_CHECK_CODES = (
    "VALID_DATE_RANGE",
    "SAME_POLICY_YEAR",
    "JOINING_DATE",
    "PAST_DATE_POLICY",
    "ADVANCE_LIMIT",
    "LEAVE_TYPE_APPLICABILITY",
    "OPTIONAL_HOLIDAY_SELECTION",
    "EXISTING_REQUEST_OVERLAP",
    "PAYABLE_WORKING_DAYS",
    "EFFECTIVE_BALANCE",
)


def resolve_employee_timezone(db: Session, employee: Employee) -> str:
    inspector = inspect(db.get_bind())
    preference = (
        db.query(UserPreferences).filter(
            UserPreferences.user_id == employee.id
        ).first()
        if inspector.has_table(UserPreferences.__tablename__)
        else None
    )
    setting = (
        db.query(UserSettings).filter(
            UserSettings.user_id == employee.id
        ).first()
        if inspector.has_table(UserSettings.__tablename__)
        else None
    )
    candidate = (
        preference.timezone
        if preference and preference.timezone
        else setting.time_zone
        if setting and setting.time_zone
        else {
            "IN": "Asia/Kolkata",
            "US": "America/New_York",
            "AE": "Asia/Dubai",
        }.get(employee_region(employee), "UTC")
    )
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return "UTC"
    return candidate


def local_now(db: Session, employee: Employee) -> tuple[datetime, str]:
    timezone_name = resolve_employee_timezone(db, employee)
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
        timezone_name = "UTC"
    return datetime.now(zone), timezone_name


def _manager_name(db: Session, employee: Employee) -> str | None:
    approver = resolve_leave_approver(db, employee)
    return approver.display_name if approver else None


def _selected_optional_holiday(
    db: Session,
    employee: Employee,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
) -> tuple[str | None, str]:
    if (leave_type.code or "").upper() not in {"FL", "OH"}:
        return None, "not_applicable"
    if start_date != end_date:
        return None, "selection_required"
    rows = db.query(CompanyHoliday).filter(
        CompanyHoliday.is_active == True,
        CompanyHoliday.holiday_date == start_date,
        CompanyHoliday.holiday_type.in_(["floating", "optional"]),
    ).all()
    visible = [
        row for row in rows
        if region_visible(row.regions, employee_region(employee))
    ]
    if len(visible) != 1:
        return None, "selection_required"
    return visible[0].id, "selected_automatically"


def _missing_policy_configuration(
    db: Session, employee: Employee, leave_type: LeaveType, year: int
) -> bool:
    stored = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee.id,
        LeaveBalance.leave_type_id == leave_type.id,
        LeaveBalance.year == year,
    ).first()
    return (
        stored is None
        and bool(leave_type.is_paid)
        and float(leave_type.default_days_per_year or 0) <= 0
        and (leave_type.code or "").upper() not in {"CO"}
    )


def _policy_checks(blocker_codes: set[str]) -> list[LeavePolicyCheck]:
    mapping = {
        "VALID_DATE_RANGE": {"INVALID_DATE_RANGE"},
        "SAME_POLICY_YEAR": {"CROSS_YEAR_LEAVE_NOT_SUPPORTED"},
        "JOINING_DATE": {"BEFORE_JOINING_DATE"},
        "PAST_DATE_POLICY": {"PAST_DATE_NOT_ALLOWED", "PAST_DATE_LIMIT_EXCEEDED"},
        "ADVANCE_LIMIT": {"ADVANCE_LIMIT_EXCEEDED"},
        "LEAVE_TYPE_APPLICABILITY": {"LEAVE_TYPE_NOT_APPLICABLE"},
        "OPTIONAL_HOLIDAY_SELECTION": {
            "HOLIDAY_REQUIRED", "HOLIDAY_NOT_AVAILABLE",
            "HOLIDAY_DATE_MISMATCH", "HOLIDAY_ALREADY_USED",
        },
        "EXISTING_REQUEST_OVERLAP": {"LEAVE_OVERLAP"},
        "PAYABLE_WORKING_DAYS": {"NO_PAYABLE_WORKING_DAYS"},
        "EFFECTIVE_BALANCE": {
            "INSUFFICIENT_EFFECTIVE_BALANCE", "MISSING_POLICY_CONFIGURATION"
        },
    }
    return [
        LeavePolicyCheck(
            code=code,
            passed=not bool(blocker_codes.intersection(mapping[code])),
        )
        for code in POLICY_CHECK_CODES
    ]


def check_my_leave_eligibility(
    db: Session,
    employee: Employee,
    leave_type_ref: str,
    start_date: date,
    end_date: date,
    *,
    evaluated_at: datetime | None = None,
    timezone_name: str | None = None,
) -> MyLeaveEligibilityResult:
    """Evaluate eligibility without adding, flushing, committing, or mutating rows."""
    leave_type = resolve_leave_type_reference(db, leave_type_ref)
    if not leave_type:
        raise LeaveServiceError(
            "LEAVE_TYPE_NOT_FOUND",
            f"'{leave_type_ref}' is not a supported leave type.",
            404,
            "leave_type",
        )
    if evaluated_at is None or timezone_name is None:
        observed_at, resolved_timezone = local_now(db, employee)
    else:
        observed_at, resolved_timezone = evaluated_at, timezone_name

    holiday_id, optional_treatment = _selected_optional_holiday(
        db, employee, leave_type, start_date, end_date
    )
    assessment = assess_my_leave_request(
        db,
        employee,
        LeaveAssessmentInput(
            leave_type_id=leave_type.id,
            start_date=start_date,
            end_date=end_date,
            holiday_id=holiday_id,
        ),
        as_of=observed_at.replace(tzinfo=None),
    )
    blockers = list(assessment.blocking_reasons)
    if _missing_policy_configuration(db, employee, leave_type, start_date.year):
        blockers.append(
            LeaveBlockingReason(
                code="MISSING_POLICY_CONFIGURATION",
                message=f"{leave_type.name} is not configured for this policy year.",
                field="leave_type",
            )
        )
    blockers = list({item.code: item for item in blockers}.values())

    overlaps = find_overlapping_leave_requests(
        db, employee.id, start_date, end_date
    )
    overlap_items = []
    for overlap in overlaps:
        serialized = serialize_leave_request(db, overlap, employee=employee)
        overlap_items.append(
            LeaveOverlapSummary(
                request_id=serialized.id,
                leave_type=serialized.leave_type,
                start_date=serialized.start_date,
                end_date=serialized.end_date,
                status=serialized.status,
            )
        )
    source = (
        "on_request"
        if assessment.effective_balance_before == "On request"
        else "stored_balance"
        if db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.leave_type_id == leave_type.id,
            LeaveBalance.year == start_date.year,
        ).first()
        else "policy_default"
    )
    information_codes = {
        "HOLIDAY_REQUIRED",
        "HOLIDAY_NOT_AVAILABLE",
        "MISSING_POLICY_CONFIGURATION",
    }
    blocker_codes = {item.code for item in blockers}
    if "MISSING_POLICY_CONFIGURATION" in blocker_codes:
        eligibility_status = "requires_information"
    elif blockers:
        eligibility_status = (
            "requires_information"
            if blocker_codes and blocker_codes.issubset(information_codes)
            else "not_eligible"
        )
    elif assessment.warnings:
        eligibility_status = "eligible_with_warnings"
    else:
        eligibility_status = "eligible"
    calendar_count = (
        (end_date - start_date).days + 1 if end_date >= start_date else 0
    )
    return MyLeaveEligibilityResult(
        leave_type=leave_type.name,
        leave_type_code=leave_type.code,
        start_date=start_date,
        end_date=end_date,
        calendar_day_count=calendar_count,
        working_day_count=assessment.payable_working_days,
        weekend_dates_excluded=assessment.excluded_weekends,
        company_holidays_excluded=assessment.excluded_holidays,
        optional_holiday_treatment=optional_treatment,
        required_leave_units=assessment.payable_working_days,
        available_leave_balance=assessment.effective_balance_before,
        balance_source=source,
        existing_overlaps=overlap_items,
        policy_checks_performed=_policy_checks(blocker_codes),
        blocking_reasons=blockers,
        warnings=assessment.warnings,
        eligibility_status=eligibility_status,
        current_approver=_manager_name(db, employee),
        evaluated_at=observed_at,
        timezone=resolved_timezone,
    )
