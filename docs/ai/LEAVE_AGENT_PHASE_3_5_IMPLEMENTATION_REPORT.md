# Orbit Leave Agent Phase 3.5 Implementation Report

Date: 2026-07-25  
Capability: **Conversational leave intake and missing-information collection**  
Risk class: R1, expiring owner-scoped intake and AI draft only

## Summary

Phase 3.5 lets employees begin leave preparation with ordinary phrases such as
“Apply leave,” “I’m sick tomorrow,” and “Put leave for Friday.” It collects
missing information one focused question at a time, then invokes the existing
Phase 3 preparation tool. It never creates an official `LeaveRequest`, submits
anything, sends a reminder, acts for a manager, or retrieves policy text.

The implementation remains deterministic. It extends the existing typed intent
parser and static tool registry rather than adding a generic planner.

## Conversational flow

The intake tracks these slots:

- Required: leave type, start date, end date.
- Conditionally required: reason and supporting information when the canonical
  backend policy adapter requires them.
- Optional: reason and supporting information under the current Orbit rules.
- Supporting context: requested duration and whether the optional reason was
  explicitly skipped.

Typical interaction:

1. “Apply leave” creates an intake and asks for dates.
2. “Next Monday and Tuesday” records exact dates and asks for leave type.
3. “Casual” records the normalized leave type and offers the optional reason.
4. “No reason” records the explicit skip.
5. Phase 3 reruns eligibility, resolves the approver in the backend, validates
   the reason, creates an AI-only draft, and clears the intake.

The server returns typed `leave_intake_question`,
`leave_intake_summary`, `leave_intake_cancelled`, `leave_draft`, or
`requires_clarification` outcomes. The existing API response uses
`leave_request_draft` as the concrete draft result discriminator for backward
compatibility with Phase 3.

## Safe inference

High-confidence deterministic inference includes:

- “I’m sick tomorrow” -> Sick Leave and tomorrow.
- A named weekday -> the next occurrence of that weekday.
- “family event next Monday” -> reason `family event` and the resolved date.
- A bounded duration such as “two days from Monday” -> start and end dates.

The agent does not infer a leave type from generic leave wording, dates from
“Apply leave,” a reason, an approver, or employee identity. Ambiguous “next
week” wording is stored without dates and results in an exact-date question.
Every inferred field is visible in the intake or final draft card.

## Durable intake state

`AILeaveIntakeState` maps to `ai_leave_intake_states`. A row contains:

- authenticated owner employee ID;
- conversation ID and goal;
- collected fields;
- missing required and optional fields;
- per-field source confidence;
- created, updated, and expiry timestamps.

The owner/conversation pair is unique. State expires after 15 minutes and is
deleted when read after expiry. It is also cleared after successful draft
creation or “Start over.” Intake rows are AI workflow state and are not
official HR records.

Migration:

`backend/migrations/phase_ai_leave_intake_v1.sql`

For an existing PostgreSQL deployment:

```powershell
Set-Location backend
venv\Scripts\python.exe -c "from pathlib import Path; from app.core.database import engine; sql=Path('migrations/phase_ai_leave_intake_v1.sql').read_text(); c=engine.raw_connection(); cur=c.cursor(); cur.execute(sql); c.commit(); cur.close(); c.close()"
```

## Files created

- `backend/app/ai/leave_intake.py`
- `backend/app/services/leave_intake_service.py`
- `backend/migrations/phase_ai_leave_intake_v1.sql`
- `backend/tests/test_ai_leave_agent_phase3_5.py`
- `docs/ai/LEAVE_AGENT_PHASE_3_5_IMPLEMENTATION_REPORT.md`

## Files modified

- `backend/app/models/ai_workflow.py`
- `backend/app/models/__init__.py`
- `backend/app/main.py`
- `backend/app/schemas/ai.py`
- `backend/app/ai/leave_intent.py`
- `backend/app/ai/orchestrator.py`
- `backend/app/api/ai.py`
- Phase 1–3 AI test database fixtures
- `src/services/aiApi.ts`
- `src/components/ai/LeaveAgentResultCards.tsx`
- `src/components/ai/AIChatResponseContent.test.tsx`
- `docs/ai/COMPLETE_LEAVE_AGENT_ARCHITECTURE.md`

## Security controls

- Identity comes only from `AuthenticatedPrincipal`.
- State lookup and mutation always use the authenticated employee ID plus the
  conversation ID.
- Another principal cannot read, continue, clear, or convert an intake.
- User/model-provided employee IDs, email, roles, approvers, balances, SQL,
  API paths, and tool names remain blocked by the existing unsafe-scope guard.
- Leave-balance, eligibility, status, and explicit official-submission intents
  are not consumed as intake follow-ups.
- Intake never accepts an approver. Phase 3 resolves it from canonical backend
  employee and policy data.
- No draft is created before required slots are present.
- Draft creation reruns authoritative eligibility and reason validation.
- The only allowed persistent writes are the expiring intake, the existing
  Phase 3 AI draft, and approved audit records.
- No `leave_requests`, balances, notifications, emails, or approval records
  are created or updated.

## Frontend

The persistent Orbit AI launcher, panel, conversation request flow, API client,
and structured result renderer are reused. Intake cards show collected dates,
leave type, reason/no-reason state, remaining required fields, and expiry. A
cancelled or expired intake has a distinct informational card. React performs
no inference, eligibility check, or draft calculation.

## Test results

- Focused backend Phase 3 + 3.5: **31 passed**
- Full backend: **157 passed**
- Focused AI React rendering: **12 passed**
- Full frontend: **16 passed**
- TypeScript/Vite production build: **passed**

Coverage includes generic intake, dates-first and type-first follow-ups,
optional reason skip, backend-required reason, safe sick/date and family-event
inference, ambiguous dates, duration collection, edits to type/date/reason,
restart, expiry, cross-principal isolation, prompt injection, intent
separation, official-submission blocking, no official leave write, and Phase
1–3 regression behavior.

## Known limitations

- The current `LeaveType` and leave-policy schema has no reason-required or
  attachment-required fields. The policy adapter therefore preserves the
  current behavior: reason is optional and supporting information is not
  required. Tests prove the conditional path without inventing a production
  policy.
- Supporting text can be collected, but chat attachment upload is not part of
  this phase.
- Intake expiry is enforced on access; there is no separate cleanup worker.
- Date understanding is intentionally bounded and deterministic. Ambiguous
  expressions are clarified instead of guessed.
- No official submission, reminder, manager action, cancellation, or RAG is
  present.

## Rollback

1. Remove conversational intake dispatch from the orchestrator.
2. Remove the intake response variants and React cards.
3. Remove the intake model/service and migration registration.
4. Archive then drop `ai_leave_intake_states` if desired.
5. Keep Phase 1–3 tools and drafts unchanged.

Dropping intake state cannot remove or alter an official leave request because
Phase 3.5 never creates one.

## Recommended next step

Do not start Phase 4 until product owners define confirmation, idempotency, and
fresh revalidation requirements for official submission. Separately, add
explicit policy schema fields before enforcing leave-type-specific reasons or
attachments.
