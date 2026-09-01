"""Explicit Platform 1B production registry; not wired to the chat gateway."""

from app.ai_platform.capabilities.leave import (
    LEAVE_BALANCE_CAPABILITY_ID,
    LEAVE_BALANCE_CAPABILITY_VERSION,
    LeaveBalanceCapabilityInput,
    LeaveBalanceCapabilityOutput,
    authorize_leave_balance_self,
    execute_leave_balance_adapter,
    validate_leave_balance_postconditions,
    validate_leave_balance_result,
)
from app.ai_platform.capability import CapabilityDefinition
from app.ai_platform.capability_registry import CapabilityRegistry
from app.ai_platform.contracts import (
    ActorScope,
    AuditPolicy,
    Availability,
    ConfirmationRequirement,
    DataClassification,
    IdempotencyPolicy,
    OperationClass,
    RetryPolicy,
    RiskClass,
)
from app.core.authentication import LEAVE_BALANCE_SELF_PERMISSION
from app.ai_platform.capabilities.manager import (
    EMPLOYEE_MANAGER_CAPABILITY_ID, EMPLOYEE_MANAGER_CAPABILITY_VERSION,
    EmployeeManagerCapabilityInput, EmployeeManagerCapabilityOutput,
    authorize_employee_manager_read_self, execute_employee_manager_adapter,
    validate_employee_manager_postconditions, validate_employee_manager_result,
)
from app.core.authentication import EMPLOYEE_MANAGER_SELF_PERMISSION
from app.ai_platform.capabilities.projects import (
    PROJECT_ASSIGNMENTS_CAPABILITY_ID, PROJECT_ASSIGNMENTS_CAPABILITY_VERSION,
    CurrentProjectAssignmentsCapabilityInput, CurrentProjectAssignmentsCapabilityOutput,
    authorize_project_assignments_list_self, execute_project_assignments_adapter,
    validate_project_assignments_postconditions, validate_project_assignments_result,
)
from app.core.authentication import PROJECT_ASSIGNMENTS_SELF_PERMISSION


def build_platform_registry(
    *, kill_switch_active: bool = False, manager_kill_switch_active: bool = False,
    project_kill_switch_active: bool = False,
) -> CapabilityRegistry:
    """Construct the explicit registry; configuration remains server-owned."""

    leave_balance = CapabilityDefinition(
        capability_id=LEAVE_BALANCE_CAPABILITY_ID,
        version=LEAVE_BALANCE_CAPABILITY_VERSION,
        description="Read the authenticated employee's own effective leave balances.",
        domain="leave",
        operation_class=OperationClass.READ,
        risk=RiskClass.MODERATE,
        input_model=LeaveBalanceCapabilityInput,
        output_model=LeaveBalanceCapabilityOutput,
        required_permissions=(LEAVE_BALANCE_SELF_PERMISSION,),
        actor_scope=ActorScope.SELF,
        allowed_target_scopes=(ActorScope.SELF,),
        executor=execute_leave_balance_adapter,
        authorization_policy=authorize_leave_balance_self,
        timeout_seconds=5.0,
        retry_policy=RetryPolicy.NONE,
        idempotency_policy=IdempotencyPolicy.NONE,
        confirmation_requirement=ConfirmationRequirement.NONE,
        audit_policy=AuditPolicy.SENSITIVE,
        data_classification=DataClassification.CONFIDENTIAL,
        result_validator=validate_leave_balance_result,
        postcondition_validator=validate_leave_balance_postconditions,
        kill_switch_active=kill_switch_active,
        availability=Availability.ENABLED,
    )
    employee_manager = CapabilityDefinition(
        capability_id=EMPLOYEE_MANAGER_CAPABILITY_ID,
        version=EMPLOYEE_MANAGER_CAPABILITY_VERSION,
        description="Read the authenticated employee's reporting-manager directory projection.",
        domain="employee", operation_class=OperationClass.READ, risk=RiskClass.LOW,
        input_model=EmployeeManagerCapabilityInput,
        output_model=EmployeeManagerCapabilityOutput,
        required_permissions=(EMPLOYEE_MANAGER_SELF_PERMISSION,),
        actor_scope=ActorScope.SELF, allowed_target_scopes=(ActorScope.SELF,),
        executor=execute_employee_manager_adapter,
        authorization_policy=authorize_employee_manager_read_self,
        timeout_seconds=3.0, retry_policy=RetryPolicy.NONE,
        idempotency_policy=IdempotencyPolicy.NONE,
        confirmation_requirement=ConfirmationRequirement.NONE,
        audit_policy=AuditPolicy.STANDARD,
        data_classification=DataClassification.INTERNAL,
        result_validator=validate_employee_manager_result,
        postcondition_validator=validate_employee_manager_postconditions,
        kill_switch_active=manager_kill_switch_active,
        availability=Availability.ENABLED,
    )
    project_assignments = CapabilityDefinition(
        capability_id=PROJECT_ASSIGNMENTS_CAPABILITY_ID,
        version=PROJECT_ASSIGNMENTS_CAPABILITY_VERSION,
        description="List the authenticated employee's current allocation-backed projects.",
        domain="project", operation_class=OperationClass.READ, risk=RiskClass.MODERATE,
        input_model=CurrentProjectAssignmentsCapabilityInput,
        output_model=CurrentProjectAssignmentsCapabilityOutput,
        required_permissions=(PROJECT_ASSIGNMENTS_SELF_PERMISSION,),
        actor_scope=ActorScope.SELF, allowed_target_scopes=(ActorScope.SELF,),
        executor=execute_project_assignments_adapter,
        authorization_policy=authorize_project_assignments_list_self,
        timeout_seconds=4.0, retry_policy=RetryPolicy.NONE,
        idempotency_policy=IdempotencyPolicy.NONE,
        confirmation_requirement=ConfirmationRequirement.NONE,
        audit_policy=AuditPolicy.SENSITIVE,
        data_classification=DataClassification.INTERNAL,
        result_validator=validate_project_assignments_result,
        postcondition_validator=validate_project_assignments_postconditions,
        kill_switch_active=project_kill_switch_active,
        availability=Availability.ENABLED,
    )
    return CapabilityRegistry((leave_balance, employee_manager, project_assignments))


PLATFORM_REGISTRY = build_platform_registry()
