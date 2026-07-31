"""Static Phase 1 registry: no dynamic imports, API proxying, or SQL tools."""

from types import MappingProxyType
from typing import Callable

from app.ai.leave_balance_tool import get_my_leave_balance
from app.ai.leave_comparison_tool import compare_my_leave_balance
from app.ai.leave_eligibility_tool import check_my_leave_eligibility
from app.ai.leave_request_tools import (
    explain_my_leave_decision,
    get_my_leave_request_details,
    get_my_leave_request_status,
    get_my_recent_leave_requests,
)
from app.ai.leave_draft_tools import (
    discard_my_leave_request_draft,
    get_my_leave_request_draft,
    prepare_my_leave_request,
    update_my_leave_request_draft,
)

AI_TOOLS: MappingProxyType[str, Callable] = MappingProxyType(
    {
        "get_my_leave_balance": get_my_leave_balance,
        "compare_my_leave_balance": compare_my_leave_balance,
        "get_my_recent_leave_requests": get_my_recent_leave_requests,
        "get_my_leave_request_status": get_my_leave_request_status,
        "get_my_leave_request_details": get_my_leave_request_details,
        "explain_my_leave_decision": explain_my_leave_decision,
        "check_my_leave_eligibility": check_my_leave_eligibility,
        "prepare_my_leave_request": prepare_my_leave_request,
        "get_my_leave_request_draft": get_my_leave_request_draft,
        "update_my_leave_request_draft": update_my_leave_request_draft,
        "discard_my_leave_request_draft": discard_my_leave_request_draft,
    }
)
