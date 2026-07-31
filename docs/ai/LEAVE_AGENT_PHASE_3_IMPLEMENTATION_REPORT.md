# Orbit Leave Agent Phase 3 Implementation Report

Date: 2026-07-24  
Capability: **Prepare my leave request**  
Risk class: R1, reversible owner-scoped AI draft only

## Summary

Phase 3 prepares, retrieves, updates, continues and discards a durable AI leave
draft. It does not submit a leave request, create an official request number,
deduct a balance, trigger approval, send email/notification, cancel/withdraw a
request, remind an approver, use RAG or perform manager actions.

The architecture roadmap called this Phase 4, while the approved brief calls it
Phase 3. This implementation follows the approved numbering and scope.

## Storage and migration

`AILeaveRequestDraft` maps to `ai_leave_request_drafts`. It stores the
authenticated owner, capability, normalized leave type, dates, optional reason,
eligibility snapshot, working days, balance-source category, backend-resolved
approver, blocker/warning snapshots, AI-only status, timestamps, 30-minute
expiry, optimistic version, payload hash, correlation ID and optional
conversation ID.

The model uses its own identifier and these AI-only statuses:

- `draft`
- `requires_information`
- `not_eligible`
- `ready_for_review`
- `ready_for_confirmation`
- `discarded`
- `expired`

It has no request number and is never serialized as `LeaveRequest`.

The PostgreSQL migration is:

`backend/migrations/phase_ai_leave_request_draft_v1.sql`

For an existing PostgreSQL deployment, run from the repository root:

```powershell
Set-Location backend
venv\Scripts\python.exe -c "from pathlib import Path; from app.core.database import engine; sql=Path('migrations/phase_ai_leave_request_draft_v1.sql').read_text(); c=engine.raw_connection(); cur=c.cursor(); cur.execute(sql); c.commit(); cur.close(); c.close()"
```

Normal application startup also registers the model with SQLAlchemy
`create_tables`, consistent with the current project bootstrap. The migration
remains the explicit managed-deployment artifact.

## Canonical reuse and preparation flow

`prepare_my_leave_request`:

1. Receives a trusted `Employee` resolved from `AuthenticatedPrincipal`.
2. Resolves the active leave type with `resolve_leave_type_reference`.
3. Reruns `check_my_leave_eligibility`, which wraps the canonical
   `assess_my_leave_request`, calendar, holiday, overlap and effective-balance
   rules.
4. Resolves the approver with `resolve_leave_approver`.
5. Validates the optional reason through shared `normalize_leave_reason`.
6. Creates or version-updates only an owner-scoped AI draft.
7. Returns a strict `LeaveRequestDraftOutput`.

Blocking eligibility is stored consistently as `not_eligible`. Missing
eligibility/approver information becomes `requires_information`; eligible
drafts become `ready_for_review`.

## Files created

- `backend/app/models/ai_workflow.py`
- `backend/app/services/leave_approver_service.py`
- `backend/app/services/leave_draft_service.py`
- `backend/app/ai/leave_draft_tools.py`
- `backend/migrations/phase_ai_leave_request_draft_v1.sql`
- `backend/tests/test_ai_leave_agent_phase3.py`
- `src/components/ai/LeaveRequestDraftCard.tsx`
- `docs/ai/LEAVE_AGENT_PHASE_3_IMPLEMENTATION_REPORT.md`

## Files modified

- `backend/app/models/__init__.py`
- `backend/app/main.py`
- `backend/app/core/authentication.py`
- `backend/app/services/leave_service.py`
- `backend/app/services/leave_eligibility_service.py`
- `backend/app/schemas/ai.py`
- `backend/app/ai/leave_intent.py`
- `backend/app/ai/conversation_context.py`
- `backend/app/ai/orchestrator.py`
- `backend/app/ai/tool_registry.py`
- `backend/app/api/ai.py`
- `src/services/aiApi.ts`
- `src/components/ai/AIChatResponseContent.tsx`
- `src/components/ai/LeaveAgentResultCards.tsx`
- `src/components/ai/AIChatResponseContent.test.tsx`
- `src/components/ai/OrbitAIBriefing.tsx`
- `docs/ai/COMPLETE_LEAVE_AGENT_ARCHITECTURE.md`

## Typed tools

- `prepare_my_leave_request`
- `get_my_leave_request_draft`
- `update_my_leave_request_draft`
- `discard_my_leave_request_draft`

Every tool independently requires `leave.request.prepare.self` and reloads the
active employee from `principal.employee_id`. User/model input contains only
leave type, dates, optional reason, and an internally assigned expected
version. Draft identity is passed separately as a trusted server reference.

## Natural language and references

The bounded intent model distinguishes eligibility, draft prepare/get/update/
discard/continue, submission, other-person and manager/approver requests.
Supported updates include leave type, dates, extend one day, move to next week,
set/remove reason and “use the dates we just checked.”

Eligibility and draft references are process-local, principal-bound and
15-minute limited. A draft UUID is never inferred from chat. Every edit fetches
the durable owner-scoped draft; stale versions return
`DRAFT_VERSION_CONFLICT`. Multiple drafts use the most recently updated
non-terminal draft, preferring the active conversation.

## Security and grounding

- Identity, role and permissions come only from the signed principal.
- Employee/manager/approver identities, UUIDs, SQL, API paths and tool names in
  chat are rejected before dispatch.
- The model/browser cannot choose an approver or supply eligibility/balance.
- Dates, counts, balance source, approver, blockers and warnings come from a
  fresh backend evaluation.
- Completed draft responses require an allowlisted draft tool and matching
  result tool.
- Assistant copy explicitly says drafts are not submitted.
- “Submit it” returns `SUBMISSION_NOT_AVAILABLE_IN_PHASE_3` with no tool call.
- Draft writes and approved audit writes are the only new persistence.

## Versioning and expiry

Each material edit increments `version` and recomputes a SHA-256 payload hash
over owner, capability, type, dates, reason and version. Updates require the
trusted expected version and lock the selected row. Drafts expire after 30
minutes; expired/discarded drafts cannot be edited. `Continue` performs a fresh
eligibility evaluation and only advances an eligible draft to
`ready_for_confirmation`.

## Frontend

The existing Orbit AI launcher, panel, chat request flow and structured result
renderer are reused. `LeaveRequestDraftCard` displays AI-draft status, type,
dates, calendar/working-day counts, reason, required/available balance,
balance-source category, approver resolution, blockers, warnings, expiry,
version and correlation reference.

Edit actions prefill the existing chat input. Remove reason, discard and
continue send typed natural-language commands through the same authenticated
gateway. React performs no validation or calculation, and no Submit button is
shown.

## Audit

Phase 3 audit metadata includes actor, correlation/conversation, capability,
tool/draft action, hashed draft reference, draft status/version, normalized
type/date range, permission/tool outcome, eligibility/balance-source category,
approver-resolution state, blocker codes, latency and error category.

It excludes full prompt, reason text, balance amounts, employee records and
approver records.

## Test results

Baseline before implementation:

- Backend: **115 passed**
- Frontend: **12 passed**

Final:

- Focused Phase 3 backend: **15 tests / 40 required scenarios covered, passed**
- Phase 1/2 secure AI regressions: **63 passed**
- Full backend: **130 passed**
- Focused/full frontend: **13 passed**
- TypeScript + Vite production build: **passed**
- Python compilation: **passed**
- `git diff --check`: **passed**

Coverage includes eligible/not-eligible types, referenced dates, missing and
invalid data, past/insufficient/overlap rules, default/on-request balances,
approver resolution, reason changes, type/date changes, extend/move, retrieval,
deterministic latest selection, discard/expiry/stale version, cross-principal
access, injection/identity/approver/SQL/API/tool-name attempts, unsupported
submission, service failure, grounded numerics, and no official side effects.

## Design deviations and known limitations

- Roadmap Phase 4 is delivered under the approved Phase 3 name.
- Draft context is process-local, but draft state is durable. A new process can
  deterministically recover the latest owner-scoped draft.
- Multiple active drafts select the most recently updated draft rather than
  rendering a selection card.
- Reasons use the same at-rest convention as existing leave reasons; they are
  omitted from audit logs.
- No official submission/confirmation token or idempotent request write exists.

## Rollback

1. Remove the four draft tools from `AI_TOOLS`.
2. Remove draft dispatch/result variants and the React draft card.
3. Keep the canonical approver/reason helpers; existing leave behavior uses
   them.
4. Optionally archive then drop `ai_leave_request_drafts`; no official leave or
   balance data is affected.

## Recommended Phase 4

Add an explicit, short-lived confirmation token and idempotent official
submission service. Immediately revalidate eligibility, approver and balance
inside one transaction, create exactly one official request, then read back the
official state. Notification/reminder/manager actions should remain separate
later phases.
