"""Safe, framework-independent Orbit AI Platform errors."""

from __future__ import annotations

import re
from enum import Enum

from app.ai_platform.contracts import PlatformContract, SAFE_CODE_PATTERN


class EmployeeErrorClass(str, Enum):
    UNSUPPORTED = "unsupported"
    CLARIFICATION = "clarification"
    UNAVAILABLE = "unavailable"
    DENIED = "denied"
    TEMPORARY = "temporary"
    INTERNAL = "internal"


class ErrorContextItem(PlatformContract):
    key: str
    value: str

    @classmethod
    def _safe(cls, value: str, *, limit: int) -> str:
        normalized = " ".join(value.split())[:limit]
        if re.search(r"bearer\s|api[_-]?key|authorization|password|token", normalized, re.I):
            raise ValueError("error context contains forbidden secret material")
        return normalized

    def model_post_init(self, __context: object) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", self.key):
            raise ValueError("invalid error context key")
        if not self.value or len(self.value) > 120:
            raise ValueError("invalid error context value")
        self._safe(self.value, limit=120)


class PlatformError(Exception):
    code = "INTERNAL_PLATFORM_FAILURE"
    employee_classification = EmployeeErrorClass.INTERNAL
    retryable = False

    def __init__(self, safe_message: str, *, context: tuple[ErrorContextItem, ...] = ()):
        normalized = " ".join(str(safe_message).split())[:240]
        if not normalized:
            normalized = "Orbit AI could not complete the request safely."
        if re.search(r"bearer\s|api[_-]?key|authorization|password|token", normalized, re.I):
            normalized = "Orbit AI could not complete the request safely."
        if not SAFE_CODE_PATTERN.fullmatch(self.code):
            raise RuntimeError("platform error code is invalid")
        super().__init__(normalized)
        self.safe_message = normalized
        self.context = tuple(context[:8])

    def safe_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "classification": self.employee_classification.value,
            "retryable": self.retryable,
            "message": self.safe_message,
            "context": [item.model_dump(mode="json") for item in self.context],
        }


def _error(name: str, code: str, classification: EmployeeErrorClass, retryable: bool = False):
    return type(name, (PlatformError,), {
        "code": code,
        "employee_classification": classification,
        "retryable": retryable,
    })


UnsupportedRequestError = _error("UnsupportedRequestError", "UNSUPPORTED_REQUEST", EmployeeErrorClass.UNSUPPORTED)
ClarificationRequiredError = _error("ClarificationRequiredError", "CLARIFICATION_REQUIRED", EmployeeErrorClass.CLARIFICATION)
UnknownCapabilityError = _error("UnknownCapabilityError", "UNKNOWN_CAPABILITY", EmployeeErrorClass.UNAVAILABLE)
DuplicateCapabilityError = _error("DuplicateCapabilityError", "DUPLICATE_CAPABILITY", EmployeeErrorClass.INTERNAL)
DisabledCapabilityError = _error("DisabledCapabilityError", "DISABLED_CAPABILITY", EmployeeErrorClass.UNAVAILABLE)
ShadowOnlyCapabilityError = _error("ShadowOnlyCapabilityError", "SHADOW_ONLY_CAPABILITY", EmployeeErrorClass.UNAVAILABLE)
InvalidCapabilityDefinitionError = _error("InvalidCapabilityDefinitionError", "INVALID_CAPABILITY_DEFINITION", EmployeeErrorClass.INTERNAL)
InvalidPlanError = _error("InvalidPlanError", "INVALID_PLAN", EmployeeErrorClass.UNAVAILABLE)
PlanTooLargeError = _error("PlanTooLargeError", "PLAN_TOO_LARGE", EmployeeErrorClass.UNAVAILABLE)
PlanCycleError = _error("PlanCycleError", "PLAN_CYCLE", EmployeeErrorClass.UNAVAILABLE)
WriteCapabilityProhibitedError = _error("WriteCapabilityProhibitedError", "WRITE_CAPABILITY_PROHIBITED", EmployeeErrorClass.DENIED)
CapabilityInputInvalidError = _error("CapabilityInputInvalidError", "CAPABILITY_INPUT_INVALID", EmployeeErrorClass.CLARIFICATION)
AuthorizationDeniedError = _error("AuthorizationDeniedError", "AUTHORIZATION_DENIED", EmployeeErrorClass.DENIED)
CapabilityTimeoutError = _error("CapabilityTimeoutError", "CAPABILITY_TIMEOUT", EmployeeErrorClass.TEMPORARY, True)
CapabilityExecutionError = _error("CapabilityExecutionError", "CAPABILITY_EXECUTION_FAILURE", EmployeeErrorClass.TEMPORARY, True)
CapabilityResultInvalidError = _error("CapabilityResultInvalidError", "CAPABILITY_RESULT_INVALID", EmployeeErrorClass.UNAVAILABLE)
GroundingFailureError = _error("GroundingFailureError", "GROUNDING_FAILURE", EmployeeErrorClass.UNAVAILABLE)
ProviderUnavailableError = _error("ProviderUnavailableError", "PROVIDER_UNAVAILABLE", EmployeeErrorClass.TEMPORARY, True)
InternalPlatformError = _error("InternalPlatformError", "INTERNAL_PLATFORM_FAILURE", EmployeeErrorClass.INTERNAL)

PLATFORM_ERROR_TYPES = (
    UnsupportedRequestError, ClarificationRequiredError, UnknownCapabilityError,
    DuplicateCapabilityError, DisabledCapabilityError, ShadowOnlyCapabilityError,
    InvalidCapabilityDefinitionError, InvalidPlanError, PlanTooLargeError,
    PlanCycleError, WriteCapabilityProhibitedError, CapabilityInputInvalidError,
    AuthorizationDeniedError, CapabilityTimeoutError, CapabilityExecutionError,
    CapabilityResultInvalidError, GroundingFailureError, ProviderUnavailableError,
    InternalPlatformError,
)
