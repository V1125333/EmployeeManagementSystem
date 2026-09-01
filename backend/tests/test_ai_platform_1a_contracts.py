"""Platform 1A contract, registry, policy, result, error, and trace tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.ai_platform.authorization import (
    AuthorizationDecision,
    AuthorizationState,
    minimize_target_reference,
)
from app.ai_platform.capability import CapabilityDefinition
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.contracts import (
    ActorScope,
    AuditPolicy,
    Availability,
    ConfirmationRequirement,
    DataClassification,
    FailurePolicy,
    IdempotencyPolicy,
    OperationClass,
    PlanSource,
    PlatformContract,
    RetryPolicy,
    RiskClass,
)
from app.ai_platform.errors import (
    AuthorizationDeniedError,
    CapabilityInputInvalidError,
    DisabledCapabilityError,
    DuplicateCapabilityError,
    ErrorContextItem,
    PLATFORM_ERROR_TYPES,
    PlatformError,
    ShadowOnlyCapabilityError,
    UnknownCapabilityError,
    WriteCapabilityProhibitedError,
)
from app.ai_platform.execution import CapabilityExecutionContext, ExecutionPrincipal
from app.ai_platform.plan import (
    CandidatePlan,
    CandidatePlanStep,
    PlanArgument,
    ValidatedPlan,
    validate_phase1_plan,
)
from app.ai_platform.result import (
    CapabilityResultReference,
    Freshness,
    ResultAvailability,
    ResultValidationStatus,
    ValidatedCapabilityResult,
)
from app.ai_platform.trace import AIRequestTrace, TraceEvent, TraceOutcome, TraceStage


NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


class DummyInput(PlatformContract):
    query: str


class DummyOutput(PlatformContract):
    value: str


def executor(*_args):
    return DummyOutput(value="verified")


def validator(value):
    return value


def allow_policy(_input):
    return AuthorizationDecision.allow(
        reason_code="SELF_SCOPE_ALLOWED",
        evaluated_scope=ActorScope.SELF,
        policy_version="test-v1",
        target_reference_hash="a" * 32,
        evaluated_at=NOW,
    )


def deny_policy(_input):
    return AuthorizationDecision.deny(
        reason_code="SELF_SCOPE_DENIED",
        evaluated_scope=ActorScope.SELF,
        policy_version="test-v1",
        evaluated_at=NOW,
    )


def capability(
    capability_id: str = "test.profile.read_self",
    *, version: int = 1,
    operation_class: OperationClass = OperationClass.READ,
    risk: RiskClass = RiskClass.LOW,
    availability: Availability = Availability.ENABLED,
    executor_ref=executor,
    authorization_policy=allow_policy,
    kill_switch_active: bool = False,
    confirmation: ConfirmationRequirement = ConfirmationRequirement.NONE,
    idempotency: IdempotencyPolicy = IdempotencyPolicy.NONE,
) -> CapabilityDefinition:
    return CapabilityDefinition(
        capability_id=capability_id,
        version=version,
        description="Test-only read capability definition.",
        domain="test",
        operation_class=operation_class,
        risk=risk,
        input_model=DummyInput,
        output_model=DummyOutput,
        required_permissions=("test.profile.read.self",),
        actor_scope=ActorScope.SELF,
        allowed_target_scopes=(ActorScope.SELF,),
        executor=executor_ref,
        authorization_policy=authorization_policy,
        timeout_seconds=2.0,
        retry_policy=RetryPolicy.NONE,
        idempotency_policy=idempotency,
        confirmation_requirement=confirmation,
        audit_policy=AuditPolicy.STANDARD,
        data_classification=DataClassification.INTERNAL,
        result_validator=validator,
        postcondition_validator=validator,
        kill_switch_active=kill_switch_active,
        availability=availability,
    )


def step(
    step_id: str = "read_profile",
    *, capability_id: str = "test.profile.read_self",
    version: int = 1,
    depends_on: tuple[str, ...] = (),
    arguments: tuple[PlanArgument, ...] | None = None,
    authorization_state: AuthorizationState = AuthorizationState.PENDING,
) -> CandidatePlanStep:
    return CandidatePlanStep(
        step_id=step_id,
        capability_id=capability_id,
        capability_version=version,
        arguments=arguments if arguments is not None else (PlanArgument(name="query", value="mine"),),
        depends_on=depends_on,
        expected_result_type="DummyOutput",
        failure_policy=FailurePolicy.STOP,
        authorization_state=authorization_state,
    )


def plan(*steps: CandidatePlanStep) -> CandidatePlan:
    return CandidatePlan(
        plan_id="plan_test_001",
        intent="read_profile",
        steps=steps or (step(),),
        maximum_duration_ms=5000,
        source=PlanSource.TEST,
    )


def test_valid_read_capability_definition_is_immutable():
    definition = capability()
    assert definition.is_read_only
    with pytest.raises(ValidationError):
        definition.version = 2


@pytest.mark.parametrize("changes", [
    {"capability_id": "/api/v1/users"},
    {"capability_id": "not-dotted"},
    {"version": 0},
    {"timeout_seconds": 0},
])
def test_capability_definition_rejects_invalid_identity_version_and_timeout(changes):
    values = capability().model_dump()
    values.update(changes)
    with pytest.raises(ValidationError):
        CapabilityDefinition.model_validate(values)


def test_enabled_capability_requires_callable_executor_and_unknown_fields_fail():
    with pytest.raises(ValidationError):
        capability(executor_ref=None)
    values = capability().model_dump()
    values["module_name"] = "evil.module"
    with pytest.raises(ValidationError):
        CapabilityDefinition.model_validate(values)


@pytest.mark.parametrize("operation,risk,confirmation", [
    (OperationClass.READ, RiskClass.HIGH, ConfirmationRequirement.NONE),
    (OperationClass.PREPARE, RiskClass.LOW, ConfirmationRequirement.NONE),
    (OperationClass.WRITE, RiskClass.LOW, ConfirmationRequirement.EXPLICIT),
    (OperationClass.WRITE, RiskClass.MODERATE, ConfirmationRequirement.NONE),
])
def test_invalid_operation_risk_and_write_confirmation_combinations_fail(operation, risk, confirmation):
    with pytest.raises(ValidationError):
        capability(operation_class=operation, risk=risk, confirmation=confirmation)


def test_registry_registration_lookup_listing_and_latest_are_deterministic():
    first = capability(version=1)
    second = capability(version=2)
    registry = CapabilityRegistry((second, first))
    assert registry.get(first.capability_id, 1) is first
    assert registry.resolve(first.capability_id) is second
    assert registry.is_read_only(first.capability_id, 1)
    assert registry.list_metadata() == (
        (first.capability_id, 1, Availability.ENABLED),
        (first.capability_id, 2, Availability.ENABLED),
    )


def test_registry_rejects_duplicates_unknown_ids_and_versions():
    definition = capability()
    with pytest.raises(DuplicateCapabilityError):
        CapabilityRegistry((definition, definition))
    registry = CapabilityRegistry((definition,))
    with pytest.raises(UnknownCapabilityError):
        registry.get("test.unknown.read_self", 1)
    with pytest.raises(UnknownCapabilityError):
        registry.get(definition.capability_id, 99)


def test_disabled_shadow_and_killed_capabilities_fail_production_resolution():
    disabled = capability("test.disabled.read_self", availability=Availability.DISABLED, executor_ref=None)
    shadow = capability("test.shadow.read_self", availability=Availability.SHADOW_ONLY)
    killed = capability("test.killed.read_self", kill_switch_active=True)
    registry = CapabilityRegistry((disabled, shadow, killed))
    with pytest.raises(DisabledCapabilityError):
        registry.resolve(disabled.capability_id, 1)
    with pytest.raises(ShadowOnlyCapabilityError):
        registry.resolve(shadow.capability_id, 1)
    assert registry.resolve(shadow.capability_id, 1, production=False) is shadow
    with pytest.raises(DisabledCapabilityError):
        registry.resolve(killed.capability_id, 1)


def test_registry_is_sealed_and_accepts_only_explicit_definitions():
    registry = CapabilityRegistry((capability(),))
    assert not hasattr(registry, "register")
    with pytest.raises((AttributeError, TypeError)):
        registry._definitions[("test.other.read_self", 1)] = capability()
    with pytest.raises(AttributeError):
        registry._definitions = {}
    with pytest.raises(TypeError):
        CapabilityRegistry(("evil.function",))


def test_valid_one_and_three_step_candidate_plans_are_non_executable():
    one = plan(step())
    three = plan(step("one"), step("two"), step("three"))
    assert len(one.steps) == 1 and len(three.steps) == 3
    assert not hasattr(one, "execute")


def test_candidate_plan_rejects_more_than_three_duplicate_missing_cycle_and_depth():
    with pytest.raises(ValidationError):
        plan(step("one"), step("two"), step("three"), step("four"))
    with pytest.raises(ValidationError):
        plan(step("same"), step("same"))
    with pytest.raises(ValidationError):
        plan(step("one", depends_on=("missing",)))
    with pytest.raises(ValidationError):
        plan(step("one", depends_on=("two",)), step("two", depends_on=("one",)))
    with pytest.raises(ValidationError):
        plan(step("one"), step("two", depends_on=("one",)), step("three", depends_on=("two",)))


def test_candidate_arguments_reject_arbitrary_control_fields_and_unknown_schema_fields():
    for name in ("url", "sql", "function_name", "db_session", "permissions"):
        with pytest.raises(ValidationError):
            PlanArgument(name=name, value="unsafe")
    values = step().model_dump()
    values["module"] = "evil"
    with pytest.raises(ValidationError):
        CandidatePlanStep.model_validate(values)


def test_candidate_plan_cannot_self_authorize():
    with pytest.raises(ValidationError):
        step(authorization_state=AuthorizationState.ALLOWED)


def test_phase1_validates_typed_input_and_creates_immutable_trusted_plan():
    validated = validate_phase1_plan(plan(step()), CapabilityRegistry((capability(),)))
    assert isinstance(validated, ValidatedPlan)
    assert validated.steps[0].validated_input == DummyInput(query="mine")
    with pytest.raises(ValidationError):
        validated.plan_id = "replacement"
    with pytest.raises(ValidationError):
        ValidatedPlan.model_validate(validated.model_dump())


def test_phase1_rejects_prepare_write_unknown_disabled_version_and_invalid_input():
    prepare = capability(
        "test.profile.prepare_self", operation_class=OperationClass.PREPARE,
        risk=RiskClass.MODERATE,
    )
    write = capability(
        "test.profile.write_self", operation_class=OperationClass.WRITE,
        risk=RiskClass.MODERATE, confirmation=ConfirmationRequirement.EXPLICIT,
    )
    for definition in (prepare, write):
        candidate = plan(step(capability_id=definition.capability_id))
        with pytest.raises(WriteCapabilityProhibitedError):
            validate_phase1_plan(candidate, CapabilityRegistry((definition,)))
    with pytest.raises(UnknownCapabilityError):
        validate_phase1_plan(plan(step(version=99)), CapabilityRegistry((capability(),)))
    disabled = capability(availability=Availability.DISABLED, executor_ref=None)
    with pytest.raises(DisabledCapabilityError):
        validate_phase1_plan(plan(step()), CapabilityRegistry((disabled,)))
    bad_args = (PlanArgument(name="unexpected", value="value"),)
    with pytest.raises(CapabilityInputInvalidError):
        validate_phase1_plan(plan(step(arguments=bad_args)), CapabilityRegistry((capability(),)))


def test_phase1_preliminary_authorization_denial_fails_closed():
    denied = capability(authorization_policy=deny_policy)
    with pytest.raises(AuthorizationDeniedError):
        validate_phase1_plan(plan(step()), CapabilityRegistry((denied,)))


def test_authorization_factories_create_allowed_and_denied_immutable_decisions():
    allowed = allow_policy(DummyInput(query="mine"))
    denied = deny_policy(DummyInput(query="mine"))
    assert allowed.allowed and not denied.allowed
    with pytest.raises(ValidationError):
        allowed.allowed = False
    with pytest.raises(ValidationError):
        AuthorizationDecision.model_validate(allowed.model_dump())


def test_authorization_reason_and_target_reference_are_bounded_and_minimized():
    hashed = minimize_target_reference("raw-employee-id", salt="application-salt")
    assert "raw-employee-id" not in hashed and len(hashed) == 32
    with pytest.raises(ValidationError):
        AuthorizationDecision.allow(
            reason_code="x" * 80,
            evaluated_scope=ActorScope.SELF,
            policy_version="v1",
            evaluated_at=NOW,
        )


def result_reference(**changes) -> CapabilityResultReference:
    values = {
        "result_reference_id": "res_abcdefghijklmnop",
        "capability_id": "test.profile.read_self",
        "capability_version": 1,
        "retrieved_at": NOW,
        "freshness": Freshness.FRESH,
        "source_service": "test.profile_service",
        "data_classification": DataClassification.INTERNAL,
        "validation_status": ResultValidationStatus.VALID,
    }
    values.update(changes)
    return CapabilityResultReference(**values)


def test_valid_typed_result_missing_state_and_opaque_reference():
    result = ValidatedCapabilityResult[DummyOutput](
        reference=result_reference(),
        availability=ResultAvailability.AVAILABLE,
        output=DummyOutput(value="verified"),
        permitted_field_paths=("value",),
    )
    missing = ValidatedCapabilityResult[DummyOutput](
        reference=result_reference(freshness=Freshness.UNAVAILABLE),
        availability=ResultAvailability.MISSING,
    )
    assert result.output.value == "verified" and missing.output is None
    with pytest.raises(ValidationError):
        result_reference(result_reference_id="employee-123")


def test_result_rejects_raw_object_invalid_output_invalid_reference_and_unknown_fields():
    class ORMLike:
        value = "raw"

    with pytest.raises(ValidationError):
        ValidatedCapabilityResult[DummyOutput](
            reference=result_reference(), availability=ResultAvailability.AVAILABLE,
            output=ORMLike(), permitted_field_paths=("value",),
        )
    with pytest.raises(ValidationError):
        ValidatedCapabilityResult[DummyOutput](
            reference=result_reference(), availability=ResultAvailability.AVAILABLE,
            output={"wrong": "shape"}, permitted_field_paths=("value",),
        )
    with pytest.raises(ValidationError):
        result_reference(validation_status=ResultValidationStatus.INVALID)
    values = result_reference().model_dump()
    values["raw_output"] = "secret"
    with pytest.raises(ValidationError):
        CapabilityResultReference.model_validate(values)


@dataclass(frozen=True)
class PrincipalStub:
    employee_id: str = "employee-1"
    email: str = "employee@example.com"
    role: str = "employee"
    status: str = "active"
    permissions: frozenset[str] = frozenset({"test.profile.read.self"})
    token_id: str = "token-id-123"
    organization_scope: str = "reknew"


def test_execution_context_requires_server_principal_and_excludes_runtime_session():
    principal = ExecutionPrincipal.from_authenticated(PrincipalStub())
    context = CapabilityExecutionContext(
        principal=principal,
        request_id="request-001",
        correlation_id="correlation-001",
        conversation_id="conversation-001",
        plan_id="plan-001",
        step_id="read_profile",
        deadline_at=NOW + timedelta(seconds=5),
    )
    dumped = context.model_dump(mode="json")
    assert "db" not in dumped and "authorization" not in dumped
    with pytest.raises(ValidationError):
        ExecutionPrincipal.model_validate(principal.model_dump())


def test_every_platform_error_has_stable_safe_code_and_secret_redaction():
    codes = set()
    for error_type in PLATFORM_ERROR_TYPES:
        error = error_type("Safe bounded message")
        safe = error.safe_dict()
        assert safe["code"] and safe["message"] == "Safe bounded message"
        assert safe["code"] not in codes
        codes.add(safe["code"])
    error = PlatformError("Bearer secret-token should never appear")
    assert "secret-token" not in error.safe_message
    with pytest.raises(ValidationError):
        ErrorContextItem(key="detail", value="Authorization: Bearer abc")


def trace_event(stage: TraceStage, *, start_offset: int, outcome: TraceOutcome = TraceOutcome.SUCCEEDED, error: str | None = None):
    started = NOW + timedelta(milliseconds=start_offset)
    return TraceEvent(
        stage=stage,
        started_at=started,
        completed_at=started + timedelta(milliseconds=10),
        latency_ms=10,
        outcome=outcome,
        safe_error_category=error,
    )


def test_trace_latency_outcome_and_forbidden_sensitive_fields_fail_closed():
    with pytest.raises(ValidationError):
        TraceEvent(
            stage=TraceStage.REQUEST, started_at=NOW,
            completed_at=NOW + timedelta(milliseconds=20), latency_ms=1,
            outcome=TraceOutcome.SUCCEEDED,
        )
    values = trace_event(TraceStage.REQUEST, start_offset=0).model_dump()
    values["authorization_header"] = "Bearer secret"
    with pytest.raises(ValidationError):
        TraceEvent.model_validate(values)


def test_in_memory_trace_hierarchy_represents_complete_read_flow():
    stages = (
        TraceStage.REQUEST, TraceStage.INTERPRETATION, TraceStage.PLAN_VALIDATION,
        TraceStage.AUTHORIZATION, TraceStage.CAPABILITY_EXECUTION,
        TraceStage.RESULT_VALIDATION, TraceStage.COMPOSITION,
    )
    events = tuple(trace_event(stage, start_offset=index * 10) for index, stage in enumerate(stages))
    trace = AIRequestTrace(
        request_id="request-001",
        conversation_id="conversation-001",
        actor_reference="a" * 32,
        plan_id="plan-test-001",
        events=events,
        final_outcome=TraceOutcome.SUCCEEDED,
    )
    dumped = trace.model_dump(mode="json")
    assert len(trace.events) == 7
    assert "prompt" not in dumped and "raw_output" not in dumped


def test_trace_supports_bounded_provider_usage_and_cost_without_prompt_content():
    event = TraceEvent(
        stage=TraceStage.INTERPRETATION,
        started_at=NOW,
        completed_at=NOW + timedelta(milliseconds=10),
        latency_ms=10,
        outcome=TraceOutcome.SUCCEEDED,
        provider_model="test-model",
        input_tokens=20,
        output_tokens=5,
        estimated_cost_usd=Decimal("0.000100"),
    )
    assert event.input_tokens == 20
