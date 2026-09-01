"""Fail-closed Platform 1C candidate-plan validation and authorization."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from app.ai_platform.authorization import AuthorizationDecision, AuthorizationState
from app.ai_platform.capabilities.leave import LEAVE_BALANCE_CAPABILITY_ID
from app.ai_platform.capabilities.manager import EMPLOYEE_MANAGER_CAPABILITY_ID
from app.ai_platform.capabilities.projects import PROJECT_ASSIGNMENTS_CAPABILITY_ID
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.contracts import OperationClass, PlanSource
from app.ai_platform.errors import (
    AuthorizationDeniedError,
    CapabilityInputInvalidError,
    InvalidPlanError,
    PlanCycleError,
    PlanTooLargeError,
    WriteCapabilityProhibitedError,
)
from app.ai_platform.execution import ExecutionPrincipal
from app.ai_platform.plan import (
    CandidatePlan,
    CandidatePlanStep,
    ValidatedPlan,
    ValidatedPlanStep,
    _build_validated_plan,
)

MAX_PHASE1_STEPS = 3
_ALLOWED_INTENTS = {
    LEAVE_BALANCE_CAPABILITY_ID: "read_leave_balance",
    EMPLOYEE_MANAGER_CAPABILITY_ID: "read_employee_manager",
    PROJECT_ASSIGNMENTS_CAPABILITY_ID: "list_current_project_assignments",
}


def _validate_graph(plan: CandidatePlan) -> None:
    steps = tuple(plan.steps)
    if not 1 <= len(steps) <= MAX_PHASE1_STEPS:
        raise PlanTooLargeError("A Platform Phase 1 plan must contain one to three steps.")
    if any(not isinstance(step, CandidatePlanStep) for step in steps):
        raise InvalidPlanError("Every candidate plan step must use the strict step contract.")
    step_map = {step.step_id: step for step in steps}
    if len(step_map) != len(steps):
        raise InvalidPlanError("Candidate plan step IDs must be unique.")
    for step in steps:
        if step.step_id in step.depends_on:
            raise PlanCycleError("The candidate plan contains a dependency cycle.")
        if any(dependency not in step_map for dependency in step.depends_on):
            raise InvalidPlanError("A candidate dependency references an unknown step.")

    visiting: set[str] = set()
    depths: dict[str, int] = {}

    def visit(step_id: str) -> int:
        if step_id in visiting:
            raise PlanCycleError("The candidate plan contains a dependency cycle.")
        if step_id in depths:
            return depths[step_id]
        visiting.add(step_id)
        depth = max((visit(item) + 1 for item in step_map[step_id].depends_on), default=0)
        visiting.remove(step_id)
        if depth > 1:
            raise InvalidPlanError("Plan execution depth cannot exceed one.")
        depths[step_id] = depth
        return depth

    for step_id in step_map:
        visit(step_id)
    if any(step.depends_on for step in steps):
        raise InvalidPlanError("Result chaining is not supported in Platform Phase 1.")


def validate_candidate_plan(
    plan: CandidatePlan,
    registry: CapabilityRegistry,
    principal: ExecutionPrincipal,
    db: object,
) -> ValidatedPlan:
    """Produce an immutable executable plan after all Phase 1 checks pass."""

    if not isinstance(plan, CandidatePlan):
        raise InvalidPlanError("A strict candidate plan is required.")
    if not plan.is_interpreter_trusted:
        raise InvalidPlanError("A deterministic interpreter-attested candidate plan is required.")
    if not isinstance(principal, ExecutionPrincipal) or not principal.is_application_trusted:
        raise AuthorizationDeniedError("A trusted authenticated principal is required.")
    _validate_graph(plan)
    if plan.source is not PlanSource.DETERMINISTIC:
        raise InvalidPlanError("Only deterministic plans are executable in Platform Phase 1.")
    if plan.safety_flags:
        raise InvalidPlanError("A plan containing interpreter safety flags cannot execute.")

    seen_capabilities: set[tuple[str, int]] = set()
    validated_steps: list[ValidatedPlanStep] = []
    total_timeout_ms = 0
    for step in plan.steps:
        if step.authorization_state is not AuthorizationState.PENDING:
            raise InvalidPlanError("Candidate plans cannot claim prior authorization.")
        definition = registry.resolve(
            step.capability_id,
            step.capability_version,
            production=True,
        )
        capability_key = definition.key
        if capability_key in seen_capabilities:
            raise InvalidPlanError("Duplicate capability combinations are not permitted.")
        seen_capabilities.add(capability_key)
        if definition.operation_class is not OperationClass.READ:
            raise WriteCapabilityProhibitedError(
                "Only registered read capabilities are permitted in Platform Phase 1."
            )
        expected_intent = _ALLOWED_INTENTS.get(definition.capability_id)
        if expected_intent is None or plan.intent != expected_intent:
            raise InvalidPlanError("The plan intent does not match the registered capability.")
        if step.expected_result_type != definition.output_model.__name__:
            raise InvalidPlanError("The expected result type does not match the capability output.")
        try:
            validated_input = definition.input_model.model_validate(
                step.argument_dict(),
                strict=True,
            )
        except ValidationError as exc:
            raise CapabilityInputInvalidError(
                "Capability arguments did not match the registered input contract."
            ) from exc
        try:
            decision = definition.authorization_policy(db, principal, validated_input)
        except Exception as exc:
            raise AuthorizationDeniedError("Preliminary capability authorization failed.") from exc
        if not isinstance(decision, AuthorizationDecision) or not decision.allowed:
            raise AuthorizationDeniedError("The candidate capability is not authorized.")
        total_timeout_ms += int(definition.timeout_seconds * 1000)
        validated_steps.append(ValidatedPlanStep(
            step_id=step.step_id,
            capability_id=definition.capability_id,
            capability_version=definition.version,
            validated_input=validated_input,
            expected_output_model=definition.output_model,
            depends_on=step.depends_on,
            failure_policy=step.failure_policy,
            preliminary_authorization=decision,
        ))
    if total_timeout_ms > plan.maximum_duration_ms:
        raise InvalidPlanError("The plan duration is smaller than its capability timeouts.")
    return _build_validated_plan(
        plan=plan,
        steps=tuple(validated_steps),
        validation_profile="platform_1c",
    )
