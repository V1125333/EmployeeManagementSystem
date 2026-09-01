"""Platform-to-current-AI compatibility mapping for isolated parity tests."""

from app.ai.leave_balance_tool import AIToolException
from app.ai_platform.capabilities.leave import (
    LeaveBalanceCapabilityError,
    LeaveBalanceCapabilityOutput,
)
from app.schemas.ai import (
    AIChatResponse,
    AIMessage,
    AIToolError,
    GetMyLeaveBalanceOutput,
    LeaveBalanceResultCard,
    LeaveBalanceToolItem,
)
from app.ai_platform.platform_response import PlatformResponse, PlatformResponseStatus


def to_legacy_leave_balance_output(
    output: LeaveBalanceCapabilityOutput,
) -> GetMyLeaveBalanceOutput:
    as_of = output.as_of.replace(tzinfo=None) if output.as_of.tzinfo else output.as_of
    return GetMyLeaveBalanceOutput(
        as_of=as_of,
        year=output.year,
        balances=[
            LeaveBalanceToolItem(
                leave_type=item.leave_type,
                code=item.code,
                total=item.total,
                available=item.available,
                used=item.used,
                pending=item.pending,
                source=item.source,
            )
            for item in output.balances
        ],
    )


def to_leave_balance_result_card(
    output: LeaveBalanceCapabilityOutput,
) -> LeaveBalanceResultCard:
    legacy = to_legacy_leave_balance_output(output)
    return LeaveBalanceResultCard(
        title="My leave balance",
        as_of=legacy.as_of,
        balances=legacy.balances,
    )


def legacy_balance_answer(output: LeaveBalanceCapabilityOutput) -> str:
    legacy = to_legacy_leave_balance_output(output)
    if len(legacy.balances) == 1:
        item = legacy.balances[0]
        available = item.available if isinstance(item.available, str) else f"{item.available:g} days"
        return (
            f"You have {available} of {item.leave_type} available. "
            f"Used: {item.used:g} days; pending: {item.pending:g} days."
        )
    return (
        f"I found {len(legacy.balances)} leave balances for {legacy.year}. "
        "The verified values are shown below."
    )


def to_legacy_tool_exception(error: LeaveBalanceCapabilityError) -> AIToolException:
    return AIToolException(
        AIToolError(code=error.legacy_code, message=error.safe_message)
    )


def to_legacy_ai_chat_response(response: PlatformResponse) -> AIChatResponse:
    """Map an isolated Platform response to the existing external shape for parity tests."""

    status = {
        PlatformResponseStatus.COMPLETED: "completed",
        PlatformResponseStatus.CLARIFICATION_REQUIRED: "needs_clarification",
        PlatformResponseStatus.UNSUPPORTED: "unsupported",
        PlatformResponseStatus.DENIED: "failed",
        PlatformResponseStatus.FAILED: "failed",
        PlatformResponseStatus.TIMED_OUT: "failed",
    }[response.status]
    error = None
    if response.safe_error:
        allowed = {
            "UNSUPPORTED_LEAVE_TYPE", "LEAVE_TYPE_NOT_APPLICABLE",
            "MISSING_POLICY_CONFIGURATION", "MISSING_BALANCE_RECORD",
            "PERMISSION_DENIED", "TOOL_UNAVAILABLE", "INVALID_TOOL_INPUT",
        }
        code = response.safe_error.code if response.safe_error.code in allowed else (
            "PERMISSION_DENIED" if response.status is PlatformResponseStatus.DENIED
            else "INVALID_TOOL_INPUT" if response.status is PlatformResponseStatus.CLARIFICATION_REQUIRED
            else "TOOL_UNAVAILABLE"
        )
        error = AIToolError(code=code, message=response.safe_error.message)
    return AIChatResponse(
        conversation_id=response.conversation_id, status=status,
        message=AIMessage(content=response.message),
        result=response.result_cards[0] if response.result_cards else None,
        error=error,
        tool_used="get_my_leave_balance" if response.result_reference_ids else None,
        correlation_id=response.correlation_id,
    )
