"""Platform 1D contracts, grounding, composition, parity, and orchestration tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.leave_balance_tool import get_my_leave_balance
from app.ai_platform.capabilities.leave import (
    LeaveBalanceCapabilityEntry, LeaveBalanceCapabilityOutput, validate_leave_balance_result,
)
from app.ai_platform.compatibility import (
    legacy_balance_answer, to_leave_balance_result_card, to_legacy_ai_chat_response,
)
from app.ai_platform.contracts import Availability, DataClassification
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.errors import (
    AuthorizationDeniedError, CapabilityExecutionError, CapabilityResultInvalidError,
    CapabilityTimeoutError, ClarificationRequiredError, GroundingFailureError, InvalidPlanError,
)
from app.ai_platform.execution import ExecutionPrincipal
from app.ai_platform.grounding import (
    ClaimType, GroundedClaim, ValidatedGrounding, extract_leave_balance_claims,
    validate_grounding,
)
from app.ai_platform.interpreter import InterpreterRequest, interpret_employee_request
from app.ai_platform.orchestrator import run_platform_request
from app.ai_platform.plan_validator import validate_candidate_plan
from app.ai_platform.platform_registry import PLATFORM_REGISTRY, build_platform_registry
from app.ai_platform.platform_request import PlatformRequest
from app.ai_platform.platform_response import (
    PlatformResponse, PlatformResponseStatus, PlatformSafeError, verify_platform_response,
)
from app.ai_platform.response_composer import compose_leave_balance_response
from app.ai_platform.result import ResultAvailability, ValidatedCapabilityResult
from app.ai_platform.trace import AIRequestTrace, TraceEvent, TraceOutcome, TraceStage
from app.core.authentication import AuthenticatedPrincipal, LEAVE_BALANCE_SELF_PERMISSION
from app.core.database import Base
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.organization import Department, Designation
from app.schemas.ai import GetMyLeaveBalanceInput


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def state():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Department.__table__, Designation.__table__, Employee.__table__, LeaveType.__table__,
        LeaveBalance.__table__, LeaveRequest.__table__,
    ])
    db = sessionmaker(bind=engine)()
    employee = Employee(
        id="ground-employee-1", first_name="Asha", last_name="Rao",
        work_email="asha.ground@example.com", phone="1000000000", workforce_type="full_time",
        role="employee", employment_status="active", is_active=True, account_locked=False,
        gender="female", joining_date=date(2025, 1, 1),
    )
    db.add_all([
        employee,
        LeaveType(id="ground-cl", name="Casual Leave", code="CL", default_days_per_year=12,
                  is_paid=True, is_active=True, sort_order=1),
        LeaveType(id="ground-sl", name="Sick Leave", code="SL", default_days_per_year=10,
                  is_paid=True, is_active=True, sort_order=2),
    ])
    db.commit()
    auth = AuthenticatedPrincipal(
        employee_id=employee.id, email=employee.work_email, role="employee", status="active",
        permissions=frozenset({LEAVE_BALANCE_SELF_PERMISSION}), token_id="ground-token-001",
    )
    principal = ExecutionPrincipal.from_authenticated(auth)
    yield {"db": db, "employee": employee, "auth": auth, "principal": principal}
    db.close(); engine.dispose()


def request(state, message="What is my leave balance?", **changes):
    values = dict(
        request_id="request-ground-001", correlation_id="correlation-ground-001",
        conversation_id="conversation-ground-001", principal=state["principal"], message=message,
        locale="en-US", timezone="UTC", received_at=datetime.now(timezone.utc),
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    values.update(changes)
    return PlatformRequest(**values)


def plan_for(state, message="What is my leave balance?"):
    interpreted = interpret_employee_request(InterpreterRequest(message=message), state["principal"], PLATFORM_REGISTRY)
    return validate_candidate_plan(interpreted.candidate_plan, PLATFORM_REGISTRY, state["principal"], state["db"])


def output(*balances, warnings=()):
    return LeaveBalanceCapabilityOutput(
        status="available", as_of=NOW, year=2026, balances=balances, warnings=warnings,
    )


def sick(available=7.0, used=2.0, pending=1.0, *, source="stored_balance"):
    return LeaveBalanceCapabilityEntry(
        leave_type="Sick Leave", code="SL", total=10.0, available=available,
        used=used, pending=pending, source=source,
    )


def grounded(state, capability_output=None, message="Show my sick leave balance"):
    plan = plan_for(state, message)
    result = validate_leave_balance_result(capability_output or output(sick()))
    claims = extract_leave_balance_claims(result)
    return plan, result, claims, validate_grounding(plan, (result,), claims)


def minimal_trace(outcome=TraceOutcome.FAILED):
    now = datetime.now(timezone.utc)
    event = TraceEvent(stage=TraceStage.REQUEST, started_at=now, completed_at=now,
                       latency_ms=0, outcome=TraceOutcome.SUCCEEDED)
    return AIRequestTrace(request_id="request-ground-001", conversation_id="conversation-ground-001",
                          actor_reference="a" * 32, events=(event,), final_outcome=outcome)


def test_platform_request_accepts_only_trusted_bounded_internal_identity(state):
    valid = request(state)
    assert valid.principal.employee_id == state["employee"].id
    serialized = valid.model_dump_json().lower()
    assert "bearer " not in serialized and "authorization" not in serialized and "jwt" not in serialized
    forged = ExecutionPrincipal.model_construct(
        employee_id="other", email="other@example.com", role="admin", status="active",
        permissions=frozenset(), token_id="forged-token", organization_scope="reknew",
    )
    with pytest.raises(ValidationError):
        request(state, principal=forged)
    with pytest.raises(ValidationError):
        request(state, message="x" * 2001)
    with pytest.raises(ValidationError):
        request(state, deadline_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        PlatformRequest(**{**valid.model_dump(), "authorization": "Bearer secret"})


def test_platform_response_contract_rejects_unattested_completion_failure_cards_and_bad_clarification():
    with pytest.raises(ValidationError):
        PlatformResponse(
            request_id="request-ground-001", correlation_id="correlation-ground-001",
            conversation_id="conversation-ground-001", status=PlatformResponseStatus.COMPLETED,
            message="fabricated", grounded_claims=(), result_reference_ids=(),
            trace=minimal_trace(TraceOutcome.SUCCEEDED), completed_at=datetime.now(timezone.utc),
        )
    with pytest.raises(ValidationError):
        PlatformResponse(
            request_id="request-ground-001", correlation_id="correlation-ground-001",
            conversation_id="conversation-ground-001", status=PlatformResponseStatus.FAILED,
            message="failed", result_cards=({},), safe_error=PlatformSafeError(
                code="SAFE_FAILURE", classification="internal", message="failed"
            ), trace=minimal_trace(), completed_at=datetime.now(timezone.utc),
        )
    with pytest.raises(ValidationError):
        PlatformResponse(
            request_id="request-ground-001", correlation_id="correlation-ground-001",
            conversation_id="conversation-ground-001", status=PlatformResponseStatus.CLARIFICATION_REQUIRED,
            message="clarify", clarification="Which one? What dates?",
            trace=minimal_trace(), completed_at=datetime.now(timezone.utc),
        )


def test_valid_claims_are_complete_typed_and_source_bound(state):
    _, result, claims, validated = grounded(state)
    assert validated.is_grounding_trusted
    assert {claim.claim_type for claim in claims} >= {
        ClaimType.STATUS, ClaimType.AS_OF, ClaimType.YEAR, ClaimType.LEAVE_TYPE,
        ClaimType.TOTAL, ClaimType.AVAILABLE, ClaimType.USED, ClaimType.PENDING, ClaimType.UNIT,
    }
    assert all(claim.source_result_reference_id == result.reference.result_reference_id for claim in claims)
    with pytest.raises(ValidationError):
        ValidatedGrounding.model_validate(validated.model_dump())


@pytest.mark.parametrize("mutation", ["reference", "capability", "path", "value", "classification"])
def test_grounding_rejects_reference_capability_path_value_and_classification_mutation(state, mutation):
    plan, result, claims, _ = grounded(state)
    target = next(item for item in claims if item.claim_type is ClaimType.AVAILABLE)
    updates = {
        "reference": {"source_result_reference_id": "res_abcdefghijklmnop"},
        "capability": {"capability_version": 2},
        "path": {"source_field_paths": ("balances.0.manager_name",)},
        "value": {"rendered_value": "999"},
        "classification": {"data_classification": DataClassification.RESTRICTED},
    }[mutation]
    altered = tuple(target.model_copy(update=updates) if item is target else item for item in claims)
    with pytest.raises(GroundingFailureError):
        validate_grounding(plan, (result,), altered)


def test_grounding_rejects_missing_duplicate_unsupported_and_failed_result_claims(state):
    plan, result, claims, _ = grounded(state)
    with pytest.raises(GroundingFailureError):
        validate_grounding(plan, (result,), claims[:-1])
    with pytest.raises(GroundingFailureError):
        validate_grounding(plan, (result,), claims + (claims[-1].model_copy(update={"rendered_value": "other"}),))
    unsupported = claims[0].model_copy(update={"claim_type": "policy_explanation"})
    with pytest.raises(GroundingFailureError):
        validate_grounding(plan, (result,), (unsupported,) + claims[1:])
    missing = result.model_copy(update={"availability": ResultAvailability.MISSING, "output": None})
    with pytest.raises(GroundingFailureError):
        extract_leave_balance_claims(missing)


def test_single_balance_composition_matches_existing_message_and_card(state):
    _, _, _, validation = grounded(state)
    content = compose_leave_balance_response(validation, locale="en-US", timezone="UTC")
    assert content.message == "You have 7 days of Sick Leave available. Used: 2 days; pending: 1 days."
    assert content.result_cards[0].balances[0].available == 7.0
    assert not hasattr(content, "output") and not hasattr(content, "db")


@pytest.mark.parametrize("entry", [
    sick(0.0, 10.0, 0.0),
    sick(4.0, 2.0, 4.0),
    LeaveBalanceCapabilityEntry(leave_type="Maternity Leave", code="ML", total=0.0,
                                available="On request", used=0.0, pending=0.0, source="on_request"),
])
def test_composer_preserves_exhausted_pending_and_on_request_values(state, entry):
    message = "Show my sick leave balance" if entry.leave_type == "Sick Leave" else "Show my maternity leave balance"
    _, _, _, validation = grounded(state, output(entry), message)
    content = compose_leave_balance_response(validation, locale="en-US", timezone="UTC")
    expected_available = entry.available if isinstance(entry.available, str) else f"{entry.available:g}"
    assert expected_available in content.message
    assert content.result_cards[0].balances[0].pending == entry.pending


def test_all_balance_and_unavailable_warning_composition(state):
    plan = plan_for(state)
    all_result = validate_leave_balance_result(output(
        LeaveBalanceCapabilityEntry(leave_type="Casual Leave", code="CL", total=12.0,
                                    available=12.0, used=0.0, pending=0.0, source="policy_default"),
        sick(), warnings=("Balances reflect approved and pending leave.",),
    ))
    all_ground = validate_grounding(plan, (all_result,), extract_leave_balance_claims(all_result))
    content = compose_leave_balance_response(all_ground, locale="en-US", timezone="UTC")
    assert content.message == "I found 2 leave balances for 2026. The verified values are shown below."
    assert content.safe_warnings == ("Balances reflect approved and pending leave.",)
    unavailable = validate_leave_balance_result(LeaveBalanceCapabilityOutput(
        status="unavailable", as_of=NOW, year=2026, balances=(),
        warnings=("No leave balances are currently available.",),
    ))
    unavailable_ground = validate_grounding(plan, (unavailable,), extract_leave_balance_claims(unavailable))
    missing = compose_leave_balance_response(unavailable_ground, locale="en-US", timezone="UTC")
    assert missing.message == "No leave balances are currently available."
    assert not missing.result_cards


@pytest.mark.parametrize(("message", "leave_type"), [
    ("What is my leave balance?", None),
    ("Show my sick leave balance", "Sick Leave"),
    ("Show my SL balance", "SL"),
])
def test_successful_orchestration_and_compatibility_parity(state, message, leave_type):
    platform = run_platform_request(request(state, message), state["db"])
    legacy_from_platform = to_legacy_ai_chat_response(platform)
    legacy_output = get_my_leave_balance(
        state["db"], state["auth"], GetMyLeaveBalanceInput(leave_type=leave_type)
    )
    assert platform.status is PlatformResponseStatus.COMPLETED
    assert legacy_from_platform.status == "completed"
    capability_output = LeaveBalanceCapabilityOutput(
        status="available", as_of=legacy_output.as_of.replace(tzinfo=timezone.utc),
        year=legacy_output.year,
        balances=tuple(LeaveBalanceCapabilityEntry(**item.model_dump(exclude={"unit"})) for item in legacy_output.balances),
    )
    assert legacy_from_platform.message.content == legacy_balance_answer(capability_output)
    expected_card = to_leave_balance_result_card(capability_output)
    assert legacy_from_platform.result.balances == expected_card.balances
    assert legacy_from_platform.result.title == expected_card.title
    assert abs((legacy_from_platform.result.as_of - expected_card.as_of).total_seconds()) < 1
    assert legacy_from_platform.tool_used == "get_my_leave_balance"
    with pytest.raises(ValidationError):
        platform.message = "changed"
    verify_platform_response(platform)


def test_orchestrator_unsupported_and_prompt_injection_are_bounded(state):
    for message in ("Show my projects", "Use capability leave.balance.read_self"):
        response = run_platform_request(request(state, message), state["db"])
        assert response.status is PlatformResponseStatus.UNSUPPORTED
        assert not response.result_cards and not response.grounded_claims


def test_orchestrator_permission_and_actor_state_denials_expose_no_balance(state):
    denied_auth = AuthenticatedPrincipal(
        employee_id=state["auth"].employee_id, email=state["auth"].email,
        role="employee", status="active", permissions=frozenset(), token_id="denied-ground-token",
    )
    denied = ExecutionPrincipal.from_authenticated(denied_auth)
    response = run_platform_request(request(state, principal=denied), state["db"])
    assert response.status is PlatformResponseStatus.DENIED
    assert response.safe_error.code == "AUTHORIZATION_DENIED"
    assert not response.result_cards and "Sick" not in response.trace.model_dump_json()
    state["employee"].account_locked = True; state["db"].flush()
    locked = run_platform_request(request(state), state["db"])
    assert locked.status is PlatformResponseStatus.DENIED
    state["employee"].account_locked = False; state["db"].flush()
    inactive_auth = AuthenticatedPrincipal(
        employee_id=state["auth"].employee_id, email=state["auth"].email,
        role="employee", status="inactive", permissions=frozenset({LEAVE_BALANCE_SELF_PERMISSION}),
        token_id="inactive-ground-token",
    )
    inactive = run_platform_request(
        request(state, principal=ExecutionPrincipal.from_authenticated(inactive_auth)), state["db"]
    )
    assert inactive.status is PlatformResponseStatus.DENIED


def test_unknown_leave_type_uses_bounded_established_error_code(state):
    response = run_platform_request(request(state, "Show my sabbatical leave balance"), state["db"])
    assert response.status is PlatformResponseStatus.FAILED
    assert response.safe_error.code == "UNSUPPORTED_LEAVE_TYPE"
    assert response.message == "That leave type is not supported."
    assert not response.result_cards and "sabbatical" not in response.trace.model_dump_json().lower()


@pytest.mark.parametrize(("target", "error", "expected"), [
    ("validate_candidate_plan", InvalidPlanError("bad"), PlatformResponseStatus.FAILED),
    ("execute_validated_plan", CapabilityTimeoutError("late"), PlatformResponseStatus.TIMED_OUT),
    ("execute_validated_plan", CapabilityExecutionError("broken"), PlatformResponseStatus.FAILED),
    ("execute_validated_plan", CapabilityResultInvalidError("invalid"), PlatformResponseStatus.FAILED),
    ("validate_grounding", GroundingFailureError("mutated"), PlatformResponseStatus.FAILED),
])
def test_orchestrator_maps_plan_execution_result_and_grounding_failures(
    state, monkeypatch, target, error, expected
):
    import app.ai_platform.orchestrator as module
    monkeypatch.setattr(module, target, lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    response = run_platform_request(request(state), state["db"])
    assert response.status is expected
    assert response.safe_error is not None
    assert not response.result_cards and not response.grounded_claims
    assert str(error) not in response.message


def test_orchestrator_clarification_deadline_single_pass_and_trace_safety(state, monkeypatch):
    import app.ai_platform.orchestrator as module
    monkeypatch.setattr(module, "interpret_employee_request", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(ClarificationRequiredError("raw detail"))
    ))
    clarification = run_platform_request(request(state), state["db"])
    assert clarification.status is PlatformResponseStatus.CLARIFICATION_REQUIRED
    assert clarification.clarification.count("?") == 1
    past = datetime.now(timezone.utc) - timedelta(seconds=2)
    timed = run_platform_request(request(
        state, received_at=past, deadline_at=past + timedelta(seconds=1)
    ), state["db"])
    assert timed.status is PlatformResponseStatus.TIMED_OUT

    monkeypatch.undo()
    counts = {"interpret": 0, "execute": 0}
    original_interpret, original_execute = module.interpret_employee_request, module.execute_validated_plan
    def track_interpret(*args, **kwargs):
        counts["interpret"] += 1; return original_interpret(*args, **kwargs)
    def track_execute(*args, **kwargs):
        counts["execute"] += 1; return original_execute(*args, **kwargs)
    monkeypatch.setattr(module, "interpret_employee_request", track_interpret)
    monkeypatch.setattr(module, "execute_validated_plan", track_execute)
    response = run_platform_request(request(state), state["db"])
    assert counts == {"interpret": 1, "execute": 1}
    stages = [event.stage for event in response.trace.events]
    required = [
        TraceStage.REQUEST, TraceStage.INTERPRETATION, TraceStage.CANDIDATE_PLAN,
        TraceStage.PLAN_VALIDATION, TraceStage.PRELIMINARY_AUTHORIZATION,
        TraceStage.FINAL_AUTHORIZATION, TraceStage.CAPABILITY_EXECUTION,
        TraceStage.RESULT_VALIDATION, TraceStage.CLAIM_EXTRACTION,
        TraceStage.GROUNDING_VALIDATION, TraceStage.COMPOSITION, TraceStage.REQUEST_COMPLETION,
    ]
    assert all(stages.index(stage) < stages.index(required[i + 1]) for i, stage in enumerate(required[:-1]))
    serialized = response.trace.model_dump_json()
    for sensitive in (state["employee"].id, state["employee"].work_email, "Sick Leave", "ground-token"):
        assert sensitive not in serialized


def test_card_mutation_and_other_employee_claim_fail_closed(state):
    response = run_platform_request(request(state, "Show my sick leave balance"), state["db"])
    card = response.result_cards[0].model_copy(update={
        "balances": [response.result_cards[0].balances[0].model_copy(update={"available": 999.0})]
    })
    altered = response.model_copy(update={"result_cards": (card,)})
    with pytest.raises(GroundingFailureError):
        verify_platform_response(altered)
    with pytest.raises(GroundingFailureError):
        verify_platform_response(response.model_copy(update={
            "message": "Your manager says you have 99 days."
        }))
    other = response.grounded_claims[0].model_copy(update={"rendered_value": "Another employee has 99 days"})
    plan, result, claims, _ = grounded(state)
    with pytest.raises(GroundingFailureError):
        validate_grounding(plan, (result,), (other,) + claims[1:])


def test_disabled_and_killed_capability_fail_without_facts(state):
    definition = PLATFORM_REGISTRY.get("leave.balance.read_self", 1)
    disabled = CapabilityRegistry((definition.model_copy(update={
        "availability": Availability.DISABLED, "executor": None,
    }),))
    for registry in (build_platform_registry(kill_switch_active=True), disabled):
        response = run_platform_request(request(state), state["db"], registry)
        assert response.status is PlatformResponseStatus.FAILED
        assert not response.result_cards
