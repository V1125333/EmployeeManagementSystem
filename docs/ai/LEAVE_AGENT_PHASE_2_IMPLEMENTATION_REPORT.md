# Orbit Leave Agent Phase 2 Implementation Report

Date: 2026-07-24  
Capability: **Check my leave eligibility**  
Risk class: R0, authenticated read-only

## Summary

Phase 2 adds a secure, deterministic eligibility check to the existing Orbit AI
panel while preserving all Phase 1 behavior. It does not prepare or submit
leave, cancel requests, send reminders, perform approvals, use policy RAG,
generate SQL, or invoke arbitrary APIs.

## Canonical reuse

The implementation reuses `assess_my_leave_request`, `effective_balance` with
`provision=False`, `payable_leave_dates`, employee workweek/region rules,
region-visible holidays and the existing pending/approved overlap query.
Existing `Employee`, `LeaveType`, `LeaveBalance`, `LeaveRequest` and
`CompanyHoliday` models remain authoritative. No calculation is duplicated in
the orchestrator or React.

## Files created

- `backend/app/services/leave_eligibility_service.py`
- `backend/app/ai/leave_eligibility_tool.py`
- `backend/tests/test_ai_leave_agent_phase2.py`
- `src/components/ai/LeaveEligibilityResultCard.tsx`
- `docs/ai/LEAVE_AGENT_PHASE_2_IMPLEMENTATION_REPORT.md`

## Files modified

- `backend/app/services/leave_service.py`
- `backend/app/schemas/leave.py`
- `backend/app/schemas/ai.py`
- `backend/app/core/authentication.py`
- `backend/app/ai/leave_intent.py`
- `backend/app/ai/conversation_context.py`
- `backend/app/ai/orchestrator.py`
- `backend/app/ai/tool_registry.py`
- `backend/app/api/ai.py`
- `backend/requirements.txt`
- `src/services/aiApi.ts`
- `src/components/ai/LeaveAgentResultCards.tsx`
- `src/components/ai/AIChatResponseContent.tsx`
- `src/components/ai/AIChatResponseContent.test.tsx`
- `docs/ai/COMPLETE_LEAVE_AGENT_ARCHITECTURE.md`

## Service result

`check_my_leave_eligibility` returns type/range, calendar and working days,
weekend and holiday exclusions, optional-holiday treatment, required units,
available balance and source, overlapping requests, policy checks, blockers,
warnings, eligibility category, approver, evaluation time and timezone. It
never calls `add`, `flush`, `commit`, provisioning, or mutation code.

## Tool contract and security

The static `check_my_leave_eligibility` tool accepts only:

```json
{
  "leave_type": "Casual Leave",
  "start_date": "2026-08-03",
  "end_date": "2026-08-07"
}
```

It independently verifies `leave.assess.self`, resolves the active employee
from `principal.employee_id`, calls the canonical service and returns a strict
Pydantic value. Identity, email, role, manager, permission/policy overrides,
SQL, URLs and tool selection are not input fields and are rejected in chat.

## Date understanding and context

The bounded deterministic parser supports today/tomorrow, this/next weekday,
two named weekdays, next week, this weekend, ISO dates/ranges, month/day
dates/ranges and trusted same/extend/move follow-ups. Backend time and employee
timezone are authoritative; `tzdata` was added for Windows IANA-zone support.
Invalid, missing and ambiguous dates are clarified. “Two days next week”
requires exact dates rather than silently choosing days.

Context stores only principal ID, normalized type, absolute range and a
15-minute expiry. It is principal-bound and never authoritative: follow-ups
always rerun current balance, calendar, holiday, overlap and policy checks.

## Grounding and explanations

- Completed eligibility requires a successful allowlisted tool call.
- `leave_eligibility` must pair with `check_my_leave_eligibility`.
- `eligible` with blockers is rejected.
- Dates, counts, balance source, exclusions, overlaps, approver and explanations
  are rendered exclusively from the typed tool result.
- Unsupported write requests do not dispatch a tool.

## Frontend

The existing panel and API client are reused. The eligibility card shows state,
range, working/calendar counts, required/available balance, source, excluded
days, holidays, overlaps, blockers, warnings, approver and correlation ID. The
accessible clarification card identifies missing type/date fields. React does
not calculate eligibility.

## Audit behavior

Eligibility audit metadata includes actor, correlation/conversation IDs,
capability/tool, normalized type/date range, permission/tool outcome,
eligibility and balance-source categories, blocker codes, latency and error
category. It excludes prompt text, leave reason, balance amounts, full employee
records and sensitive policy content.

## Tests

- Focused Phase 2 backend: **24 passed**
- Phase 1 backend regression: **39 passed**
- Focused frontend: **9 passed**
- Full backend: **115 passed**
- Full frontend: **12 passed**
- TypeScript and production Vite build: **passed**
- Python compilation and `git diff --check`: **passed**

The focused matrix covers eligibility outcomes, stored/default/on-request
balances, weekends, holidays, optional holidays, overlaps by status, invalid
and missing data, authentication, identity/injection/SQL/API attempts, failures,
no-row-write guarantees and trusted follow-ups.

## Deviations and limitations

- The approved request calls eligibility Phase 2 although the architecture
  roadmap originally called it Phase 3.
- No migration was needed; context is process-local.
- Optional holidays auto-resolve only for one visible holiday on one exact day.
- Natural-language dates use a safe bounded grammar, not an open planner.
- No policy-document explanation or state-changing action is available.

## Rollback

Remove the eligibility tool from the static registry, eligibility dispatch and
the two eligibility result variants/cards. Phase 1 and the normal leave UI
remain unchanged. No data or schema rollback is required.

## Recommended Phase 3

Add confirmation-gated leave preparation only after canonical approver
resolution and durable idempotent workflow storage exist. Keep preparation
separate from submission and revalidate all rules immediately before a write.
