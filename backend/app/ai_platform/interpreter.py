"""Bounded deterministic interpreter for registry-backed Platform 1C plans."""

from __future__ import annotations

import re
import uuid
from enum import Enum

from pydantic import Field, model_validator

from app.ai.leave_intent import parse_leave_goal
from app.ai_platform.authorization import AuthorizationState
from app.ai_platform.capabilities.leave import (
    LEAVE_BALANCE_CAPABILITY_ID,
    LEAVE_BALANCE_CAPABILITY_VERSION,
)
from app.ai_platform.capabilities.manager import (
    EMPLOYEE_MANAGER_CAPABILITY_ID,
    EMPLOYEE_MANAGER_CAPABILITY_VERSION,
)
from app.ai_platform.capabilities.projects import (
    PROJECT_ASSIGNMENTS_CAPABILITY_ID,
    PROJECT_ASSIGNMENTS_CAPABILITY_VERSION,
)
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.contracts import (
    FailurePolicy,
    PlanSafetyFlag,
    PlanSource,
    PlatformContract,
    TraceMetadataItem,
)
from app.ai_platform.errors import UnknownCapabilityError
from app.ai_platform.execution import ExecutionPrincipal
from app.ai_platform.plan import CandidatePlan, CandidatePlanStep, PlanArgument


class InterpretationStatus(str, Enum):
    PLANNED = "planned"
    UNSUPPORTED = "unsupported"


class IntentConfidence(str, Enum):
    HIGH = "high"
    LOW = "low"


class InterpreterRequest(PlatformContract):
    message: str = Field(min_length=1, max_length=2_000)


class DeterministicInterpretation(PlatformContract):
    status: InterpretationStatus
    intent: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    confidence: IntentConfidence
    candidate_plan: CandidatePlan | None = None
    safety_flags: tuple[PlanSafetyFlag, ...] = Field(default=(), max_length=8)
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")

    @model_validator(mode="after")
    def status_matches_plan(self) -> "DeterministicInterpretation":
        if self.status is InterpretationStatus.PLANNED and self.candidate_plan is None:
            raise ValueError("planned interpretations require a candidate plan")
        if self.status is InterpretationStatus.UNSUPPORTED and self.candidate_plan is not None:
            raise ValueError("unsupported interpretations cannot contain a plan")
        return self


_CAPABILITY_OVERRIDE = re.compile(
    r"\b(?:capability|tool|function|module|endpoint|api[_ -]?path|version)\b"
    r"|\b[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}\b"
    r"|\bget_my_leave_balance\b",
    re.IGNORECASE,
)
_IDENTITY_OVERRIDE = re.compile(
    r"\b(?:employee|user|manager)[_-]?id\b|\bx-user-(?:id|email)\b"
    r"|\banother employee\b|\bsomeone else\b|\btheir leave\b"
    r"|\b(?:for|of)\s+[\w.+-]+@[\w.-]+\b"
    r"|\b(?:show|read|get)\b.{0,40}\b(?:for|of)\s+(?!me\b|my\b)[A-Z][a-z]+\b",
    re.IGNORECASE,
)
_EXECUTION_OVERRIDE = re.compile(
    r"\b(?:select|insert|update|delete|drop|alter)\b.{0,80}\b(?:from|into|table|where)\b"
    r"|/api/|https?://|\b(?:shell|powershell|command prompt)\b",
    re.IGNORECASE,
)
_UNSAFE_INSTRUCTION = re.compile(
    r"\bignore\b.{0,80}\b(?:instruction|system|developer|policy)\b"
    r"|\b(?:pretend|act)\s+(?:that\s+)?(?:i am|i'm|as)\s+(?:an?\s+)?(?:admin|hr|manager)\b"
    r"|\boverride\b.{0,80}\b(?:permission|authorization|system|policy)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_COMPARISON = re.compile(
    r"\b(?:compare|comparison|difference between|versus|vs\.?)\b",
    re.IGNORECASE,
)
_GENERAL_BALANCE = re.compile(
    r"\b(?:what(?:'s| is)|show|get|view|tell me)\s+(?:me\s+)?(?:all\s+)?my\s+leave\s+balances?\b",
    re.IGNORECASE,
)
_MANAGER_SELF = re.compile(
    r"^(?:who\s+is\s+my\s+(?:reporting\s+)?manager|who\s+do\s+i\s+report\s+to|"
    r"what\s+is\s+my\s+manager(?:'s|s)\s+name|"
    r"who\s+should\s+i\s+contact\s+as\s+my\s+manager)[?.!]*$",
    re.IGNORECASE,
)
_PROJECT_ASSIGNMENTS_SELF = re.compile(
    r"^(?:what\s+projects?\s+am\s+i\s+(?:currently\s+)?(?:working\s+on|on)|"
    r"show\s+(?:me\s+)?my\s+current\s+projects|"
    r"which\s+projects?\s+am\s+i\s+assigned\s+to|"
    r"what\s+are\s+my\s+active\s+project\s+allocations|"
    r"list\s+my\s+project\s+assignments)[?.!]*$",
    re.IGNORECASE,
)


def _safety_flags(message: str) -> tuple[PlanSafetyFlag, ...]:
    flags: list[PlanSafetyFlag] = []
    for pattern, flag in (
        (_CAPABILITY_OVERRIDE, PlanSafetyFlag.PROMPT_CAPABILITY_OVERRIDE),
        (_IDENTITY_OVERRIDE, PlanSafetyFlag.PROMPT_IDENTITY_OVERRIDE),
        (_EXECUTION_OVERRIDE, PlanSafetyFlag.PROMPT_EXECUTION_OVERRIDE),
        (_UNSAFE_INSTRUCTION, PlanSafetyFlag.UNSAFE_INSTRUCTION),
    ):
        if pattern.search(message):
            flags.append(flag)
    return tuple(flags)


def interpret_employee_request(
    request: InterpreterRequest,
    principal: ExecutionPrincipal,
    registry: CapabilityRegistry,
) -> DeterministicInterpretation:
    """Interpret one authenticated request without executing or authorizing it."""

    if not isinstance(principal, ExecutionPrincipal) or not principal.is_application_trusted:
        return DeterministicInterpretation(
            status=InterpretationStatus.UNSUPPORTED,
            intent="unsupported",
            confidence=IntentConfidence.LOW,
            safety_flags=(PlanSafetyFlag.PROMPT_IDENTITY_OVERRIDE,),
            reason_code="TRUSTED_PRINCIPAL_REQUIRED",
        )
    message = " ".join(request.message.strip().split())
    flags = _safety_flags(message)
    if flags:
        return DeterministicInterpretation(
            status=InterpretationStatus.UNSUPPORTED,
            intent="unsupported",
            confidence=IntentConfidence.LOW,
            safety_flags=flags,
            reason_code="UNSAFE_REQUEST_REJECTED",
        )

    if _MANAGER_SELF.fullmatch(message):
        try:
            definition = registry.get(
                EMPLOYEE_MANAGER_CAPABILITY_ID,
                EMPLOYEE_MANAGER_CAPABILITY_VERSION,
            )
        except UnknownCapabilityError:
            return DeterministicInterpretation(
                status=InterpretationStatus.UNSUPPORTED, intent="unsupported",
                confidence=IntentConfidence.LOW, reason_code="CAPABILITY_NOT_REGISTERED",
            )
        candidate = CandidatePlan(
            plan_id=f"plan_{uuid.uuid4().hex}", intent="read_employee_manager",
            steps=(CandidatePlanStep(
                step_id="read_employee_manager",
                capability_id=definition.capability_id,
                capability_version=definition.version,
                arguments=(), depends_on=(),
                expected_result_type=definition.output_model.__name__,
                failure_policy=FailurePolicy.STOP,
                authorization_state=AuthorizationState.PENDING,
            ),),
            maximum_duration_ms=min(int(definition.timeout_seconds * 1000), 30_000),
            source=PlanSource.DETERMINISTIC,
            trace_metadata=(
                TraceMetadataItem(key="interpreter_version", value="platform-1e-v1"),
                TraceMetadataItem(key="matched_intent", value="employee_manager_self"),
            ), safety_flags=(),
        )
        object.__setattr__(candidate, "_interpreter_trusted", True)
        return DeterministicInterpretation(
            status=InterpretationStatus.PLANNED, intent="read_employee_manager",
            confidence=IntentConfidence.HIGH, candidate_plan=candidate,
            reason_code="DETERMINISTIC_MATCH",
        )

    if _PROJECT_ASSIGNMENTS_SELF.fullmatch(message):
        try:
            definition = registry.get(
                PROJECT_ASSIGNMENTS_CAPABILITY_ID,
                PROJECT_ASSIGNMENTS_CAPABILITY_VERSION,
            )
        except UnknownCapabilityError:
            return DeterministicInterpretation(
                status=InterpretationStatus.UNSUPPORTED, intent="unsupported",
                confidence=IntentConfidence.LOW, reason_code="CAPABILITY_NOT_REGISTERED",
            )
        candidate = CandidatePlan(
            plan_id=f"plan_{uuid.uuid4().hex}",
            intent="list_current_project_assignments",
            steps=(CandidatePlanStep(
                step_id="list_current_project_assignments",
                capability_id=definition.capability_id,
                capability_version=definition.version,
                arguments=(), depends_on=(),
                expected_result_type=definition.output_model.__name__,
                failure_policy=FailurePolicy.STOP,
                authorization_state=AuthorizationState.PENDING,
            ),),
            maximum_duration_ms=min(int(definition.timeout_seconds * 1000), 30_000),
            source=PlanSource.DETERMINISTIC,
            trace_metadata=(
                TraceMetadataItem(key="interpreter_version", value="platform-1f-v1"),
                TraceMetadataItem(key="matched_intent", value="project_assignments_self"),
            ), safety_flags=(),
        )
        object.__setattr__(candidate, "_interpreter_trusted", True)
        return DeterministicInterpretation(
            status=InterpretationStatus.PLANNED,
            intent="list_current_project_assignments",
            confidence=IntentConfidence.HIGH,
            candidate_plan=candidate,
            reason_code="DETERMINISTIC_MATCH",
        )

    goal = parse_leave_goal(message)
    if goal.intent != "balance" or _UNSUPPORTED_COMPARISON.search(message):
        return DeterministicInterpretation(
            status=InterpretationStatus.UNSUPPORTED,
            intent="unsupported",
            confidence=IntentConfidence.LOW,
            reason_code="INTENT_NOT_REGISTERED",
        )
    try:
        definition = registry.get(
            LEAVE_BALANCE_CAPABILITY_ID,
            LEAVE_BALANCE_CAPABILITY_VERSION,
        )
    except UnknownCapabilityError:
        return DeterministicInterpretation(
            status=InterpretationStatus.UNSUPPORTED,
            intent="unsupported",
            confidence=IntentConfidence.LOW,
            reason_code="CAPABILITY_NOT_REGISTERED",
        )

    scoped_leave_type = None if _GENERAL_BALANCE.search(message) else goal.leave_type
    arguments = (
        (PlanArgument(name="leave_type", value=scoped_leave_type),)
        if scoped_leave_type
        else ()
    )
    candidate = CandidatePlan(
        plan_id=f"plan_{uuid.uuid4().hex}",
        intent="read_leave_balance",
        steps=(CandidatePlanStep(
            step_id="read_leave_balance",
            capability_id=definition.capability_id,
            capability_version=definition.version,
            arguments=arguments,
            depends_on=(),
            expected_result_type=definition.output_model.__name__,
            failure_policy=FailurePolicy.STOP,
            authorization_state=AuthorizationState.PENDING,
        ),),
        maximum_duration_ms=min(int(definition.timeout_seconds * 1000), 30_000),
        source=PlanSource.DETERMINISTIC,
        trace_metadata=(
            TraceMetadataItem(key="interpreter_version", value="platform-1c-v1"),
            TraceMetadataItem(key="matched_intent", value="leave_balance"),
        ),
        safety_flags=(),
    )
    object.__setattr__(candidate, "_interpreter_trusted", True)
    return DeterministicInterpretation(
        status=InterpretationStatus.PLANNED,
        intent="read_leave_balance",
        confidence=IntentConfidence.HIGH,
        candidate_plan=candidate,
        reason_code="DETERMINISTIC_MATCH",
    )
