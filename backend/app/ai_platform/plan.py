"""Strict candidate plans, trusted validated plans, and Phase 1 policy."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, ValidationInfo, field_validator, model_validator

from app.ai_platform.authorization import AuthorizationDecision, AuthorizationState
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.contracts import (
    FailurePolicy,
    PlanSafetyFlag,
    PlanSource,
    PlatformContract,
    TraceMetadataItem,
)
from app.ai_platform.errors import (
    AuthorizationDeniedError,
    CapabilityInputInvalidError,
    InvalidPlanError,
    WriteCapabilityProhibitedError,
)

ScalarArgument: TypeAlias = str | int | float | bool | date | datetime | None
_FORBIDDEN_ARGUMENT_NAMES = {
    "actor", "actor_id", "actor_role", "authorization", "authorization_state",
    "permission", "permissions", "db", "db_session", "session", "url", "endpoint",
    "sql", "module", "module_name", "function", "function_name", "callable", "executor",
}
_VALIDATED_PLAN_CONTEXT = object()


class PlanArgument(PlatformContract):
    """A bounded scalar candidate value; still untrusted until input validation."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    value: ScalarArgument

    @field_validator("name")
    @classmethod
    def safe_name(cls, value: str) -> str:
        if value in _FORBIDDEN_ARGUMENT_NAMES:
            raise ValueError("argument name is reserved by the platform")
        return value

    @field_validator("value")
    @classmethod
    def bounded_value(cls, value: ScalarArgument) -> ScalarArgument:
        if isinstance(value, str) and (not value or len(value) > 500):
            raise ValueError("string argument must be bounded")
        return value


class CandidatePlanStep(PlatformContract):
    step_id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    capability_id: str = Field(min_length=5, max_length=120, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    capability_version: int = Field(gt=0, le=999)
    arguments: tuple[PlanArgument, ...] = Field(default=(), max_length=32)
    depends_on: tuple[str, ...] = Field(default=(), max_length=3)
    expected_result_type: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    failure_policy: FailurePolicy = FailurePolicy.STOP
    authorization_state: AuthorizationState = AuthorizationState.PENDING

    @field_validator("arguments")
    @classmethod
    def unique_arguments(cls, values: tuple[PlanArgument, ...]) -> tuple[PlanArgument, ...]:
        names = [item.name for item in values]
        if len(names) != len(set(names)):
            raise ValueError("argument names must be unique")
        return values

    @field_validator("depends_on")
    @classmethod
    def unique_dependencies(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("dependencies must be unique")
        return values

    @field_validator("authorization_state")
    @classmethod
    def pending_only(cls, value: AuthorizationState) -> AuthorizationState:
        if value is not AuthorizationState.PENDING:
            raise ValueError("candidate plan authorization must remain pending")
        return value

    def argument_dict(self) -> dict[str, ScalarArgument]:
        """Return candidate values for schema validation, never for direct execution."""
        return {item.name: item.value for item in self.arguments}


class CandidatePlan(PlatformContract):
    """Non-executable proposal constrained to at most three depth-one steps."""

    plan_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    intent: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    steps: tuple[CandidatePlanStep, ...] = Field(min_length=1, max_length=3)
    maximum_duration_ms: int = Field(gt=0, le=30_000)
    source: PlanSource
    trace_metadata: tuple[TraceMetadataItem, ...] = Field(default=(), max_length=16)
    safety_flags: tuple[PlanSafetyFlag, ...] = Field(default=(), max_length=8)
    _interpreter_trusted: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def valid_graph(self) -> "CandidatePlan":
        step_map = {step.step_id: step for step in self.steps}
        if len(step_map) != len(self.steps):
            raise ValueError("step IDs must be unique")
        for step in self.steps:
            if step.step_id in step.depends_on:
                raise ValueError("plan contains a cycle")
            if any(dependency not in step_map for dependency in step.depends_on):
                raise ValueError("dependency references an unknown step")

        visiting: set[str] = set()
        depths_by_step: dict[str, int] = {}

        def visit(step_id: str) -> int:
            if step_id in visiting:
                raise ValueError("plan contains a cycle")
            if step_id in depths_by_step:
                return depths_by_step[step_id]
            visiting.add(step_id)
            depths = [visit(dep) + 1 for dep in step_map[step_id].depends_on]
            visiting.remove(step_id)
            depth = max(depths, default=0)
            if depth > 1:
                raise ValueError("plan execution depth cannot exceed one")
            depths_by_step[step_id] = depth
            return depth

        for identifier in step_map:
            visit(identifier)
        return self

    @property
    def is_interpreter_trusted(self) -> bool:
        return self._interpreter_trusted


class ValidatedPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True)

    step_id: str
    capability_id: str
    capability_version: int
    validated_input: BaseModel
    expected_output_model: type[BaseModel]
    depends_on: tuple[str, ...]
    failure_policy: FailurePolicy
    preliminary_authorization: AuthorizationDecision

    @model_validator(mode="after")
    def authorization_allowed(self) -> "ValidatedPlanStep":
        if not self.preliminary_authorization.allowed:
            raise ValueError("validated steps require preliminary authorization")
        return self


class ValidatedPlan(BaseModel):
    """Immutable plan constructible only through the trusted Phase 1 validator."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True)

    plan_id: str
    intent: str
    steps: tuple[ValidatedPlanStep, ...]
    maximum_duration_ms: int
    source: PlanSource
    trace_metadata: tuple[TraceMetadataItem, ...] = ()
    _validator_trusted: bool = PrivateAttr(default=False)
    _validation_profile: str = PrivateAttr(default="")

    @model_validator(mode="after")
    def trusted_construction(self, info: ValidationInfo) -> "ValidatedPlan":
        context_trusted = bool(
            info.context and info.context.get("plan_validator") is _VALIDATED_PLAN_CONTEXT
        )
        if not context_trusted and not self._validator_trusted:
            raise ValueError("ValidatedPlan must be created by the trusted plan validator")
        return self

    @property
    def is_validator_trusted(self) -> bool:
        return self._validator_trusted

    @property
    def validation_profile(self) -> str:
        return self._validation_profile


def _build_validated_plan(
    *,
    plan: CandidatePlan,
    steps: tuple[ValidatedPlanStep, ...],
    validation_profile: str,
) -> ValidatedPlan:
    validated = ValidatedPlan.model_validate({
        "plan_id": plan.plan_id,
        "intent": plan.intent,
        "steps": steps,
        "maximum_duration_ms": plan.maximum_duration_ms,
        "source": plan.source,
        "trace_metadata": plan.trace_metadata,
    }, context={"plan_validator": _VALIDATED_PLAN_CONTEXT})
    object.__setattr__(validated, "_validator_trusted", True)
    object.__setattr__(validated, "_validation_profile", validation_profile)
    return validated


def validate_phase1_plan(plan: CandidatePlan, registry: CapabilityRegistry) -> ValidatedPlan:
    """Resolve and validate a read-only Phase 1 plan.

    Candidate plans are never executable. This is the sole Platform 1A trusted
    construction path for ``ValidatedPlan``.
    """

    if not isinstance(plan, CandidatePlan):
        raise InvalidPlanError("A strict candidate plan is required.")
    validated_steps: list[ValidatedPlanStep] = []
    for step in plan.steps:
        definition = registry.resolve(step.capability_id, step.capability_version, production=True)
        if not definition.is_read_only:
            raise WriteCapabilityProhibitedError("Only read capabilities are permitted in Platform Phase 1.")
        try:
            validated_input = definition.input_model.model_validate(step.argument_dict(), strict=True)
        except ValidationError as exc:
            raise CapabilityInputInvalidError("Capability arguments did not match the registered input contract.") from exc
        if step.expected_result_type != definition.output_model.__name__:
            raise InvalidPlanError("The expected result type does not match the registered capability output.")
        decision = definition.authorization_policy(validated_input)
        if not isinstance(decision, AuthorizationDecision) or not decision.allowed:
            raise AuthorizationDeniedError("The capability is not authorized.")
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
    return _build_validated_plan(
        plan=plan,
        steps=tuple(validated_steps),
        validation_profile="platform_1a",
    )
