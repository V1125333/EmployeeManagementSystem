"""Declarative capability definitions with application-supplied callables."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai_platform.contracts import (
    ActorScope,
    AuditPolicy,
    Availability,
    ConfirmationRequirement,
    DataClassification,
    IDENTIFIER_PATTERN,
    IdempotencyPolicy,
    OperationClass,
    RetryPolicy,
    RiskClass,
)

CapabilityCallable = Callable[..., Any]


class CapabilityDefinition(BaseModel):
    """Immutable metadata and trusted runtime hooks for one capability version."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        arbitrary_types_allowed=True,
    )

    capability_id: str = Field(min_length=5, max_length=120)
    version: int = Field(gt=0, le=999)
    description: str = Field(min_length=8, max_length=400)
    domain: str = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    operation_class: OperationClass
    risk: RiskClass
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    required_permissions: tuple[str, ...] = Field(min_length=1, max_length=16)
    actor_scope: ActorScope
    allowed_target_scopes: tuple[ActorScope, ...] = Field(min_length=1, max_length=5)
    executor: CapabilityCallable | None
    authorization_policy: CapabilityCallable
    timeout_seconds: float = Field(gt=0, le=30)
    retry_policy: RetryPolicy = RetryPolicy.NONE
    idempotency_policy: IdempotencyPolicy = IdempotencyPolicy.NONE
    confirmation_requirement: ConfirmationRequirement = ConfirmationRequirement.NONE
    audit_policy: AuditPolicy = AuditPolicy.STANDARD
    data_classification: DataClassification
    result_validator: CapabilityCallable
    postcondition_validator: CapabilityCallable
    kill_switch_active: bool = False
    availability: Availability = Availability.ENABLED

    @field_validator("capability_id")
    @classmethod
    def valid_capability_id(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value) or "/" in value:
            raise ValueError("capability_id must use the stable dotted convention")
        return value

    @field_validator("required_permissions")
    @classmethod
    def valid_permissions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("required_permissions must be unique")
        for value in values:
            if not IDENTIFIER_PATTERN.fullmatch(value):
                raise ValueError("permission identifiers must use dotted convention")
        return values

    @field_validator("allowed_target_scopes")
    @classmethod
    def unique_scopes(cls, values: tuple[ActorScope, ...]) -> tuple[ActorScope, ...]:
        if len(set(values)) != len(values):
            raise ValueError("allowed target scopes must be unique")
        return values

    @model_validator(mode="after")
    def valid_combination(self) -> "CapabilityDefinition":
        if self.availability is Availability.ENABLED and self.executor is None:
            raise ValueError("enabled capabilities require an executor")
        if self.operation_class is OperationClass.READ:
            if self.risk is RiskClass.HIGH:
                raise ValueError("high-risk reads require a separately approved contract")
            if self.confirmation_requirement is not ConfirmationRequirement.NONE:
                raise ValueError("read capabilities cannot require write confirmation")
            if self.idempotency_policy is not IdempotencyPolicy.NONE:
                raise ValueError("read capabilities cannot use write idempotency")
        if self.operation_class is OperationClass.PREPARE and self.risk is RiskClass.LOW:
            raise ValueError("prepare capabilities cannot be classified low risk")
        if self.operation_class is OperationClass.WRITE:
            if self.risk is RiskClass.LOW:
                raise ValueError("write capabilities cannot be classified low risk")
            if self.confirmation_requirement is ConfirmationRequirement.NONE:
                raise ValueError("write capabilities require confirmation metadata")
            if self.retry_policy is not RetryPolicy.NONE:
                raise ValueError("automatic write retries are prohibited")
        if self.retry_policy is RetryPolicy.BOUNDED_READ and self.operation_class is not OperationClass.READ:
            raise ValueError("bounded retries are allowed only for reads")
        if self.actor_scope not in self.allowed_target_scopes:
            raise ValueError("actor_scope must be included in allowed_target_scopes")
        return self

    @property
    def key(self) -> tuple[str, int]:
        return self.capability_id, self.version

    @property
    def is_read_only(self) -> bool:
        return self.operation_class is OperationClass.READ
