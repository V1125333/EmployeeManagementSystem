"""Thin execution bridge for validator-attested Platform 1C plans."""

from __future__ import annotations

from pydantic import BaseModel

from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.errors import InvalidPlanError
from app.ai_platform.execution import CapabilityExecutionContext
from app.ai_platform.executor import CapabilityExecutionOutcome, execute_capability
from app.ai_platform.plan import ValidatedPlan


class ValidatedPlanExecutionOutcome(BaseModel):
    model_config = {"extra": "forbid", "frozen": True, "arbitrary_types_allowed": True}

    plan_id: str
    steps: tuple[CapabilityExecutionOutcome, ...]


def execute_validated_plan(
    plan: ValidatedPlan,
    registry: CapabilityRegistry,
    context: CapabilityExecutionContext,
    db: object,
) -> ValidatedPlanExecutionOutcome:
    """Execute only attested, independent steps through the existing executor."""

    if (
        not isinstance(plan, ValidatedPlan)
        or not plan.is_validator_trusted
        or plan.validation_profile != "platform_1c"
    ):
        raise InvalidPlanError("Only a Platform 1C validator-attested plan can be executed.")
    if context.plan_id != plan.plan_id:
        raise InvalidPlanError("Execution context does not match the validated plan.")
    if any(step.depends_on for step in plan.steps):
        raise InvalidPlanError("Result chaining is not supported by the Platform executor.")
    outcomes = tuple(
        execute_capability(
            registry,
            step.capability_id,
            step.capability_version,
            step.validated_input,
            context.model_copy(update={"step_id": step.step_id}),
            db,
        )
        for step in plan.steps
    )
    return ValidatedPlanExecutionOutcome(plan_id=plan.plan_id, steps=outcomes)
