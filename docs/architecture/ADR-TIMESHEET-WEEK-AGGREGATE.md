# ADR: TimesheetWeek Aggregate and Canonical Notification Boundary

- Status: Accepted; additive schema implemented by Task 8B, authority deferred to Task 8C-8F
- Decision date: 2026-08-01
- Scope: architecture decision only; Task 8A changes no production schema or behavior

## Context

The current persistence model represents a week only as a set of
`TimesheetEntry` rows. There is no row that exists for an empty week, no unique
week identity, no aggregate status, and no version suitable for optimistic
concurrency.

Submission calls the draft-save route, which commits, before changing rows to
submitted and committing again. A deterministic Task 8A test proves that a
notification-stage failure leaves the draft persisted. Recall changes all rows
when any row is submitted. Manager and administrative approval duplicate state
changes while using different schemas, audit identifiers and responses. No
operation locks the employee/week as a whole.

Notifications are inserted by several route and service helpers with inconsistent
fields, transaction ownership, audit attribution and deduplication. A future
constrained AI executor must call the same authorized, transactional operations
as HTTP routes and must not gain a path around business rules.

## Decision

Introduce a `TimesheetWeek` aggregate. Task 8B implemented the aggregate
additively without connecting current routes.

The aggregate will have:

- immutable ID;
- unique key `(employee_id, week_start)`;
- state: `draft`, `submitted`, `approved`, or `rejected` (absence means not started);
- integer version, incremented for every state or entry-set change;
- time zone;
- created/updated/submitted/reviewed timestamps;
- reviewer ID and bounded rejection/review metadata where policy permits;
- relationship from existing `TimesheetEntry` rows through `timesheet_week_id`;
- optional current idempotency/result references kept in a separate operation table.

Every write will begin a transaction, load/create and lock the aggregate with
`SELECT ... FOR UPDATE`, compare `expected_version`, validate authorization and
state, mutate entries, stage audit and required notifications, verify
postconditions, then commit once. Optimistic version checks protect clients from
stale recall or approval; the lock serializes simultaneous writes.

Idempotency records will be unique by actor, aggregate, operation and key. They
will store a bounded input hash and result reference, not the raw payload. Replay
of the same key and input returns the prior result; reuse with different input
fails.

## Alternatives considered

### Continue using only entry rows

- Benefits: no new table or backfill.
- Risks: no lockable empty week, mixed states remain representable, and aggregate
  version/idempotency remain awkward.
- Migration complexity: low initially, high in every service operation.
- Portability: high.
- Rollback: trivial, but defects remain. Rejected.

### Database advisory locks without an aggregate

- Benefits: can serialize an employee/week even when no entry exists.
- Risks: database-specific lock-key design, weak discoverability, no persisted
  state/version, and difficult operational diagnostics.
- Migration complexity: low schema complexity but high behavioral complexity.
- Portability: low.
- Rollback: code-only, but in-flight locking semantics are hard to reason about.
  Rejected as the primary design; acceptable only as a short-lived bridge.

### Add a `TimesheetWeek` aggregate

- Benefits: explicit identity/state/version, reliable row lock, unique employee
  week, coherent audit/entity references, and clean service/tool contract.
- Risks: backfill, compatibility period and additional joins.
- Migration complexity: medium-high but localized and testable.
- Portability: high across relational databases supporting row locks.
- Rollback: additive schema can remain while routes temporarily use legacy reads.
  Selected.

### Event-sourced timesheet ledger

- Benefits: complete transition history and natural idempotency/event identity.
- Risks: major read-model, operational and developer complexity that the current
  system does not justify.
- Migration complexity: very high.
- Portability: moderate.
- Rollback: difficult after event-ledger authority changes. Rejected for Task 8.

## Notification decision

A future canonical notification service will accept an authenticated actor and a
validated business event, not arbitrary client-provided recipients or text.
Canonical data will include origin domain, event type, related entity, recipient,
template ID/parameters, allowlisted navigation target, priority, deduplication
key, created/read/dismissed/expiry state and audit correlation.

Domain recipient resolvers will derive reporting managers, project managers,
administrators, employees or workflow owners from server state. A template
registry will bound text and exclude sensitive notes. A database unique
constraint on recipient plus deduplication key will make sequential and concurrent
replay safe. Required in-application notifications participate in the business
transaction; the notification service will flush but will not independently
commit. External delivery, if later required, uses an outbox and is outside Task 8.

## Migration strategy

The repository currently uses `Base.metadata.create_all`, startup `ensure_*`
functions and a directory of manually executed Python/SQL migrations. Those
mechanisms do not provide a single ordered, versioned migration history or safe
downgrade tracking.

Before adding the aggregate, adopt Alembic as the formal migration mechanism:

1. Baseline the existing production schema without recreating it.
2. Add the week table, nullable entry foreign key, notification metadata and
   indexes additively.
3. Backfill one aggregate per distinct employee/week and associate entries.
4. Detect and report mixed-status weeks rather than silently choosing a state.
5. Validate row counts, totals, status mapping and orphan counts.
6. Add unique and foreign-key constraints only after validation.
7. Deploy compatibility reads, then canonical writes, without dual-writing two
   authoritative implementations.
8. Keep old columns/helpers through a measured compatibility period.
9. Remove related `ensure_*` schema mutation only after all supported databases
   are migration-managed.

Rollback is code-first: point route adapters back to legacy behavior while
leaving additive tables and nullable columns in place. Backups are required before
backfill and constraint activation. Destructive downgrade is not the normal
rollback path.

Implementation note: revisions `20260801_0001` and `20260801_0002` implement the
legacy baseline and additive schema. Mixed or invalid legacy state sets use the
`mixed_legacy` aggregate state and a bounded `timesheet_migration_anomalies`
record rather than blocking deployment or silently normalizing entry state.

## Consequences

The design adds tables/columns, migrations, version and idempotency handling, and
production-database concurrency tests. In exchange, routes become HTTP adapters,
manager/admin approval converges on one service operation, audit identity becomes
stable, notifications become consistent, and a future constrained AI executor can
invoke the same explicit authorization boundary without receiving raw ORM access.
