from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday
from app.schemas.leave import (
    ConfiguredLeavePolicy,
    ExcludedLeaveDate,
    LeaveAssessmentInput,
    LeaveBalanceResponse,
    LeaveBlockingReason,
    LeaveContextResponse,
    LeaveEligibilityResponse,
    LeaveRequestInput,
    LeaveRequestResponse,
    LeaveWarning,
    OwnerScopedLeaveRequestStatus,
    SubmittedLeaveResult,
)
from app.services.audit_service import log_audit
from app.core.config import settings
from app.services.transactional_email_service import enqueue_email
from app.services.work_calendar_service import (
    employee_working_weekdays,
    iter_dates,
    payable_leave_dates,
    employee_region,
    region_visible,
)


DEFAULT_LEAVE_DATE_POLICIES = {
    "SL": {
        "allow_future_dates": True,
        "past_date_limit_days": None,
        "future_date_warning": None,
    },
    "BL": {
        "allow_future_dates": True,
        "past_date_limit_days": 30,
        "future_date_warning": "Future bereavement leave is unusual. Please confirm the dates before submitting.",
    },
}


@dataclass
class LeaveServiceError(Exception):
    code: str
    message: str
    status_code: int = 400
    field: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


def decimal_to_float(value: Any) -> float:
    return float(value) if isinstance(value, Decimal) else float(value or 0)


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown"
    return f"{employee.first_name} {employee.last_name}".strip()


def employee_joining_date(employee: Employee) -> date | None:
    return employee.date_of_joining or employee.joining_date


def min_request_date(employee: Employee, *, today: date | None = None) -> date:
    current = today or date.today()
    joining_date = employee_joining_date(employee)
    return max(current, joining_date) if joining_date else current


def leave_type_applies_to_employee(leave_type: LeaveType, employee: Employee) -> bool:
    code = (leave_type.code or "").upper()
    gender = (employee.gender or "").lower()
    if code == "ML":
        return gender == "female"
    if code == "PL":
        return gender == "male"
    return True


def configured_policy(leave_type: LeaveType) -> ConfiguredLeavePolicy:
    code = (leave_type.code or "").upper()
    defaults = DEFAULT_LEAVE_DATE_POLICIES.get(
        code,
        {"allow_future_dates": True, "past_date_limit_days": None, "future_date_warning": None},
    )
    allow_future = leave_type.allow_future_dates
    return ConfiguredLeavePolicy(
        leave_type_id=leave_type.id,
        name=leave_type.name,
        code=code,
        is_paid=bool(leave_type.is_paid),
        is_carry_forward=bool(leave_type.is_carry_forward),
        max_carry_forward_days=decimal_to_float(leave_type.max_carry_forward_days),
        allow_future_dates=defaults["allow_future_dates"] if allow_future is None else bool(allow_future),
        past_date_limit_days=(
            leave_type.past_date_limit_days
            if leave_type.past_date_limit_days is not None
            else defaults["past_date_limit_days"]
        ),
        future_date_warning=(
            leave_type.future_date_warning
            if leave_type.future_date_warning is not None
            else defaults["future_date_warning"]
        ),
        # Production currently rejects every past-dated request in the general
        # validator, even though BL exposes a past-date window. Preserve that
        # behavior until the product owner resolves the policy conflict.
        past_dates_currently_allowed=False,
    )


def _active_leave_type(db: Session, leave_type_id: str) -> LeaveType:
    leave_type = db.query(LeaveType).filter(
        LeaveType.id == leave_type_id,
        LeaveType.is_active == True,
    ).first()
    if not leave_type:
        raise LeaveServiceError("LEAVE_TYPE_NOT_FOUND", "Leave type not found.", 404, "leave_type_id")
    return leave_type


def _balance_for_year(
    db: Session,
    employee_id: str,
    leave_type: LeaveType,
    year: int,
    *,
    provision: bool = False,
    lock: bool = False,
) -> tuple[LeaveBalance | None, float, float, float]:
    query = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type_id == leave_type.id,
        LeaveBalance.year == year,
    )
    if lock:
        query = query.with_for_update()
    balance = query.first()
    if balance is None and provision:
        balance = LeaveBalance(
            employee_id=employee_id,
            leave_type_id=leave_type.id,
            year=year,
            total_days=leave_type.default_days_per_year,
            used_days=0,
            carry_forward_days=0,
        )
        db.add(balance)
        db.flush()

    total = (
        decimal_to_float(balance.total_days) + decimal_to_float(balance.carry_forward_days)
        if balance
        else decimal_to_float(leave_type.default_days_per_year)
    )
    used = decimal_to_float(balance.used_days) if balance else 0.0
    carry_forward = decimal_to_float(balance.carry_forward_days) if balance else 0.0
    return balance, total, used, carry_forward


def pending_days(db: Session, employee_id: str, leave_type_id: str, year: int) -> float:
    requests = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.leave_type_id == leave_type_id,
        LeaveRequest.status == "pending",
        LeaveRequest.start_date >= date(year, 1, 1),
        LeaveRequest.start_date <= date(year, 12, 31),
    ).all()
    return round(sum(decimal_to_float(item.total_days) for item in requests), 1)


def effective_balance(
    db: Session,
    employee_id: str,
    leave_type: LeaveType,
    year: int,
    *,
    provision: bool = False,
    lock: bool = False,
) -> tuple[LeaveBalance | None, float, float, float, float]:
    balance, total, used, _ = _balance_for_year(
        db, employee_id, leave_type, year, provision=provision, lock=lock
    )
    pending = pending_days(db, employee_id, leave_type.id, year)
    available = round(max(total - used - pending, 0), 1)
    return balance, total, used, pending, available


def provision_leave_balance(
    db: Session, employee_id: str, leave_type: LeaveType, year: int
) -> LeaveBalance:
    balance, _, _, _ = _balance_for_year(
        db, employee_id, leave_type, year, provision=True
    )
    assert balance is not None
    return balance


def serialize_leave_request(
    db: Session,
    request: LeaveRequest,
    *,
    leave_type: LeaveType | None = None,
    employee: Employee | None = None,
) -> LeaveRequestResponse:
    leave_type = leave_type or db.query(LeaveType).filter(LeaveType.id == request.leave_type_id).first()
    employee = employee or db.query(Employee).filter(Employee.id == request.employee_id).first()
    reviewer = (
        db.query(Employee).filter(Employee.id == request.reviewed_by).first()
        if request.reviewed_by
        else None
    )
    manager_name = employee.reporting_manager if employee else None
    pending_with = manager_name or "Super Admin"
    return LeaveRequestResponse(
        id=request.id,
        employee_id=request.employee_id,
        employee_name=employee_name(employee),
        leave_type_id=request.leave_type_id,
        leave_type=leave_type.name if leave_type else "Leave",
        start_date=request.start_date,
        end_date=request.end_date,
        total_days=decimal_to_float(request.total_days),
        holiday_id=request.holiday_id,
        reason=request.reason,
        status=request.status,
        reporting_manager=manager_name,
        pending_with=pending_with if request.status == "pending" else None,
        reviewed_by=employee_name(reviewer) if reviewer else None,
        reviewed_at=request.reviewed_at,
        reviewer_notes=request.reviewer_notes,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def get_my_leave_context(
    db: Session,
    employee: Employee,
    *,
    as_of: datetime | None = None,
) -> LeaveContextResponse:
    """Return employee leave context without flushing, committing, or mutating state."""
    observed_at = as_of or datetime.utcnow()
    year = observed_at.year
    leave_types = db.query(LeaveType).filter(LeaveType.is_active == True).order_by(
        LeaveType.sort_order.asc(), LeaveType.name.asc()
    ).all()
    leave_types = [item for item in leave_types if leave_type_applies_to_employee(item, employee)]
    balances: list[LeaveBalanceResponse] = []
    for leave_type in leave_types:
        balance, total, used, pending, available = effective_balance(
            db, employee.id, leave_type, year, provision=False
        )
        on_request = total <= 0 and not leave_type.is_paid
        balances.append(
            LeaveBalanceResponse(
                leave_type_id=leave_type.id,
                type=leave_type.name,
                code=leave_type.code,
                date_policy=configured_policy(leave_type),
                total=total,
                available="On request" if on_request else available,
                effective_available="On request" if on_request else available,
                used=round(used, 1),
                pending=pending,
                is_paid=bool(leave_type.is_paid),
                is_carry_forward=bool(leave_type.is_carry_forward),
                max_carry_forward_days=decimal_to_float(leave_type.max_carry_forward_days),
                expiry_label=(
                    "No balance expiry"
                    if on_request
                    else f"Carry forward up to {decimal_to_float(leave_type.max_carry_forward_days):g} days"
                    if leave_type.is_carry_forward
                    else f"Expires Dec 31, {year}"
                ),
                initialized=balance is not None,
            )
        )

    requests = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee.id
    ).order_by(LeaveRequest.created_at.desc()).limit(12).all()
    return LeaveContextResponse(
        as_of=observed_at,
        reporting_manager=employee.reporting_manager or None,
        joining_date=employee_joining_date(employee),
        min_request_date=min_request_date(employee, today=observed_at.date()),
        balances=balances,
        requests=[serialize_leave_request(db, item, employee=employee) for item in requests],
    )


def _holiday_for_employee(
    db: Session,
    employee: Employee,
    leave_type: LeaveType,
    holiday_id: str | None,
    start_date: date,
    end_date: date,
    exclude_request_id: str | None = None,
) -> tuple[CompanyHoliday | None, LeaveBlockingReason | None]:
    if (leave_type.code or "").upper() not in {"FL", "OH"}:
        return None, None
    if not holiday_id:
        return None, LeaveBlockingReason(
            code="HOLIDAY_REQUIRED",
            message=f"{leave_type.name} requires selecting a holiday.",
            field="holiday_id",
        )
    holiday = db.query(CompanyHoliday).filter(
        CompanyHoliday.id == holiday_id,
        CompanyHoliday.is_active == True,
        CompanyHoliday.holiday_type.in_(["floating", "optional"]),
    ).first()
    region = employee_region(employee)
    if not holiday or not region_visible(holiday.regions, region):
        return None, LeaveBlockingReason(
            code="HOLIDAY_NOT_AVAILABLE",
            message="Selected holiday is not available for your region.",
            field="holiday_id",
        )
    if start_date != holiday.holiday_date or end_date != holiday.holiday_date:
        return holiday, LeaveBlockingReason(
            code="HOLIDAY_DATE_MISMATCH",
            message="Floating or optional holiday dates must match the selected holiday.",
            field="holiday_id",
        )
    existing_query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.holiday_id == holiday.id,
        LeaveRequest.status.in_(["pending", "approved"]),
    )
    if exclude_request_id:
        existing_query = existing_query.filter(LeaveRequest.id != exclude_request_id)
    existing = existing_query.first()
    if existing:
        return holiday, LeaveBlockingReason(
            code="HOLIDAY_ALREADY_USED",
            message="This holiday has already been requested or used.",
            field="holiday_id",
        )
    return holiday, None


def _exclusions(
    db: Session,
    employee: Employee,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
) -> tuple[list[ExcludedLeaveDate], list[ExcludedLeaveDate], float]:
    working_weekdays = employee_working_weekdays(employee)
    holiday_rows = db.query(CompanyHoliday).filter(
        CompanyHoliday.is_active == True,
        CompanyHoliday.holiday_date >= start_date,
        CompanyHoliday.holiday_date <= end_date,
        CompanyHoliday.holiday_type.in_(["public", "company"]),
    ).all()
    region = employee_region(employee)
    holidays = {
        row.holiday_date: row.name
        for row in holiday_rows
        if region_visible(row.regions, region)
    }
    selected_holiday_type = (leave_type.code or "").upper() in {"FL", "OH"}
    excluded_weekends: list[ExcludedLeaveDate] = []
    excluded_holidays: list[ExcludedLeaveDate] = []
    for current in iter_dates(start_date, end_date):
        if current.weekday() not in working_weekdays:
            excluded_weekends.append(
                ExcludedLeaveDate(
                    date=current,
                    reason="weekend" if current.weekday() >= 5 else "non_working_day",
                )
            )
        elif current in holidays and not selected_holiday_type:
            excluded_holidays.append(
                ExcludedLeaveDate(date=current, reason="company_holiday", label=holidays[current])
            )
    payable = float(len(payable_leave_dates(db, employee, leave_type, start_date, end_date)))
    return excluded_weekends, excluded_holidays, payable


def assess_my_leave_request(
    db: Session,
    employee: Employee,
    payload: LeaveAssessmentInput,
    *,
    as_of: datetime | None = None,
    exclude_request_id: str | None = None,
) -> LeaveEligibilityResponse:
    """Assess eligibility using the same canonical rule path used by submission."""
    observed_at = as_of or datetime.utcnow()
    leave_type = _active_leave_type(db, payload.leave_type_id)
    policy = configured_policy(leave_type)
    blockers: list[LeaveBlockingReason] = []
    warnings: list[LeaveWarning] = []

    if payload.start_date.year != payload.end_date.year:
        blockers.append(LeaveBlockingReason(
            code="CROSS_YEAR_LEAVE_NOT_SUPPORTED",
            message="Leave requests must start and end in the same calendar year.",
            field="end_date",
        ))
    if payload.end_date < payload.start_date:
        blockers.append(LeaveBlockingReason(
            code="INVALID_DATE_RANGE", message="End date must be on or after start date.", field="end_date"
        ))
    joining_date = employee_joining_date(employee)
    if joining_date and (payload.start_date < joining_date or payload.end_date < joining_date):
        blockers.append(LeaveBlockingReason(
            code="BEFORE_JOINING_DATE",
            message=f"Leave cannot be applied before your joining date ({joining_date.strftime('%b %d, %Y')}).",
            field="start_date",
        ))
    # Known policy conflict: BL exposes a 30-day past window, but production's
    # general forward-date validator rejects all past dates. Preserve that
    # behavior. See test_past_date_policy_conflict_preserves_production_rule.
    if payload.start_date < observed_at.date() or payload.end_date < observed_at.date():
        blockers.append(LeaveBlockingReason(
            code="PAST_DATE_NOT_ALLOWED",
            message="Cannot apply leave for a past date.",
            field="start_date",
        ))
    if payload.start_date > observed_at.date() + timedelta(days=90):
        blockers.append(LeaveBlockingReason(
            code="ADVANCE_LIMIT_EXCEEDED",
            message="Leave cannot be applied more than 90 days in advance.",
            field="start_date",
        ))
    if not policy.allow_future_dates and (
        payload.start_date > observed_at.date() or payload.end_date > observed_at.date()
    ):
        blockers.append(LeaveBlockingReason(
            code="FUTURE_DATE_NOT_ALLOWED",
            message=f"{leave_type.name} cannot be applied for future dates.",
            field="start_date",
        ))
    past_limit = policy.past_date_limit_days
    if past_limit is not None and payload.start_date < observed_at.date() - timedelta(days=past_limit):
        blockers.append(LeaveBlockingReason(
            code="PAST_DATE_LIMIT_EXCEEDED",
            message=f"{leave_type.name} can only be applied up to {past_limit} days in the past.",
            field="start_date",
        ))
    if not leave_type_applies_to_employee(leave_type, employee):
        blockers.append(LeaveBlockingReason(
            code="LEAVE_TYPE_NOT_APPLICABLE",
            message="This leave type is not applicable to your profile.",
            field="leave_type_id",
        ))

    _, holiday_error = _holiday_for_employee(
        db,
        employee,
        leave_type,
        payload.holiday_id,
        payload.start_date,
        payload.end_date,
        exclude_request_id,
    )
    if holiday_error:
        blockers.append(holiday_error)

    if payload.end_date >= payload.start_date:
        overlap_query = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.start_date <= payload.end_date,
            LeaveRequest.end_date >= payload.start_date,
        )
        if exclude_request_id:
            overlap_query = overlap_query.filter(LeaveRequest.id != exclude_request_id)
        overlap = overlap_query.first()
        if overlap:
            blockers.append(LeaveBlockingReason(
                code="LEAVE_OVERLAP",
                message="You already have a leave request for this period.",
                field="start_date",
            ))

    excluded_weekends: list[ExcludedLeaveDate] = []
    excluded_holidays: list[ExcludedLeaveDate] = []
    payable_days = 0.0
    if payload.end_date >= payload.start_date:
        excluded_weekends, excluded_holidays, payable_days = _exclusions(
            db, employee, leave_type, payload.start_date, payload.end_date
        )
        if payable_days <= 0:
            blockers.append(LeaveBlockingReason(
                code="NO_PAYABLE_WORKING_DAYS",
                message="Leave requests must include at least one working day.",
                field="start_date",
            ))

    _, _, _, pending, available = effective_balance(
        db, employee.id, leave_type, payload.start_date.year, provision=False
    )
    on_request = decimal_to_float(leave_type.default_days_per_year) <= 0 and not leave_type.is_paid
    before: float | str = "On request" if on_request else available
    after: float | str = "On request" if on_request else round(max(available - payable_days, 0), 1)
    if leave_type.is_paid and payable_days > available:
        message = (
            f"No balance available - {pending:g} days are pending approval."
            if available <= 0 and pending > 0
            else f"You only have {available:g} effective days available ({pending:g} days are pending approval)."
        )
        blockers.append(LeaveBlockingReason(
            code="INSUFFICIENT_EFFECTIVE_BALANCE",
            message=message,
            field="leave_type_id",
            details={"effective_available": available, "pending": pending, "requested": payable_days},
        ))
    if policy.future_date_warning and (
        payload.start_date > observed_at.date() or payload.end_date > observed_at.date()
    ):
        warnings.append(LeaveWarning(code="FUTURE_DATE_WARNING", message=policy.future_date_warning))

    # Keep one deterministic reason per rule code.
    unique_blockers = list({item.code: item for item in blockers}.values())
    return LeaveEligibilityResponse(
        as_of=observed_at,
        eligible=not unique_blockers,
        leave_type_id=leave_type.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        payable_working_days=payable_days,
        effective_balance_before=before,
        effective_balance_after=after,
        excluded_weekends=excluded_weekends,
        excluded_holidays=excluded_holidays,
        warnings=warnings,
        blocking_reasons=unique_blockers,
        policy=policy,
    )


def _raise_first_blocker(assessment: LeaveEligibilityResponse) -> None:
    if assessment.eligible:
        return
    reason = assessment.blocking_reasons[0]
    status = 409 if reason.code == "LEAVE_OVERLAP" else 400
    raise LeaveServiceError(reason.code, reason.message, status, reason.field, reason.details)


def _queue_leave_approval_email(db: Session, employee: Employee, request: LeaveRequest, leave_type: LeaveType) -> None:
    manager = db.query(Employee).filter(Employee.id == employee.manager_id).first() if employee.manager_id else None
    if not manager and employee.reporting_manager:
        ref = employee.reporting_manager.strip().lower()
        for candidate in db.query(Employee).filter(Employee.id != employee.id).all():
            full_name = f"{candidate.first_name} {candidate.last_name}".strip().lower()
            if ref in {full_name, candidate.work_email.lower()}:
                manager = candidate
                break
    if not manager:
        return
    enqueue_email(
        db,
        recipient=manager.work_email,
        template_name="manager_approval",
        idempotency_key=f"manager-approval:leave:{request.id}:{manager.id}",
        context={
            "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
            "request_type": f"{leave_type.name} leave",
            "request_summary": f"{request.start_date} to {request.end_date} ({request.total_days:g} working days)",
            "approval_url": f"{settings.FRONTEND_BASE_URL.rstrip('/')}/employee/approvals?leaveRequestId={request.id}",
        },
    )


def create_my_leave_request(
    db: Session,
    employee: Employee,
    payload: LeaveRequestInput,
    *,
    correlation_id: str | None = None,
) -> LeaveRequest:
    if not employee.is_active or employee.employment_status != "active":
        raise LeaveServiceError(
            "EMPLOYEE_NOT_ACTIVE",
            "Only active employees can submit leave requests.",
            403,
        )
    assessment = assess_my_leave_request(
        db,
        employee,
        LeaveAssessmentInput(
            leave_type_id=payload.leave_type_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            holiday_id=payload.holiday_id,
        ),
    )
    _raise_first_blocker(assessment)
    leave_type = _active_leave_type(db, payload.leave_type_id)

    if payload.action == "submit" and leave_type.is_paid:
        _, _, _, pending, available = effective_balance(
            db,
            employee.id,
            leave_type,
            payload.start_date.year,
            provision=True,
            lock=True,
        )
        if assessment.payable_working_days > available:
            message = (
                f"No balance available - {pending:g} days are pending approval."
                if available <= 0 and pending > 0
                else f"You only have {available:g} effective days available ({pending:g} days are pending approval)."
            )
            raise LeaveServiceError("INSUFFICIENT_EFFECTIVE_BALANCE", message, 400)

    now = datetime.utcnow()
    request = LeaveRequest(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_days=assessment.payable_working_days,
        holiday_id=payload.holiday_id,
        reason=payload.reason.strip(),
        status="draft" if payload.action == "draft" else "pending",
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    db.flush()
    log_audit(
        db,
        employee,
        action="leave.draft_saved" if payload.action == "draft" else "leave.submitted",
        entity_type="leave_request",
        entity_id=request.id,
        new_values={
            "employee_id": employee.id,
            "leave_type": leave_type.name,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "total_days": assessment.payable_working_days,
            "holiday_id": payload.holiday_id,
            "status": request.status,
        },
        reason=payload.reason.strip(),
        metadata={"correlation_id": correlation_id} if correlation_id else None,
    )
    if payload.action == "submit":
        _queue_leave_approval_email(db, employee, request, leave_type)
    db.commit()
    db.refresh(request)
    return request


def submit_my_leave_request(
    db: Session,
    employee: Employee,
    payload: LeaveRequestInput,
    *,
    correlation_id: str | None = None,
) -> SubmittedLeaveResult:
    submit_payload = payload.model_copy(update={"action": "submit"})
    request = create_my_leave_request(
        db, employee, submit_payload, correlation_id=correlation_id
    )
    serialized = serialize_leave_request(db, request, employee=employee)
    return SubmittedLeaveResult(
        request_id=request.id,
        request=serialized,
        authoritative_initial_status="pending",
        submitted_at=request.created_at,
        pending_approval_owner=serialized.pending_with,
        correlation_id=correlation_id,
    )


def update_my_leave_request(
    db: Session,
    employee: Employee,
    request_id: str,
    payload: LeaveRequestInput,
) -> LeaveRequest:
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.employee_id == employee.id,
    ).first()
    if not request:
        raise LeaveServiceError("LEAVE_REQUEST_NOT_FOUND", "Leave request not found.", 404)
    if request.status != "draft":
        raise LeaveServiceError("LEAVE_REQUEST_NOT_EDITABLE", "Only draft leave requests can be edited.")
    assessment = assess_my_leave_request(
        db,
        employee,
        LeaveAssessmentInput(
            leave_type_id=payload.leave_type_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            holiday_id=payload.holiday_id,
        ),
        exclude_request_id=request.id,
    )
    _raise_first_blocker(assessment)
    leave_type = _active_leave_type(db, payload.leave_type_id)
    if payload.action == "submit" and leave_type.is_paid:
        _, _, _, pending, available = effective_balance(
            db, employee.id, leave_type, payload.start_date.year, provision=True, lock=True
        )
        if assessment.payable_working_days > available:
            raise LeaveServiceError(
                "INSUFFICIENT_EFFECTIVE_BALANCE",
                f"You only have {available:g} effective days available ({pending:g} days are pending approval).",
            )
    old_values = serialize_leave_request(db, request, employee=employee).model_dump(mode="json")
    request.leave_type_id = leave_type.id
    request.start_date = payload.start_date
    request.end_date = payload.end_date
    request.total_days = assessment.payable_working_days
    request.holiday_id = payload.holiday_id
    request.reason = payload.reason.strip()
    request.status = "draft" if payload.action == "draft" else "pending"
    request.updated_at = datetime.utcnow()
    log_audit(
        db,
        employee,
        action="leave.updated" if payload.action == "draft" else "leave.submitted",
        entity_type="leave_request",
        entity_id=request.id,
        old_values=old_values,
        new_values=serialize_leave_request(db, request, employee=employee).model_dump(mode="json"),
        reason=payload.reason.strip(),
    )
    if payload.action == "submit":
        _queue_leave_approval_email(db, employee, request, leave_type)
    db.commit()
    db.refresh(request)
    return request


def delete_my_leave_draft(db: Session, employee: Employee, request_id: str) -> None:
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.employee_id == employee.id,
    ).first()
    if not request:
        raise LeaveServiceError("LEAVE_REQUEST_NOT_FOUND", "Leave request not found.", 404)
    if request.status != "draft":
        raise LeaveServiceError("LEAVE_REQUEST_NOT_DELETABLE", "Only draft leave requests can be deleted.")
    old_values = serialize_leave_request(db, request, employee=employee).model_dump(mode="json")
    log_audit(
        db,
        employee,
        action="leave.cancelled",
        entity_type="leave_request",
        entity_id=request.id,
        old_values=old_values,
        reason="Employee deleted draft leave request.",
    )
    db.delete(request)
    db.commit()


def withdraw_my_leave_request(db: Session, employee: Employee, request_id: str) -> LeaveRequest:
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.employee_id == employee.id,
    ).first()
    if not request:
        raise LeaveServiceError("LEAVE_REQUEST_NOT_FOUND", "Leave request not found.", 404)
    if request.status != "pending":
        raise LeaveServiceError("LEAVE_REQUEST_NOT_WITHDRAWABLE", "Only pending leave requests can be withdrawn.")
    old_values = serialize_leave_request(db, request, employee=employee).model_dump(mode="json")
    request.status = "cancelled"
    request.updated_at = datetime.utcnow()
    log_audit(
        db,
        employee,
        action="leave.withdrawn",
        entity_type="leave_request",
        entity_id=request.id,
        old_values=old_values,
        new_values={"status": request.status, "updated_at": request.updated_at},
        reason="Employee withdrew pending leave request.",
    )
    db.commit()
    db.refresh(request)
    return request


def get_my_leave_request_by_id(
    db: Session,
    employee: Employee,
    request_id: str,
    *,
    as_of: datetime | None = None,
) -> OwnerScopedLeaveRequestStatus:
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.employee_id == employee.id,
    ).first()
    if not request:
        # The same response covers nonexistent records and records owned by
        # another employee, preventing ownership disclosure.
        raise LeaveServiceError(
            "LEAVE_REQUEST_NOT_FOUND",
            "Leave request not found.",
            404,
        )
    serialized = serialize_leave_request(db, request, employee=employee)
    return OwnerScopedLeaveRequestStatus(
        request_id=request.id,
        status=request.status,
        request=serialized,
        as_of=as_of or datetime.utcnow(),
    )
