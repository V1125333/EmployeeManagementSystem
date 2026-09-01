"""Focused and side-by-side tests for Platform 1B leave-balance execution."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import time

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.leave_balance_tool import AIToolException, get_my_leave_balance
from app.ai_platform.authorization import AuthorizationState
from app.ai_platform.capabilities.leave import (
    LEAVE_BALANCE_CAPABILITY_ID,
    LEAVE_BALANCE_CAPABILITY_VERSION,
    LeaveBalanceCapabilityEntry,
    LeaveBalanceCapabilityError,
    LeaveBalanceCapabilityInput,
    LeaveBalanceCapabilityOutput,
    authorize_leave_balance_self,
    execute_leave_balance_adapter,
    validate_leave_balance_result,
)
from app.ai_platform.compatibility import (
    legacy_balance_answer,
    to_leave_balance_result_card,
    to_legacy_leave_balance_output,
    to_legacy_tool_exception,
)
from app.ai_platform.contracts import ActorScope, Availability, DataClassification, OperationClass
from app.ai_platform.errors import (
    AuthorizationDeniedError,
    CapabilityExecutionError,
    CapabilityInputInvalidError,
    CapabilityResultInvalidError,
    CapabilityTimeoutError,
    DisabledCapabilityError,
    UnknownCapabilityError,
)
from app.ai_platform.execution import CapabilityExecutionContext, ExecutionPrincipal
from app.ai_platform.executor import execute_capability
from app.ai_platform.platform_registry import PLATFORM_REGISTRY, build_platform_registry
from app.ai_platform.result import ResultAvailability
from app.ai_platform.trace import TraceOutcome, TraceStage
from app.core.authentication import AuthenticatedPrincipal, LEAVE_BALANCE_SELF_PERMISSION
from app.core.database import Base
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.organization import Department, Designation
from app.schemas.ai import GetMyLeaveBalanceInput, GetMyLeaveBalanceOutput


@pytest.fixture()
def balance_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Department.__table__, Designation.__table__, Employee.__table__,
            LeaveType.__table__, LeaveBalance.__table__, LeaveRequest.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    employee = Employee(
        id="platform-employee-1",
        first_name="Asha",
        last_name="Rao",
        work_email="asha.platform@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        account_locked=False,
        gender="female",
        joining_date=date(2025, 1, 1),
    )
    leave_types = [
        LeaveType(
            id="platform-leave-cl", name="Casual Leave", code="CL",
            default_days_per_year=12, is_paid=True, is_active=True, sort_order=1,
        ),
        LeaveType(
            id="platform-leave-sl", name="Sick Leave", code="SL",
            default_days_per_year=10, is_paid=True, is_active=True, sort_order=2,
        ),
        LeaveType(
            id="platform-leave-ml", name="Maternity Leave", code="ML",
            default_days_per_year=180, is_paid=True, is_active=True, sort_order=3,
        ),
    ]
    db.add_all([employee, *leave_types])
    db.commit()
    principal = AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role="employee",
        status="active",
        permissions=frozenset({LEAVE_BALANCE_SELF_PERMISSION}),
        token_id="platform-token-001",
    )
    execution_principal = ExecutionPrincipal.from_authenticated(principal)
    context = CapabilityExecutionContext(
        principal=execution_principal,
        request_id="request-platform-001",
        correlation_id="correlation-platform-001",
        conversation_id="conversation-platform-001",
        plan_id="plan-platform-001",
        step_id="read_leave_balance",
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    yield {
        "db": db,
        "employee": employee,
        "leave_types": leave_types,
        "principal": principal,
        "execution_principal": execution_principal,
        "context": context,
    }
    db.close()
    engine.dispose()


def platform_execute(state, capability_input=None, registry=PLATFORM_REGISTRY):
    return execute_capability(
        registry,
        LEAVE_BALANCE_CAPABILITY_ID,
        LEAVE_BALANCE_CAPABILITY_VERSION,
        capability_input or LeaveBalanceCapabilityInput(),
        state["context"],
        state["db"],
    )


def legacy_execute(state, leave_type=None):
    return get_my_leave_balance(
        state["db"], state["principal"], GetMyLeaveBalanceInput(leave_type=leave_type)
    )


def adapter_output(state, leave_type=None):
    return execute_leave_balance_adapter(
        state["db"], state["context"], LeaveBalanceCapabilityInput(leave_type=leave_type)
    )


def test_registry_contains_only_correct_leave_balance_v1_metadata():
    assert len(PLATFORM_REGISTRY) == 3
    definition = PLATFORM_REGISTRY.resolve(LEAVE_BALANCE_CAPABILITY_ID, 1)
    assert definition.operation_class is OperationClass.READ
    assert definition.actor_scope is ActorScope.SELF
    assert definition.data_classification is DataClassification.CONFIDENTIAL
    assert definition.required_permissions == (LEAVE_BALANCE_SELF_PERMISSION,)
    assert definition.is_read_only
    assert PLATFORM_REGISTRY.list_metadata() == (
        ("employee.manager.read_self", 1, Availability.ENABLED),
        (LEAVE_BALANCE_CAPABILITY_ID, 1, Availability.ENABLED),
        ("project.assignments.list_self", 1, Availability.ENABLED),
    )


def test_input_accepts_empty_and_leave_type_but_rejects_identity_and_unknown_fields():
    assert LeaveBalanceCapabilityInput().leave_type is None
    assert LeaveBalanceCapabilityInput(leave_type="  Casual   Leave ").leave_type == "Casual Leave"
    for payload in (
        {"employee_id": "other"}, {"email": "other@example.com"},
        {"actor_role": "admin"}, {"permission": LEAVE_BALANCE_SELF_PERMISSION},
        {"leave_type": "Sick Leave", "unknown": True},
    ):
        with pytest.raises(ValidationError):
            LeaveBalanceCapabilityInput.model_validate(payload)


def test_self_authorization_allows_permission_and_denies_missing_or_inactive(balance_context):
    allowed = authorize_leave_balance_self(
        balance_context["db"], balance_context["execution_principal"], LeaveBalanceCapabilityInput()
    )
    assert allowed.allowed and allowed.evaluated_scope is ActorScope.SELF

    principal = balance_context["principal"]
    missing = ExecutionPrincipal.from_authenticated(
        AuthenticatedPrincipal(
            employee_id=principal.employee_id, email=principal.email,
            role=principal.role, status="active", permissions=frozenset(),
            token_id="missing-token-001",
        )
    )
    assert not authorize_leave_balance_self(balance_context["db"], missing, LeaveBalanceCapabilityInput()).allowed
    inactive = ExecutionPrincipal.from_authenticated(
        AuthenticatedPrincipal(
            employee_id=principal.employee_id, email=principal.email,
            role=principal.role, status="inactive",
            permissions=frozenset({LEAVE_BALANCE_SELF_PERMISSION}),
            token_id="inactive-token-001",
        )
    )
    assert not authorize_leave_balance_self(balance_context["db"], inactive, LeaveBalanceCapabilityInput()).allowed
    balance_context["employee"].account_locked = True
    balance_context["db"].flush()
    assert not authorize_leave_balance_self(
        balance_context["db"],
        balance_context["execution_principal"],
        LeaveBalanceCapabilityInput(),
    ).allowed
    balance_context["employee"].account_locked = False
    balance_context["db"].flush()


def test_generic_executor_reauthorizes_immediately_before_execution(balance_context):
    definition = PLATFORM_REGISTRY.get(LEAVE_BALANCE_CAPABILITY_ID, 1)
    calls = {"count": 0}

    def changing_policy(db, principal, capability_input):
        calls["count"] += 1
        decision = authorize_leave_balance_self(db, principal, capability_input)
        if calls["count"] == 2:
            return decision.deny(
                reason_code="STATE_CHANGED",
                evaluated_scope=ActorScope.SELF,
                policy_version="test-v1",
                evaluated_at=datetime.now(timezone.utc),
            )
        return decision

    registry = type(PLATFORM_REGISTRY)((definition.model_copy(update={"authorization_policy": changing_policy}),))
    with pytest.raises(AuthorizationDeniedError):
        platform_execute(balance_context, registry=registry)
    assert calls["count"] == 2


def test_executor_calls_existing_leave_service_and_maps_no_orm_objects(balance_context, monkeypatch):
    from app.ai import leave_balance_tool

    calls = {"count": 0}
    original = leave_balance_tool.get_my_leave_balances

    def tracked(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(leave_balance_tool, "get_my_leave_balances", tracked)
    outcome = platform_execute(balance_context)
    assert calls["count"] == 1
    assert outcome.result.availability is ResultAvailability.AVAILABLE
    assert isinstance(outcome.result.output, LeaveBalanceCapabilityOutput)
    assert all(isinstance(item, LeaveBalanceCapabilityEntry) for item in outcome.result.output.balances)
    dumped_context = balance_context["context"].model_dump(mode="json")
    assert "db" not in dumped_context and "session" not in dumped_context


def test_deadline_disabled_kill_switch_and_unknown_version_fail_closed(balance_context):
    expired = balance_context["context"].model_copy(
        update={"deadline_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
    )
    with pytest.raises(CapabilityTimeoutError):
        execute_capability(
            PLATFORM_REGISTRY, LEAVE_BALANCE_CAPABILITY_ID, 1,
            LeaveBalanceCapabilityInput(), expired, balance_context["db"],
        )
    definition = PLATFORM_REGISTRY.get(LEAVE_BALANCE_CAPABILITY_ID, 1)
    disabled = type(PLATFORM_REGISTRY)((definition.model_copy(update={"availability": Availability.DISABLED}),))
    with pytest.raises(DisabledCapabilityError):
        platform_execute(balance_context, registry=disabled)
    killed = build_platform_registry(kill_switch_active=True)
    with pytest.raises(DisabledCapabilityError):
        platform_execute(balance_context, registry=killed)
    with pytest.raises(UnknownCapabilityError):
        execute_capability(
            PLATFORM_REGISTRY, LEAVE_BALANCE_CAPABILITY_ID, 99,
            LeaveBalanceCapabilityInput(), balance_context["context"], balance_context["db"],
        )

    definition = PLATFORM_REGISTRY.get(LEAVE_BALANCE_CAPABILITY_ID, 1)
    original_executor = definition.executor

    def slow_executor(*args):
        time.sleep(0.01)
        return original_executor(*args)

    slow = type(PLATFORM_REGISTRY)((definition.model_copy(update={
        "executor": slow_executor,
        "timeout_seconds": 0.001,
    }),))
    with pytest.raises(CapabilityTimeoutError):
        platform_execute(balance_context, registry=slow)


def test_service_failure_is_safe_and_invalid_service_output_fails_validation(balance_context, monkeypatch):
    from app.ai import leave_balance_tool
    from app.ai_platform.capabilities import leave

    def fail(*_args, **_kwargs):
        raise RuntimeError("database password secret must not escape")

    monkeypatch.setattr(leave_balance_tool, "get_my_leave_balances", fail)
    with pytest.raises(CapabilityExecutionError) as caught:
        platform_execute(balance_context)
    assert "password" not in caught.value.safe_message
    assert caught.value.execution_trace.final_outcome is TraceOutcome.FAILED

    monkeypatch.setattr(
        leave,
        "get_my_leave_balance",
        lambda *_args, **_kwargs: SimpleNamespace(
            as_of=datetime.now(), year=2026,
            balances=[SimpleNamespace(
                leave_type="Casual Leave", code="CL", total=12.0,
                available=99.0, used=0.0, pending=0.0, source="policy_default",
            )],
        ),
    )
    with pytest.raises(CapabilityResultInvalidError):
        platform_execute(balance_context)


def test_result_validation_rejects_negative_duplicate_unknown_and_impossible_data():
    base = dict(
        leave_type="Casual Leave", code="CL", total=12.0,
        available=10.0, used=1.0, pending=1.0,
        source="stored_balance", unit="days",
    )
    valid = LeaveBalanceCapabilityEntry(**base)
    output = LeaveBalanceCapabilityOutput(
        status="available", as_of=datetime.now(timezone.utc), year=2026,
        balances=(valid,),
    )
    validated = validate_leave_balance_result(output)
    assert validated.reference.result_reference_id.startswith("res_")
    assert "Casual Leave" not in validated.reference.result_reference_id
    assert len(validated.permitted_field_paths) <= 64
    for changes in ({"total": -1.0}, {"available": 8.0}):
        with pytest.raises(ValidationError):
            LeaveBalanceCapabilityEntry(**{**base, **changes})
    with pytest.raises(ValidationError):
        LeaveBalanceCapabilityOutput(
            status="available", as_of=datetime.now(timezone.utc), year=2026,
            balances=(valid, valid),
        )
    with pytest.raises(ValidationError):
        LeaveBalanceCapabilityOutput.model_validate({
            "status": "available", "as_of": datetime.now(timezone.utc),
            "year": 2026, "balances": [base], "raw_employee": "forbidden",
        })


def test_missing_balance_data_is_explicitly_unavailable(balance_context, monkeypatch):
    from app.ai_platform.capabilities import leave

    monkeypatch.setattr(
        leave,
        "get_my_leave_balance",
        lambda *_args, **_kwargs: GetMyLeaveBalanceOutput(
            as_of=datetime(2026, 8, 2), year=2026, balances=[]
        ),
    )
    output = adapter_output(balance_context)
    assert output.status == "unavailable" and output.warnings
    result = validate_leave_balance_result(output)
    assert result.availability is ResultAvailability.UNAVAILABLE
    assert result.output is None


def assert_legacy_parity(legacy, platform):
    compatible = to_legacy_leave_balance_output(platform)
    assert compatible.year == legacy.year
    assert compatible.as_of.date() == legacy.as_of.date()
    assert compatible.balances == legacy.balances


def test_all_and_single_balance_paths_have_exact_data_card_and_message_parity(balance_context):
    for leave_type in (None, "Casual Leave", "sick", "ML"):
        legacy = legacy_execute(balance_context, leave_type)
        platform = adapter_output(balance_context, leave_type)
        assert_legacy_parity(legacy, platform)
        card = to_leave_balance_result_card(platform)
        assert card.title == "My leave balance"
        assert card.as_of.date() == legacy.as_of.date()
        assert card.balances == legacy.balances
        from app.ai.orchestrator import _balance_answer
        assert legacy_balance_answer(platform) == _balance_answer(legacy)


def test_policy_default_pending_exhausted_and_unusual_valid_balances_match(balance_context):
    db = balance_context["db"]
    employee = balance_context["employee"]
    casual = balance_context["leave_types"][0]
    current_year = datetime.utcnow().year
    db.add(LeaveBalance(
        employee_id=employee.id, leave_type_id=casual.id, year=current_year,
        total_days=12, used_days=9, carry_forward_days=0,
    ))
    db.add(LeaveRequest(
        employee_id=employee.id, leave_type_id=casual.id,
        start_date=date(current_year, 8, 10), end_date=date(current_year, 8, 11),
        total_days=2, status="pending", reason="test",
    ))
    db.commit()
    assert_legacy_parity(
        legacy_execute(balance_context, "Casual Leave"),
        adapter_output(balance_context, "Casual Leave"),
    )
    row = db.query(LeaveBalance).filter(LeaveBalance.leave_type_id == casual.id).one()
    row.used_days = 20  # unusual but valid historical state; availability remains clamped
    db.commit()
    platform = adapter_output(balance_context, "Casual Leave")
    assert platform.balances[0].available == 0.0
    assert_legacy_parity(legacy_execute(balance_context, "Casual Leave"), platform)


def test_unknown_type_error_contract_is_compatible(balance_context):
    with pytest.raises(AIToolException) as legacy_error:
        legacy_execute(balance_context, "Vacation Leave")
    with pytest.raises(LeaveBalanceCapabilityError) as platform_error:
        adapter_output(balance_context, "Vacation Leave")
    converted = to_legacy_tool_exception(platform_error.value)
    assert converted.error.code == legacy_error.value.error.code
    assert converted.error.message == legacy_error.value.error.message


def test_executor_trace_is_bounded_and_contains_no_balance_values(balance_context):
    outcome = platform_execute(balance_context)
    stages = [event.stage for event in outcome.trace.events]
    assert stages == [
        TraceStage.REQUEST,
        TraceStage.CAPABILITY_RESOLUTION,
        TraceStage.AUTHORIZATION,
        TraceStage.AUTHORIZATION,
        TraceStage.CAPABILITY_EXECUTION,
        TraceStage.RESULT_VALIDATION,
    ]
    serialized = outcome.trace.model_dump_json()
    assert outcome.result.reference.result_reference_id in serialized
    for forbidden in ("Casual Leave", "Sick Leave", "12.0", "asha.platform@example.com"):
        assert forbidden not in serialized


def test_spoofed_identity_cannot_enter_candidate_input_or_execution(balance_context):
    with pytest.raises(CapabilityInputInvalidError):
        execute_capability(
            PLATFORM_REGISTRY, LEAVE_BALANCE_CAPABILITY_ID, 1,
            {"employee_id": "another-employee"},
            balance_context["context"], balance_context["db"],
        )
