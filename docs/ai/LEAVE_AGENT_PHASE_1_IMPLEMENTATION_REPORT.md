# Orbit AI Leave Agent — Phase 1 Implementation Report

Date: July 24, 2026

## Outcome

Phase 1 extends the existing secure leave-balance slice into a bounded,
read-only Leave Agent. It understands semantic variations for balances,
thresholds, highest-balance comparisons, leave history, status, details, and
recorded decision explanations. It does not contain a generic planner and
cannot perform a leave-domain write.

Identity is resolved exclusively from `AuthenticatedPrincipal`. The public chat
contract still accepts only a message and optional conversation ID.

## Baseline

Before implementation:

- Focused backend: 34 passed.
- Focused frontend AI: 7 passed.

The baseline covered the existing balance tool, leave service/API contracts,
signed-token enforcement, grounding, rate limits, and frontend result handling.

## Files created

- `backend/app/ai/conversation_context.py`
- `backend/app/ai/leave_comparison_tool.py`
- `backend/app/ai/leave_intent.py`
- `backend/app/ai/leave_request_tools.py`
- `backend/tests/test_ai_leave_agent_phase1.py`
- `src/components/ai/LeaveAgentResultCards.tsx`
- `docs/ai/LEAVE_AGENT_PHASE_1_IMPLEMENTATION_REPORT.md`

## Files modified

- `backend/app/ai/orchestrator.py`
- `backend/app/ai/prompts.py`
- `backend/app/ai/tool_registry.py`
- `backend/app/api/ai.py`
- `backend/app/core/authentication.py`
- `backend/app/schemas/ai.py`
- `backend/app/schemas/leave.py`
- `backend/app/services/leave_service.py`
- `src/components/ai/AIChatResponseContent.tsx`
- `src/components/ai/AIChatResponseContent.test.tsx`
- `src/services/aiApi.ts`
- `docs/ai/COMPLETE_LEAVE_AGENT_ARCHITECTURE.md`

No migration, table, leave request, or leave balance record was created or
updated.

## Implemented tool contracts

| Tool | Input | Authoritative source | Result |
|---|---|---|---|
| `get_my_leave_balance` | Optional leave type | Existing canonical `get_my_leave_balances` | Effective total, available, used, and pending values |
| `compare_my_leave_balance` | Highest comparison, or typed threshold comparison | Existing balance tool/snapshot | Highest balance or verified threshold result |
| `get_my_recent_leave_requests` | Status, leave type, date, bounded limit | New canonical `list_my_leave_requests` service | Owner-scoped request list |
| `get_my_leave_request_status` | Server-resolved criteria or trusted request reference | Canonical list/by-ID services | One authoritative request status |
| `get_my_leave_request_details` | Same safe selection contract | Canonical list/by-ID services | One request with recorded details |
| `explain_my_leave_decision` | Same safe selection contract | Recorded status and `reviewer_notes` | Recorded explanation or explicit “no reason recorded” |

Every input schema uses Pydantic with `extra="forbid"`. No tool accepts employee
ID, employee email, role, manager ID, permission, SQL, API path, arbitrary tool
name, recipient, or arbitrary endpoint.

## Intent model

`LeaveGoal` is the constrained intermediate representation. It contains:

- Intent: balance, balance comparison, request list, status, details, decision
  explanation, or unsupported.
- Optional leave type.
- Official status filters.
- Resolved date reference.
- Latest/history scope.
- Threshold and comparison operator.
- A trusted request reference supplied only by server-side conversation
  context.
- Confidence.

The deterministic semantic parser recognizes concepts and entities rather than
matching whole user sentences. It resolves today, tomorrow, weekday references,
“next weekday,” ISO dates, leave-type aliases/codes, number words, status terms,
latest/recent/history scope, “at least” thresholds, and highest-balance
comparisons.

## Ambiguity handling

A singular status/details/decision lookup uses canonical owner-scoped criteria.
If more than one request matches and the user did not ask for the latest
request, the tool raises `AMBIGUOUS_LEAVE_REQUEST` with at most five safe,
owner-scoped candidates. The API returns:

- `status: needs_clarification`
- `type: ambiguous_leave_request`
- Candidate leave type, dates, days, and official status

The frontend renders these candidates and asks the user to identify the request
by leave type and dates. The agent never guesses.

## Conversation context

Conversation context stores only:

- Conversation ID
- Principal employee ID
- Last successfully resolved request ID
- Fifteen-minute expiry

It is process-local and protected by a lock. A reference is returned only to
the same principal. A foreign, missing, or expired reference is discarded. The
reference is never treated as business truth: every follow-up performs a fresh
owner-scoped database read before producing status or numerical content.

## Security controls

- Signed bearer token and active-account validation remain mandatory.
- `AuthenticatedPrincipal.employee_id` is the only source of employee scope.
- New `leave.request.read.self` permission is resolved server-side.
- Queries always include `LeaveRequest.employee_id == principal.employee_id`.
- Missing and foreign request IDs produce the same not-found behavior.
- User-supplied employee identity, email, UUID, tool name, SQL, or API path is
  rejected before tool selection.
- Role claims such as “I am CEO/admin” do not alter the principal or scope.
- Registry remains an immutable static allowlist with six read tools.
- Completed responses require both an allowlisted successful tool and a typed
  result card.
- Database/tool failures return generic errors without numbers, statuses, or
  internal exception text.
- Existing request size, response size, timeout, concurrency, per-minute, and
  per-day controls remain active.
- AI audit metadata records capability, selected tool, result type, outcome,
  error category, correlation ID, permission decision, and latency without
  storing chat content.

## Frontend

The existing persistent `OrbitAIBriefing` panel and `sendAIChat` API client are
reused. The response union and renderer now support:

- Leave balance comparison
- Leave request list/history
- Leave request status/details
- Rejection explanation
- Ambiguous request selection

Cards use the existing Orbit palette and show only server-returned structured
data.

## Test coverage and results

Phase 1 tests cover:

1. Own casual balance.
2. Sick-leave threshold.
3. Highest balance.
4. Pending request list.
5. Latest request.
6. Leave type plus relative date selection.
7. Ambiguous matching requests.
8. Approved status and decision metadata.
9. Rejection with a recorded reason.
10. Rejection without a reason.
11. Cancelled status.
12. Empty history.
13. Another employee’s request.
14. CEO/admin claims.
15. Prompt injection.
16. Employee ID, UUID, SQL, API path, and tool-name attempts.
17. Tool/database failure.
18. Grounding rejection.
19. Existing balance behavior.
20. Leave-request and leave-balance row counts before/after AI reads.
21. Trusted follow-up reference with authoritative re-read.
22. Cross-principal conversation reference rejection.

Final command results are recorded after the full validation run in this
document's final section.

## Known limitations

- Understanding is currently deterministic, English-only, and intentionally
  bounded; it is not an LLM-driven arbitrary planner.
- Date parsing supports relative day/weekday concepts and ISO dates, not every
  locale-specific date expression.
- Short-term references are process-local and do not survive a backend restart
  or span multiple backend instances.
- Pending duration is calendar-day age from submission. Working-day SLA and
  reminder eligibility belong to the later status-intelligence/reminder phases.
- Historical `withdrawn` may be represented as `cancelled` by the current data
  model and withdrawal service.
- Decision explanations can use only existing `reviewer_notes`; older records
  without notes explicitly report that no reason was recorded.
- Ambiguity cards display safe candidates; users refine the request in chat
  rather than selecting an arbitrary request ID.

## Rollback

1. Remove the four new backend AI modules and the Phase 1 backend test.
2. Restore the one-tool mapping in `backend/app/ai/tool_registry.py`.
3. Restore the original balance-only orchestrator and AI schemas.
4. Remove `LEAVE_REQUEST_SELF_PERMISSION` from the principal permission set.
5. Remove `MyLeaveRequestQuery`, `MyLeaveRequestList`, and
   `list_my_leave_requests`.
6. Restore the frontend API type to the single balance result, remove
   `LeaveAgentResultCards.tsx`, and remove its renderer branch/tests.
7. Restore the previous balance-only gateway audit capability and grounding
   check.

No database rollback or data repair is needed because Phase 1 adds no schema or
leave-domain writes.

## Recommended Phase 2

Implement read-only eligibility and working-day assessment using the existing
`assess_my_leave_request` and work-calendar services. Keep it separate from
request preparation/submission, add typed blockers and warnings, and retain the
same principal-only identity and successful-tool grounding requirements.

## Final validation

- Backend full suite: **91 passed**.
- Frontend full suite: **10 passed**.
- Focused Phase 1 backend suite: **39 passed**.
- Production build: **passed** (`tsc && vite build`).
- Build advisory: Vite reports the existing JavaScript chunk-size warning; it
  does not fail the build.
- Formatting: `git diff --check` passed for the implementation files.
