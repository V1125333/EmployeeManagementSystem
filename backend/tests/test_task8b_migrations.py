"""Task 8B formal migration, additive schema, and legacy backfill tests."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.core import database
from app.core.config import settings
from app.core.database import Base
from app.models.operations import Notification, TimesheetEntry, TimesheetIdempotencyRecord, TimesheetWeek


BACKEND = Path(__file__).resolve().parents[1]
HEAD = "20260905_0004"
BASELINE = "20260801_0001"


def _url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _config(database_url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    settings.DATABASE_URL = database_url
    return config


def _legacy_schema(engine: sa.Engine) -> None:
    metadata = sa.MetaData()
    sa.Table("employees", metadata, sa.Column("id", sa.String(36), primary_key=True))
    sa.Table(
        "timesheet_entries", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("entry_code", sa.String(10), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("project_name", sa.String(200), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("hours", sa.Numeric(4, 2), nullable=False, server_default="0"),
        sa.Column("overtime_hours", sa.Numeric(4, 2), nullable=False, server_default="0"),
        sa.Column("overtime_requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("overtime_status", sa.String(20), nullable=False, server_default="none"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("time_zone", sa.String(80), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    sa.Table(
        "notifications", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("type", sa.String(30), nullable=False, server_default="system"),
        sa.Column("notification_type", sa.String(50), nullable=True),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", sa.String(36), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("link_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    metadata.create_all(engine)


def _insert_week(connection, employee_id: str, week_start: date, statuses: list[str]) -> None:
    for index, status in enumerate(statuses):
        connection.execute(sa.text(
            "INSERT INTO timesheet_entries "
            "(id, employee_id, work_date, week_start, entry_code, project_name, hours, status, time_zone, notes) "
            "VALUES (:id, :employee_id, :work_date, :week_start, 'POC', 'Proof of Concept', 8, :status, 'UTC', :notes)"
        ), {
            "id": f"{employee_id}-{week_start}-{index}", "employee_id": employee_id,
            "work_date": week_start, "week_start": week_start, "status": status,
            "notes": f"legacy-sensitive-note-{index}",
        })


@pytest.fixture()
def migrated_legacy_database(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    url = _url(path)
    engine = sa.create_engine(url)
    _legacy_schema(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO employees (id) VALUES ('employee'), ('actor')"))
        _insert_week(connection, "employee", date(2026, 7, 5), ["draft", "draft"])
        _insert_week(connection, "employee", date(2026, 7, 12), ["submitted", "submitted"])
        _insert_week(connection, "employee", date(2026, 7, 19), ["approved"])
        _insert_week(connection, "employee", date(2026, 7, 26), ["rejected"])
        _insert_week(connection, "employee", date(2026, 8, 2), ["submitted", "approved"])
        _insert_week(connection, "employee", date(2026, 8, 9), ["unknown_legacy_state"])
        connection.execute(sa.text(
            "INSERT INTO notifications "
            "(id, user_id, title, message, type, is_read) "
            "VALUES ('legacy-note', 'employee', 'Legacy', 'preserve me', 'system', 0)"
        ))
    config = _config(url)
    command.stamp(config, BASELINE)
    command.upgrade(config, "head")
    yield engine, config
    engine.dispose()


def test_alembic_configuration_loads_application_metadata_and_has_one_head(tmp_path):
    config = _config(_url(tmp_path / "metadata.db"))
    script = ScriptDirectory.from_config(config)
    assert [revision.revision for revision in script.get_revisions("heads")] == [HEAD]
    assert Base.metadata.tables["timesheet_weeks"] is TimesheetWeek.__table__
    assert Base.metadata.tables["timesheet_idempotency_records"] is TimesheetIdempotencyRecord.__table__
    assert "timesheet_week_id" in TimesheetEntry.__table__.columns
    assert "deduplication_key" in Notification.__table__.columns


def test_upgrade_head_succeeds_on_genuinely_empty_sqlite_database(tmp_path):
    path = tmp_path / "empty.db"
    config = _config(_url(path))
    command.upgrade(config, "head")
    command.check(config)
    engine = sa.create_engine(_url(path))
    inspector = sa.inspect(engine)
    assert {"timesheet_weeks", "timesheet_idempotency_records", "timesheet_migration_anomalies", "organization_security_policy"} <= set(
        inspector.get_table_names()
    )
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
    engine.dispose()


def test_uniform_legacy_states_backfill_and_entries_link_without_data_loss(migrated_legacy_database):
    engine, _ = migrated_legacy_database
    with engine.connect() as connection:
        states = dict(connection.execute(sa.text(
            "SELECT week_start, state FROM timesheet_weeks ORDER BY week_start"
        )).all())
        assert list(states.values())[:4] == ["draft", "submitted", "approved", "rejected"]
        assert connection.execute(sa.text(
            "SELECT COUNT(*) FROM timesheet_entries WHERE timesheet_week_id IS NULL"
        )).scalar_one() == 0
        assert connection.execute(sa.text("SELECT COUNT(*) FROM timesheet_entries")).scalar_one() == 9
        assert connection.execute(sa.text(
            "SELECT COUNT(*) FROM timesheet_entries WHERE notes LIKE 'legacy-sensitive-note-%'"
        )).scalar_one() == 9


def test_mixed_state_week_is_preserved_as_bounded_migration_anomaly(migrated_legacy_database):
    engine, _ = migrated_legacy_database
    with engine.connect() as connection:
        aggregate = connection.execute(sa.text(
            "SELECT id, state FROM timesheet_weeks WHERE week_start = '2026-08-02'"
        )).one()
        anomaly = connection.execute(sa.text(
            "SELECT anomaly_type, status_summary, entry_count FROM timesheet_migration_anomalies "
            "WHERE timesheet_week_id = :week_id"
        ), {"week_id": aggregate.id}).one()
        assert aggregate.state == "mixed_legacy"
        assert anomaly.anomaly_type == "mixed_state"
        assert anomaly.status_summary == "approved:1,submitted:1"
        assert anomaly.entry_count == 2
        assert "legacy-sensitive-note" not in anomaly.status_summary


def test_invalid_legacy_state_is_reported_without_normalizing_entry(migrated_legacy_database):
    engine, _ = migrated_legacy_database
    with engine.connect() as connection:
        aggregate = connection.execute(sa.text(
            "SELECT id, state FROM timesheet_weeks WHERE week_start = '2026-08-09'"
        )).one()
        anomaly = connection.execute(sa.text(
            "SELECT anomaly_type, status_summary FROM timesheet_migration_anomalies "
            "WHERE timesheet_week_id = :week_id"
        ), {"week_id": aggregate.id}).one()
        legacy_status = connection.execute(sa.text(
            "SELECT status FROM timesheet_entries WHERE week_start = '2026-08-09'"
        )).scalar_one()
        assert aggregate.state == "mixed_legacy"
        assert anomaly.anomaly_type == "invalid_state"
        assert anomaly.status_summary == "unknown_legacy_state:1"
        assert legacy_status == "unknown_legacy_state"


def test_aggregate_unique_key_and_version_default(migrated_legacy_database):
    engine, _ = migrated_legacy_database
    with engine.begin() as connection:
        row = connection.execute(sa.text(
            "SELECT employee_id, week_start, version FROM timesheet_weeks LIMIT 1"
        )).one()
        assert row.version == 1
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO timesheet_weeks "
                "(id, employee_id, week_start, state, timezone, created_at, updated_at) "
                "VALUES ('duplicate', :employee_id, :week_start, 'draft', 'UTC', :now, :now)"
            ), {"employee_id": row.employee_id, "week_start": row.week_start, "now": datetime.utcnow()})


def test_legacy_notification_survives_with_nullable_metadata(migrated_legacy_database):
    engine, _ = migrated_legacy_database
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT message, actor_employee_id, origin_domain, event_type, deduplication_key, "
            "priority, read_at, dismissed_at, expires_at, updated_at "
            "FROM notifications WHERE id = 'legacy-note'"
        )).one()
        assert row.message == "preserve me"
        assert all(value is None for value in row[1:])


def test_notification_deduplication_key_is_unique_per_recipient_and_nulls_repeat(migrated_legacy_database):
    engine, _ = migrated_legacy_database
    with engine.begin() as connection:
        base = {
            "user_id": "employee", "title": "Event", "type": "system",
        }
        connection.execute(sa.text(
            "INSERT INTO notifications (id, user_id, title, type, deduplication_key) "
            "VALUES ('null-one', :user_id, :title, :type, NULL), "
            "('null-two', :user_id, :title, :type, NULL), "
            "('dedup-one', :user_id, :title, :type, 'event:1')"
        ), base)
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO notifications (id, user_id, title, type, deduplication_key) "
                "VALUES ('dedup-two', 'employee', 'Event', 'system', 'event:1')"
            ))


def test_idempotency_uniqueness_and_bounded_columns(migrated_legacy_database):
    engine, _ = migrated_legacy_database
    inspector = sa.inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("timesheet_idempotency_records")}
    assert columns["request_hash"]["type"].length == 64
    assert columns["result_reference"]["type"].length == 255
    with engine.begin() as connection:
        values = {
            "id": "idempotency-one", "actor": "actor", "operation": "submit_week",
            "key": "request-key", "hash": "a" * 64, "now": datetime.utcnow(),
        }
        connection.execute(sa.text(
            "INSERT INTO timesheet_idempotency_records "
            "(id, actor_employee_id, operation, aggregate_type, idempotency_key, request_hash, status, created_at) "
            "VALUES (:id, :actor, :operation, 'timesheet_week', :key, :hash, 'in_progress', :now)"
        ), values)
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO timesheet_idempotency_records "
                "(id, actor_employee_id, operation, aggregate_type, idempotency_key, request_hash, status, created_at) "
                "VALUES ('idempotency-two', 'actor', 'submit_week', 'timesheet_week', 'request-key', :hash, 'completed', :now)"
            ), {"hash": "b" * 64, "now": datetime.utcnow()})


def test_upgrade_is_restartable_and_startup_head_check_accepts_complete_schema(migrated_legacy_database, monkeypatch):
    engine, config = migrated_legacy_database
    command.upgrade(config, "head")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(settings, "MIGRATION_CHECK_ENABLED", True)
    database.validate_required_migration_head()


def test_startup_head_check_fails_closed_for_unmanaged_database(tmp_path, monkeypatch):
    engine = sa.create_engine(_url(tmp_path / "unmanaged.db"))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(settings, "MIGRATION_CHECK_ENABLED", True)
    with pytest.raises(RuntimeError, match="migration state is missing"):
        database.validate_required_migration_head()
    engine.dispose()


def test_downgrade_is_intentionally_blocked_after_backfill(migrated_legacy_database):
    _engine, config = migrated_legacy_database
    with pytest.raises(RuntimeError, match="intentionally blocked"):
        command.downgrade(config, BASELINE)


@pytest.mark.skip(reason="Requires PostgreSQL to validate nullable unique-key semantics on the production dialect")
def test_postgresql_notification_nullable_deduplication_semantics():
    pass


@pytest.mark.skip(reason="Requires PostgreSQL to validate CHECK constraints and timezone-aware timestamp types")
def test_postgresql_timesheet_constraints_and_timestamp_types():
    pass


@pytest.mark.skip(reason="Requires PostgreSQL concurrent transactions; SQLite cannot prove row locking or unique races")
def test_postgresql_concurrent_aggregate_and_idempotency_uniqueness():
    pass
