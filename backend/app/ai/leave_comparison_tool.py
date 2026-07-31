"""Read-only comparisons over the canonical self-scoped balance snapshot."""

from sqlalchemy.orm import Session

from app.ai.leave_balance_tool import AIToolException, get_my_leave_balance
from app.core.authentication import AuthenticatedPrincipal
from app.schemas.ai import (
    AIToolError,
    CompareMyLeaveBalanceInput,
    CompareMyLeaveBalanceOutput,
    GetMyLeaveBalanceInput,
)


def compare_my_leave_balance(
    db: Session,
    principal: AuthenticatedPrincipal,
    tool_input: CompareMyLeaveBalanceInput,
) -> CompareMyLeaveBalanceOutput:
    if tool_input.comparison == "at_least" and (
        tool_input.threshold is None or not tool_input.leave_type
    ):
        raise AIToolException(
            AIToolError(
                code="INVALID_TOOL_INPUT",
                message="A leave type and threshold are required for this comparison.",
            )
        )
    snapshot = get_my_leave_balance(
        db,
        principal,
        GetMyLeaveBalanceInput(
            leave_type=tool_input.leave_type
            if tool_input.comparison == "at_least"
            else None
        ),
    )
    numeric = [
        item for item in snapshot.balances if isinstance(item.available, float)
    ]
    if tool_input.comparison == "highest":
        highest = max(numeric, key=lambda item: item.available, default=None)
        return CompareMyLeaveBalanceOutput(
            as_of=snapshot.as_of,
            comparison="highest",
            balances=snapshot.balances,
            highest=highest,
        )
    available = numeric[0].available if numeric else None
    return CompareMyLeaveBalanceOutput(
        as_of=snapshot.as_of,
        comparison="at_least",
        balances=snapshot.balances,
        threshold=tool_input.threshold,
        meets_threshold=(
            available is not None and available >= float(tool_input.threshold or 0)
        ),
    )
