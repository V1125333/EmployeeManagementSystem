"""Task 8B additive timesheet and notification domain schema.

Revision ID: 20260801_0002
Revises: 20260801_0001
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import importlib
import pkgutil
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260801_0002"
down_revision = "20260801_0001"
branch_labels = None
depends_on = None

VALID_STATES = {"draft", "submitted", "approved", "rejected"}


def _load_metadata():
    from app.core.database import Base
    import app.models as models_package

    for module in pkgutil.iter_modules(models_package.__path__, f"{models_package.__name__}."):
        importlib.import_module(module.name)
    return Base.metadata


def _new_database(bind) -> bool:
    return "employees" not in sa.inspect(bind).get_table_names()


def _create_timesheet_weeks() -> None:
    op.create_table(
        "timesheet_weeks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("review_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("review_decision", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("employee_id", "week_start", name="uq_timesheet_weeks_employee_week"),
        sa.CheckConstraint(
            "state IN ('draft', 'submitted', 'approved', 'rejected', 'mixed_legacy')",
            name="ck_timesheet_weeks_state",
        ),
        sa.CheckConstraint("version >= 1", name="ck_timesheet_weeks_version_positive"),
        sa.CheckConstraint(
            "review_decision IS NULL OR review_decision IN ('approve', 'reject')",
            name="ck_timesheet_weeks_review_decision",
        ),
    )
    op.create_index("ix_timesheet_weeks_employee_week", "timesheet_weeks", ["employee_id", "week_start"])


def _create_idempotency_records() -> None:
    op.create_table(
        "timesheet_idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False, server_default="timesheet_week"),
        sa.Column("aggregate_id", sa.String(36), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("result_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "actor_employee_id", "operation", "idempotency_key",
            name="uq_timesheet_idempotency_actor_operation_key",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed', 'abandoned')",
            name="ck_timesheet_idempotency_status",
        ),
    )
    op.create_index(
        "ix_timesheet_idempotency_aggregate", "timesheet_idempotency_records",
        ["aggregate_type", "aggregate_id"],
    )
    op.create_index(
        "ix_timesheet_idempotency_expires_at", "timesheet_idempotency_records", ["expires_at"],
    )


def _create_anomalies() -> None:
    op.create_table(
        "timesheet_migration_anomalies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("timesheet_week_id", sa.String(36), sa.ForeignKey("timesheet_weeks.id"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("anomaly_type", sa.String(40), nullable=False),
        sa.Column("status_summary", sa.String(255), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("timesheet_week_id", "anomaly_type", name="uq_timesheet_anomaly_week_type"),
    )


def _add_entry_relationship() -> None:
    with op.batch_alter_table("timesheet_entries") as batch:
        batch.add_column(sa.Column("timesheet_week_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_timesheet_entries_timesheet_week_id", "timesheet_weeks",
            ["timesheet_week_id"], ["id"],
        )
        batch.create_index("ix_timesheet_entries_timesheet_week_id", ["timesheet_week_id"])


def _extend_notifications() -> None:
    columns = [
        sa.Column("actor_employee_id", sa.String(36), nullable=True),
        sa.Column("origin_domain", sa.String(50), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=True),
        sa.Column("deduplication_key", sa.String(160), nullable=True),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]
    with op.batch_alter_table("notifications") as batch:
        for column in columns:
            batch.add_column(column)
        batch.create_foreign_key(
            "fk_notifications_actor_employee_id", "employees", ["actor_employee_id"], ["id"],
        )
        batch.create_unique_constraint(
            "uq_notifications_recipient_deduplication", ["user_id", "deduplication_key"],
        )
        batch.create_index("ix_notifications_origin_event", ["origin_domain", "event_type"])


def _week_id(employee_id: str, week_start) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"reknew-orbit:timesheet-week:{employee_id}:{week_start}"))


def _summary(counter: Counter) -> str:
    return ",".join(f"{key}:{counter[key]}" for key in sorted(counter))[:255]


def _backfill(bind, batch_size: int = 500) -> None:
    groups = bind.execute(sa.text(
        "SELECT employee_id, week_start FROM timesheet_entries "
        "GROUP BY employee_id, week_start ORDER BY employee_id, week_start"
    ))
    now = datetime.now(timezone.utc)
    while True:
        batch = groups.fetchmany(batch_size)
        if not batch:
            break
        for employee_id, week_start in batch:
            statuses = bind.execute(sa.text(
                "SELECT status, COUNT(*) FROM timesheet_entries "
                "WHERE employee_id = :employee_id AND week_start = :week_start GROUP BY status"
            ), {"employee_id": employee_id, "week_start": week_start}).all()
            counts = Counter({str(status or "<null>"): int(count) for status, count in statuses})
            uniform = len(counts) == 1 and next(iter(counts)) in VALID_STATES
            state = next(iter(counts)) if uniform else "mixed_legacy"
            anomaly_type = None
            if not uniform:
                anomaly_type = "invalid_state" if any(status not in VALID_STATES for status in counts) else "mixed_state"
            aggregate_id = _week_id(employee_id, week_start)
            existing = bind.execute(sa.text(
                "SELECT id FROM timesheet_weeks WHERE employee_id = :employee_id AND week_start = :week_start"
            ), {"employee_id": employee_id, "week_start": week_start}).scalar_one_or_none()
            if existing and existing != aggregate_id:
                aggregate_id = existing
            if not existing:
                bind.execute(sa.text(
                    "INSERT INTO timesheet_weeks "
                    "(id, employee_id, week_start, state, version, timezone, created_at, updated_at) "
                    "VALUES (:id, :employee_id, :week_start, :state, 1, 'UTC', :created_at, :updated_at)"
                ), {
                    "id": aggregate_id, "employee_id": employee_id, "week_start": week_start,
                    "state": state, "created_at": now, "updated_at": now,
                })
            conflicting = bind.execute(sa.text(
                "SELECT COUNT(*) FROM timesheet_entries WHERE employee_id = :employee_id "
                "AND week_start = :week_start AND timesheet_week_id IS NOT NULL "
                "AND timesheet_week_id <> :aggregate_id"
            ), {
                "employee_id": employee_id, "week_start": week_start, "aggregate_id": aggregate_id,
            }).scalar_one()
            if conflicting:
                raise RuntimeError(
                    f"Timesheet backfill found {conflicting} conflicting entry links for employee/week."
                )
            bind.execute(sa.text(
                "UPDATE timesheet_entries SET timesheet_week_id = :aggregate_id "
                "WHERE employee_id = :employee_id AND week_start = :week_start "
                "AND timesheet_week_id IS NULL"
            ), {
                "aggregate_id": aggregate_id, "employee_id": employee_id, "week_start": week_start,
            })
            if anomaly_type:
                anomaly_exists = bind.execute(sa.text(
                    "SELECT id FROM timesheet_migration_anomalies "
                    "WHERE timesheet_week_id = :week_id AND anomaly_type = :anomaly_type"
                ), {"week_id": aggregate_id, "anomaly_type": anomaly_type}).scalar_one_or_none()
                if not anomaly_exists:
                    bind.execute(sa.text(
                        "INSERT INTO timesheet_migration_anomalies "
                        "(id, timesheet_week_id, employee_id, week_start, anomaly_type, status_summary, entry_count, detected_at) "
                        "VALUES (:id, :week_id, :employee_id, :week_start, :anomaly_type, :summary, :entry_count, :detected_at)"
                    ), {
                        "id": str(uuid.uuid4()), "week_id": aggregate_id, "employee_id": employee_id,
                        "week_start": week_start, "anomaly_type": anomaly_type,
                        "summary": _summary(counts), "entry_count": sum(counts.values()), "detected_at": now,
                    })
    unlinked = bind.execute(sa.text(
        "SELECT COUNT(*) FROM timesheet_entries WHERE timesheet_week_id IS NULL"
    )).scalar_one()
    orphans = bind.execute(sa.text(
        "SELECT COUNT(*) FROM timesheet_entries e LEFT JOIN timesheet_weeks w "
        "ON w.id = e.timesheet_week_id WHERE w.id IS NULL"
    )).scalar_one()
    if unlinked or orphans:
        raise RuntimeError(f"Timesheet backfill validation failed: unlinked={unlinked}, orphaned={orphans}.")


def _validate_schema(bind) -> None:
    inspector = sa.inspect(bind)
    required = {
        "timesheet_weeks": {"id", "employee_id", "week_start", "state", "version", "timezone"},
        "timesheet_idempotency_records": {
            "id", "actor_employee_id", "operation", "idempotency_key", "request_hash", "status",
        },
        "timesheet_migration_anomalies": {
            "id", "timesheet_week_id", "anomaly_type", "status_summary", "entry_count",
        },
        "timesheet_entries": {"timesheet_week_id"},
        "notifications": {
            "actor_employee_id", "origin_domain", "event_type", "deduplication_key", "priority",
            "read_at", "dismissed_at", "expires_at", "updated_at",
        },
    }
    tables = set(inspector.get_table_names())
    problems = []
    for table_name, column_names in required.items():
        if table_name not in tables:
            problems.append(f"missing table {table_name}")
            continue
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(column_names - actual)
        if missing:
            problems.append(f"{table_name} missing columns {missing}")
    if problems:
        raise RuntimeError("Task 8B schema validation failed: " + "; ".join(problems))


def upgrade() -> None:
    bind = op.get_bind()
    if _new_database(bind):
        _load_metadata().create_all(bind=bind)
        _validate_schema(bind)
        return

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    required = {"timesheet_entries", "notifications"}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError(f"Task 8B migration requires legacy tables: {', '.join(missing)}")

    if "timesheet_weeks" not in tables:
        _create_timesheet_weeks()
    if "timesheet_idempotency_records" not in tables:
        _create_idempotency_records()
    if "timesheet_migration_anomalies" not in tables:
        _create_anomalies()

    inspector = sa.inspect(bind)
    entry_columns = {column["name"] for column in inspector.get_columns("timesheet_entries")}
    if "timesheet_week_id" not in entry_columns:
        _add_entry_relationship()
    notification_columns = {column["name"] for column in inspector.get_columns("notifications")}
    if "deduplication_key" not in notification_columns:
        _extend_notifications()
    _backfill(bind)
    _validate_schema(bind)


def downgrade() -> None:
    raise RuntimeError(
        "Task 8B downgrade is intentionally blocked because dropping backfilled aggregate links "
        "and deduplication metadata is destructive. Restore a verified backup instead."
    )
