# Reknew Orbit Database Migrations

Task 8B establishes Alembic as the formal migration mechanism. The migration
head is `20260816_0003`; `20260801_0001` is a no-op legacy-schema baseline for
databases previously managed by startup `create_all()` and `ensure_*` functions.

## Safety rules

- Back up and verify recovery before stamping or upgrading a deployed database.
- Confirm `DATABASE_URL` identifies the intended database without printing its credentials.
- Never run `alembic upgrade` automatically during application startup.
- Never stamp a revision merely to bypass the production startup check.
- Test the exact migration against a restored production snapshot first.
- Mixed or invalid legacy weeks remain unchanged and require later resolution.

## New database installation

From `backend` with the approved environment configured:

```powershell
venv\Scripts\alembic.exe -c alembic.ini upgrade head
venv\Scripts\alembic.exe -c alembic.ini current
```

This creates the current schema when the database is genuinely empty and records
the head. It does not seed business data; application startup retains current
seed behavior.

## Existing deployed database baseline

For a pre-Alembic database containing the current legacy schema:

1. Stop application writes and create a verified backup.
2. Test against a restored copy.
3. Verify `employees`, `timesheet_entries`, and `notifications` exist.
4. Stamp only the no-op baseline, then upgrade:

```powershell
venv\Scripts\alembic.exe -c alembic.ini stamp 20260801_0001
venv\Scripts\alembic.exe -c alembic.ini upgrade 20260816_0003
venv\Scripts\alembic.exe -c alembic.ini current
```

Do not stamp `head` unless the Task 8B schema was independently applied and
validated by an approved recovery procedure.

## Upgrade and backfill behavior

Revision `20260801_0002`:

- adds `timesheet_weeks`, `timesheet_idempotency_records`, and
  `timesheet_migration_anomalies`;
- adds nullable `timesheet_entries.timesheet_week_id`;
- adds nullable notification actor, origin, event, deduplication, priority,
  read/dismiss/expiry/update metadata;
- backfills one aggregate per legacy employee/week in batches of 500;
- preserves and links every entry without removing legacy fields;
- maps uniform draft, submitted, approved, and rejected states;
- maps mixed/invalid state sets to `mixed_legacy` and records only bounded status counts;
- fails if any entry remains unlinked, orphaned, or conflicting.

Deterministic aggregate IDs and unique employee/week constraints make the
backfill restart-safe. Existing notification rows retain null metadata. Unique
`(user_id, deduplication_key)` permits multiple null keys while rejecting
repeated non-null keys under PostgreSQL and SQLite.

Revision `20260816_0003` adds the singleton organization MFA policy. Existing
user MFA preferences are enabled during upgrade to preserve the pre-migration
authentication behavior until a user explicitly opts out.

## Production startup compatibility

`MIGRATION_CHECK_ENABLED` defaults to true in production and false in
development/test. When enabled, startup verifies head `20260816_0003`, required
tables, the entry relationship, and notification metadata before `create_all()`
or any `ensure_*` function. Startup never runs Alembic.

The existing `create_all()` and fifteen `ensure_*` paths remain temporarily
active for legacy development and unrelated schema compatibility. Their removal
is outside Task 8B.

## CI validation

```powershell
venv\Scripts\alembic.exe -c alembic.ini heads
venv\Scripts\alembic.exe -c alembic.ini upgrade head
venv\Scripts\python.exe -m pytest tests\test_task8b_migrations.py -q
```

`heads` must return exactly `20260816_0003 (head)`. CI upgrades an empty SQLite
database and a legacy fixture. A PostgreSQL job is still required for production
constraints, nullable uniqueness, timezone types, row locking, and concurrent uniqueness.

## Downgrade and recovery

Automated downgrade through `20260801_0002` is intentionally blocked because
dropping backfilled links and new metadata is destructive. Operational rollback:

1. stop writes;
2. roll back application code while retaining additive schema when compatible;
3. otherwise restore the verified pre-migration backup;
4. validate row counts and migration head before reopening traffic.

No current route depends on the new tables, so code rollback can normally leave
the additive schema in place.
