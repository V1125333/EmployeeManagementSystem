"""Deterministic claim extraction and fail-closed grounding for Platform 1D."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationInfo, model_validator

from app.ai_platform.capabilities.leave import (
    LEAVE_BALANCE_CAPABILITY_ID,
    LEAVE_BALANCE_CAPABILITY_VERSION,
    LeaveBalanceCapabilityInput,
    LeaveBalanceCapabilityOutput,
)
from app.ai_platform.capabilities.manager import (
    EMPLOYEE_MANAGER_CAPABILITY_ID, EMPLOYEE_MANAGER_CAPABILITY_VERSION,
    EmployeeManagerCapabilityOutput,
)
from app.ai_platform.capabilities.projects import (
    PROJECT_ASSIGNMENTS_CAPABILITY_ID, PROJECT_ASSIGNMENTS_CAPABILITY_VERSION,
    CurrentProjectAssignmentsCapabilityOutput,
)
from app.ai_platform.contracts import DataClassification, PlatformContract
from app.ai_platform.errors import GroundingFailureError
from app.ai_platform.plan import ValidatedPlan
from app.ai_platform.result import ResultAvailability, ValidatedCapabilityResult


class ClaimType(str, Enum):
    STATUS = "status"
    AS_OF = "as_of"
    YEAR = "year"
    LEAVE_TYPE = "leave_type"
    CODE = "code"
    TOTAL = "total"
    AVAILABLE = "available"
    USED = "used"
    PENDING = "pending"
    SOURCE = "source"
    UNIT = "unit"
    WARNING = "warning"
    MANAGER_NAME = "manager_name"
    JOB_TITLE = "job_title"
    DEPARTMENT = "department"
    WORK_EMAIL = "work_email"
    ASSIGNMENT_COUNT = "assignment_count"
    PROJECT_NAME = "project_name"
    PROJECT_STATUS = "project_status"
    ALLOCATION_ROLE = "allocation_role"
    ALLOCATION_PERCENTAGE = "allocation_percentage"
    START_DATE = "start_date"
    END_DATE = "end_date"
    PROJECT_MANAGER_NAME = "project_manager_name"
    TRUNCATED = "truncated"


class GroundedClaim(PlatformContract):
    claim_id: str = Field(min_length=12, max_length=64, pattern=r"^clm_[a-f0-9]{16,60}$")
    claim_type: ClaimType
    source_result_reference_id: str = Field(min_length=20, max_length=80, pattern=r"^res_[A-Za-z0-9_-]{16,76}$")
    capability_id: str = Field(min_length=5, max_length=120, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    capability_version: int = Field(gt=0, le=999)
    source_field_paths: tuple[str, ...] = Field(min_length=1, max_length=2)
    rendered_value: str = Field(min_length=1, max_length=160)
    data_classification: DataClassification
    display_label: str | None = Field(default=None, min_length=1, max_length=80)
    safe_qualifier: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def one_safe_source(self) -> "GroundedClaim":
        if len(self.source_field_paths) != 1:
            raise ValueError("Platform 1D claims require exactly one source field")
        path = self.source_field_paths[0]
        if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.\d+|\.[a-z][a-z0-9_]*)*", path):
            raise ValueError("claim source path is invalid")
        return self


_GROUNDING_CONTEXT = object()


class ValidatedGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True)

    plan_id: str
    claims: tuple[GroundedClaim, ...]
    result_reference_ids: tuple[str, ...]
    data_classification: DataClassification
    safe_warnings: tuple[str, ...] = ()
    _grounding_trusted: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def trusted_construction(self, info: ValidationInfo) -> "ValidatedGrounding":
        trusted = bool(info.context and info.context.get("grounding") is _GROUNDING_CONTEXT)
        if not trusted and not self._grounding_trusted:
            raise ValueError("Validated grounding must be created by the grounding validator")
        return self

    @property
    def is_grounding_trusted(self) -> bool:
        return self._grounding_trusted


_BALANCE_FIELDS: tuple[tuple[str, ClaimType], ...] = (
    ("leave_type", ClaimType.LEAVE_TYPE), ("code", ClaimType.CODE),
    ("total", ClaimType.TOTAL), ("available", ClaimType.AVAILABLE),
    ("used", ClaimType.USED), ("pending", ClaimType.PENDING),
    ("source", ClaimType.SOURCE), ("unit", ClaimType.UNIT),
)


def _render(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:g}"
    return " ".join(str(value).split())


def _claim(result: ValidatedCapabilityResult, kind: ClaimType, path: str, value: object) -> GroundedClaim:
    digest = hashlib.sha256(
        f"{result.reference.result_reference_id}:{path}:{kind.value}".encode("utf-8")
    ).hexdigest()[:24]
    return GroundedClaim(
        claim_id=f"clm_{digest}", claim_type=kind,
        source_result_reference_id=result.reference.result_reference_id,
        capability_id=result.reference.capability_id,
        capability_version=result.reference.capability_version,
        source_field_paths=(path,), rendered_value=_render(value),
        data_classification=result.reference.data_classification,
    )


def extract_leave_balance_claims(result: ValidatedCapabilityResult) -> tuple[GroundedClaim, ...]:
    """Extract only the fixed leave-balance v1 field allowlist."""

    reference = result.reference
    if (reference.capability_id, reference.capability_version) != (
        LEAVE_BALANCE_CAPABILITY_ID, LEAVE_BALANCE_CAPABILITY_VERSION
    ):
        raise GroundingFailureError("No registered claim extractor exists for the result.")
    claims: list[GroundedClaim] = []
    if result.availability is ResultAvailability.UNAVAILABLE:
        claims.append(_claim(result, ClaimType.STATUS, "status", "unavailable"))
        claims.extend(
            _claim(result, ClaimType.WARNING, f"warnings.{index}", warning)
            for index, warning in enumerate(result.safe_warnings)
        )
        return tuple(claims)
    if result.availability is not ResultAvailability.AVAILABLE or result.output is None:
        raise GroundingFailureError("A failed or missing result cannot produce claims.")
    try:
        output = LeaveBalanceCapabilityOutput.model_validate(result.output.model_dump(), strict=True)
    except Exception as exc:
        raise GroundingFailureError("The typed result could not be grounded safely.") from exc
    claims.extend((
        _claim(result, ClaimType.STATUS, "status", output.status),
        _claim(result, ClaimType.AS_OF, "as_of", output.as_of),
        _claim(result, ClaimType.YEAR, "year", output.year),
    ))
    for index, balance in enumerate(output.balances):
        for field, kind in _BALANCE_FIELDS:
            claims.append(_claim(result, kind, f"balances.{index}.{field}", getattr(balance, field)))
    claims.extend(
        _claim(result, ClaimType.WARNING, f"warnings.{index}", warning)
        for index, warning in enumerate(output.warnings)
    )
    return tuple(claims)


def extract_employee_manager_claims(result: ValidatedCapabilityResult) -> tuple[GroundedClaim, ...]:
    reference = result.reference
    if (reference.capability_id, reference.capability_version) != (
        EMPLOYEE_MANAGER_CAPABILITY_ID, EMPLOYEE_MANAGER_CAPABILITY_VERSION
    ) or result.output is None:
        raise GroundingFailureError("The manager result cannot produce grounded claims.")
    try:
        output = EmployeeManagerCapabilityOutput.model_validate(result.output.model_dump(), strict=True)
    except Exception as exc:
        raise GroundingFailureError("The typed manager result could not be grounded safely.") from exc
    claims = [
        _claim(result, ClaimType.STATUS, "status", output.status),
        _claim(result, ClaimType.AS_OF, "as_of", output.as_of),
    ]
    if output.manager is not None:
        claims.append(_claim(result, ClaimType.MANAGER_NAME, "manager.display_name", output.manager.display_name))
        if output.manager.job_title:
            claims.append(_claim(result, ClaimType.JOB_TITLE, "manager.job_title", output.manager.job_title))
        if output.manager.department:
            claims.append(_claim(result, ClaimType.DEPARTMENT, "manager.department", output.manager.department))
        claims.extend((
            _claim(result, ClaimType.WORK_EMAIL, "manager.work_email", str(output.manager.work_email)),
            _claim(result, ClaimType.SOURCE, "manager.source", output.manager.source),
        ))
    claims.extend(
        _claim(result, ClaimType.WARNING, f"safe_warnings.{index}", warning)
        for index, warning in enumerate(output.safe_warnings)
    )
    return tuple(claims)


def extract_project_assignment_claims(result: ValidatedCapabilityResult) -> tuple[GroundedClaim, ...]:
    reference = result.reference
    if (reference.capability_id, reference.capability_version) != (
        PROJECT_ASSIGNMENTS_CAPABILITY_ID, PROJECT_ASSIGNMENTS_CAPABILITY_VERSION
    ) or result.output is None:
        raise GroundingFailureError("The project assignment result cannot produce grounded claims.")
    try:
        output = CurrentProjectAssignmentsCapabilityOutput.model_validate(
            result.output.model_dump(), strict=True
        )
    except Exception as exc:
        raise GroundingFailureError("The typed project result could not be grounded safely.") from exc
    claims = [
        _claim(result, ClaimType.STATUS, "status", output.status),
        _claim(result, ClaimType.AS_OF, "as_of", output.as_of),
        _claim(result, ClaimType.ASSIGNMENT_COUNT, "assignment_count", output.assignment_count),
        _claim(result, ClaimType.TRUNCATED, "truncated", output.truncated),
    ]
    fields = (
        ("project_name", ClaimType.PROJECT_NAME),
        ("project_code", ClaimType.CODE),
        ("project_status", ClaimType.PROJECT_STATUS),
        ("allocation_role", ClaimType.ALLOCATION_ROLE),
        ("allocation_percentage", ClaimType.ALLOCATION_PERCENTAGE),
        ("allocation_start_date", ClaimType.START_DATE),
    )
    for index, assignment in enumerate(output.assignments):
        for field, kind in fields:
            claims.append(_claim(result, kind, f"assignments.{index}.{field}", getattr(assignment, field)))
        if assignment.allocation_end_date is not None:
            claims.append(_claim(
                result, ClaimType.END_DATE, f"assignments.{index}.allocation_end_date",
                assignment.allocation_end_date,
            ))
        if assignment.project_manager_name is not None:
            claims.append(_claim(
                result, ClaimType.PROJECT_MANAGER_NAME,
                f"assignments.{index}.project_manager_name",
                assignment.project_manager_name,
            ))
    claims.extend(
        _claim(result, ClaimType.WARNING, f"safe_warnings.{index}", warning)
        for index, warning in enumerate(output.safe_warnings)
    )
    return tuple(claims)


def extract_registered_claims(result: ValidatedCapabilityResult) -> tuple[GroundedClaim, ...]:
    key = (result.reference.capability_id, result.reference.capability_version)
    extractors = {
        (LEAVE_BALANCE_CAPABILITY_ID, LEAVE_BALANCE_CAPABILITY_VERSION): extract_leave_balance_claims,
        (EMPLOYEE_MANAGER_CAPABILITY_ID, EMPLOYEE_MANAGER_CAPABILITY_VERSION): extract_employee_manager_claims,
        (PROJECT_ASSIGNMENTS_CAPABILITY_ID, PROJECT_ASSIGNMENTS_CAPABILITY_VERSION): extract_project_assignment_claims,
    }
    extractor = extractors.get(key)
    if extractor is None:
        raise GroundingFailureError("No registered claim extractor exists for the result.")
    return extractor(result)


def _permitted(concrete: str, patterns: tuple[str, ...]) -> bool:
    parts = concrete.split(".")
    for pattern in patterns:
        expected = pattern.split(".")
        if len(parts) == len(expected) and all(
            wanted == "*" or wanted == actual for actual, wanted in zip(parts, expected)
        ):
            return True
    return False


def _source_value(result: ValidatedCapabilityResult, path: str) -> object:
    if path == "status":
        return "unavailable" if result.availability is ResultAvailability.UNAVAILABLE else result.output.status
    if path.startswith("warnings."):
        index = int(path.split(".")[1])
        warnings = result.safe_warnings if result.output is None else result.output.warnings
        return warnings[index]
    if path.startswith("safe_warnings."):
        return result.output.safe_warnings[int(path.split(".")[1])]
    if result.output is None:
        raise LookupError(path)
    value: object = result.output
    for segment in path.split("."):
        if segment.isdigit():
            value = value[int(segment)]  # type: ignore[index]
        else:
            value = getattr(value, segment)
    return value


def validate_grounding(
    plan: ValidatedPlan,
    results: tuple[ValidatedCapabilityResult, ...],
    claims: tuple[GroundedClaim, ...],
) -> ValidatedGrounding:
    """Attest claims only when provenance, values, and plan coverage all match."""

    if not plan.is_validator_trusted or plan.validation_profile != "platform_1c":
        raise GroundingFailureError("Grounding requires a Platform 1C validated plan.")
    if len(results) != len(plan.steps) or not results:
        raise GroundingFailureError("Every completed plan step requires one validated result.")
    by_reference = {item.reference.result_reference_id: item for item in results}
    if len(by_reference) != len(results):
        raise GroundingFailureError("Result references must be unique within an execution.")
    for step, result in zip(plan.steps, results):
        if (step.capability_id, step.capability_version) != (
            result.reference.capability_id, result.reference.capability_version
        ):
            raise GroundingFailureError("A result does not match its completed plan step.")
        if isinstance(step.validated_input, LeaveBalanceCapabilityInput):
            requested = step.validated_input.leave_type
            if requested and result.output is not None:
                balances = result.output.balances
                if len(balances) != 1 or balances[0].leave_type.casefold() != requested.casefold():
                    raise GroundingFailureError("A scoped result exposed unrequested balance data.")

    expected_claims = tuple(
        expected for result in results for expected in extract_registered_claims(result)
    )
    expected_by_path = {
        (item.source_result_reference_id, item.source_field_paths[0]): item
        for item in expected_claims
    }
    seen_paths: set[tuple[str, str]] = set()
    for claim in claims:
        result = by_reference.get(claim.source_result_reference_id)
        if result is None:
            raise GroundingFailureError("A claim references an unknown execution result.")
        if (claim.capability_id, claim.capability_version) != (
            result.reference.capability_id, result.reference.capability_version
        ):
            raise GroundingFailureError("Claim capability provenance does not match its result.")
        if claim.data_classification is not result.reference.data_classification:
            raise GroundingFailureError("Claim classification does not match its source result.")
        path = claim.source_field_paths[0]
        if not _permitted(path, result.permitted_field_paths):
            raise GroundingFailureError("A claim references a field not permitted for grounding.")
        key = (claim.source_result_reference_id, path)
        if key in seen_paths:
            raise GroundingFailureError("Duplicate or contradictory grounded claims are prohibited.")
        seen_paths.add(key)
        if claim != expected_by_path.get(key):
            raise GroundingFailureError("A claim is not the deterministic claim approved for its source field.")
        try:
            source_value = _source_value(result, path)
        except (AttributeError, IndexError, KeyError, LookupError, TypeError, ValueError) as exc:
            raise GroundingFailureError("A claim references a field absent from its typed result.") from exc
        if claim.rendered_value != _render(source_value):
            raise GroundingFailureError("A claim value does not match its validated source field.")

    expected = set(expected_by_path)
    if seen_paths != expected:
        raise GroundingFailureError("The required grounded claim set is incomplete or unsupported.")
    classifications = {item.reference.data_classification for item in results}
    if len(classifications) != 1:
        raise GroundingFailureError("Mixed result classifications are not supported in Platform 1D.")
    validated = ValidatedGrounding.model_validate({
        "plan_id": plan.plan_id,
        "claims": claims,
        "result_reference_ids": tuple(by_reference),
        "data_classification": next(iter(classifications)),
        "safe_warnings": tuple(w for result in results for w in result.safe_warnings),
    }, context={"grounding": _GROUNDING_CONTEXT})
    object.__setattr__(validated, "_grounding_trusted", True)
    return validated
