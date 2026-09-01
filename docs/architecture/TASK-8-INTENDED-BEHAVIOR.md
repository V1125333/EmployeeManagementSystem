# Task 8 Intended Corrected Behavior

This specification is prospective. Task 8A does not implement it.

| Area | Current characterized behavior | Confirmed defect | Intended corrected behavior | Open policy question |
|---|---|---|---|---|
| Save and submit | Submit commits save, then commits submission | Partial draft survives a late failure | Validate and persist entries, transition, audit and required notifications in one transaction/commit | Must a submitted week meet a configured minimum-hours rule? |
| Copy validation | Calendar/leave checks run; allocation validity is copied | Expired target allocation is accepted | Revalidate every copied entry against the target date, project state and allocation | Should invalid project rows be skipped or reject the complete copy? Recommendation: reject atomically |
| Recall | Any submitted row permits recall of all rows | Mixed approved/rejected rows are reset | Aggregate must be exactly `submitted` at the expected version; recall changes only that aggregate to draft | Does a reviewer claim/open action make recall unavailable before decision commit? |
| Approval concurrency | Rows are read and changed without aggregate lock/version | Parallel reviewers can both act on stale state | Lock aggregate and require `expected_version`; exactly one decision succeeds | Are admins allowed to override an assigned reviewer before decision? |
| Expected version | Not present | Stale clients cannot be distinguished | Every write after creation supplies aggregate version; stale requests return a typed conflict | None recommended |
| Idempotency replay | Duplicate submit is an invalid-state error; notification helpers vary | Network retries have no stable result | Submit, recall, delete and decision accept server-scoped idempotency keys; identical replay returns prior result, conflicting reuse fails | Required for save/copy as well, or optional PUT/version semantics? |
| Notification deduplication | Mostly none; announcement/reminder query before insert | Sequential and concurrent duplicates possible | Persist server-derived dedup key with recipient uniqueness; conflict returns existing notification | Retention period for dedup keys |
| Transaction rollback | Depends on caller; submit spans two commits | Business state, audit and notification can diverge | One transaction owns aggregate, entries, audit, required notifications and idempotency result | Which notifications, if any, are noncritical? |
| Audit consistency | Manager/admin names and entity IDs differ; GET compliance commits | Inconsistent correlation and sensitive fields | Stable aggregate ID, common event names, bounded metadata, one audit per transition plus explicit variance event | Must compliance reads be audited, or only denied/high-risk access? |
| Sensitive messages | Some paths append notes or accept long free text | Notification content can expose sensitive detail | Template registry, bounded parameters, no reviewer/medical/security free text, allowlisted links | Exact employee-visible rejection-detail channel |
| Inbox reads | GET inbox/count can complete/delete and commit | Safe reads have side effects | GET endpoints are read-only; cleanup is an explicit command or background maintenance job | Should stale profile items be dismissed, completed, or retained? |
| Manager/admin decision | Separate routes duplicate logic and responses | Divergent behavior and audit | Both adapters invoke one `decide_timesheet` service with the same state machine and error contract | Required rejection reason and maximum length should be unified |
| Aggregate state | Derived from multiple entry rows | Mixed states are representable | `TimesheetWeek.state` is authoritative; entry status is removed or derived after compatibility | Backfill resolution for existing mixed weeks requires operator review |

## Required postconditions

After every successful write:

- one aggregate exists for employee/week;
- all entries belong to it and match its state rules;
- version increments exactly once;
- totals and entry counts match persisted rows;
- exactly one bounded audit transition exists;
- required notification intents exist once per recipient/event;
- the idempotency record references the committed result;
- no commit occurs inside a nested helper.

After failure, none of the aggregate mutation, entry replacement, audit,
notification or idempotency result is committed.

