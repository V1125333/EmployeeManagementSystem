"""
Database connection and session management.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def ensure_audit_log_table():
    """Create the centralized audit table and indexes for existing deployments."""
    from app.models.audit import AuditLog  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "audit_logs" not in inspector.get_table_names():
        return

    dialect = engine.dialect.name
    if dialect != "postgresql":
        return

    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs (actor_user_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs (entity_type)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_id ON audit_logs (entity_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)",
    ]
    with engine.begin() as connection:
        for statement in index_statements:
            connection.execute(text(statement))


def ensure_employee_audit_columns():
    """Safely add employee intelligence columns to existing databases."""
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("employees")}
    statements = []
    dialect = engine.dialect.name

    column_definitions = {
        "last_updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_by": "VARCHAR(255)",
        "workforce_status": "VARCHAR(50) DEFAULT 'internal'",
        "last_login_at": "TIMESTAMP",
        "last_active_at": "TIMESTAMP",
        "access_level": "VARCHAR(50) DEFAULT 'standard'",
        "mfa_enabled": "BOOLEAN DEFAULT FALSE",
        "device_assigned": "BOOLEAN DEFAULT FALSE",
    }

    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(
                f"ALTER TABLE employees ADD COLUMN IF NOT EXISTS {column_name} {definition}"
            )
        else:
            statements.append(f"ALTER TABLE employees ADD COLUMN {column_name} {definition}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_employee_sensitive_columns():
    """Safely add encrypted placeholders for highly sensitive employee PII."""
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("employees")}
    dialect = engine.dialect.name
    column_definitions = {
        "personal_email_encrypted": "TEXT",
        "phone_encrypted": "TEXT",
        "date_of_birth_encrypted": "TEXT",
        "emergency_contact_name_encrypted": "TEXT",
        "emergency_contact_phone_encrypted": "TEXT",
        "current_address_encrypted": "TEXT",
        "permanent_address_encrypted": "TEXT",
        "pii_key_version": "VARCHAR(20)",
    }

    statements = []
    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(
                f"ALTER TABLE employees ADD COLUMN IF NOT EXISTS {column_name} {definition}"
            )
        else:
            statements.append(f"ALTER TABLE employees ADD COLUMN {column_name} {definition}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_announcement_columns():
    """Safely add announcement workflow columns to existing databases."""
    inspector = inspect(engine)
    if "announcements" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("announcements")}
    dialect = engine.dialect.name
    column_definitions = {
        "message": "TEXT",
        "announcement_type": "VARCHAR(30) DEFAULT 'general'",
        "priority": "VARCHAR(20) DEFAULT 'normal'",
        "audience_type": "VARCHAR(30) DEFAULT 'everyone'",
        "status": "VARCHAR(20) DEFAULT 'draft'",
        "requires_acknowledgment": "BOOLEAN DEFAULT FALSE",
        "publish_at": "TIMESTAMP",
        "expires_at": "TIMESTAMP",
        "created_by": "VARCHAR(255)",
        "updated_by": "VARCHAR(255)",
    }

    statements = []
    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(
                f"ALTER TABLE announcements ADD COLUMN IF NOT EXISTS {column_name} {definition}"
            )
        else:
            statements.append(f"ALTER TABLE announcements ADD COLUMN {column_name} {definition}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_notification_columns():
    """Safely add notification metadata columns to existing databases."""
    inspector = inspect(engine)
    if "notifications" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("notifications")}
    dialect = engine.dialect.name
    column_definitions = {
        "notification_type": "VARCHAR(50)",
        "related_entity_type": "VARCHAR(50)",
        "related_entity_id": "VARCHAR(36)",
    }

    statements = []
    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(
                f"ALTER TABLE notifications ADD COLUMN IF NOT EXISTS {column_name} {definition}"
            )
        else:
            statements.append(f"ALTER TABLE notifications ADD COLUMN {column_name} {definition}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_timesheet_columns():
    """Safely add time-block and overtime columns to existing timesheet tables."""
    inspector = inspect(engine)
    if "timesheet_entries" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("timesheet_entries")}
    dialect = engine.dialect.name
    column_definitions = {
        "start_time": "TIME",
        "end_time": "TIME",
        "overtime_hours": "NUMERIC(4, 2) DEFAULT 0",
        "overtime_requires_approval": "BOOLEAN DEFAULT FALSE",
        "overtime_status": "VARCHAR(20) DEFAULT 'none'",
        "reviewed_by": "VARCHAR(36)",
        "reviewed_at": "TIMESTAMP",
        "reviewer_notes": "TEXT",
    }

    statements = []
    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(
                f"ALTER TABLE timesheet_entries ADD COLUMN IF NOT EXISTS {column_name} {definition}"
            )
        else:
            statements.append(f"ALTER TABLE timesheet_entries ADD COLUMN {column_name} {definition}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_time_off_columns():
    """Safely add admin time-off audit fields to existing databases."""
    inspector = inspect(engine)
    if "leave_balances" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("leave_balances")}
    if "updated_by" in existing_columns:
        return

    dialect = engine.dialect.name
    statement = (
        "ALTER TABLE leave_balances ADD COLUMN IF NOT EXISTS updated_by VARCHAR(255)"
        if dialect == "postgresql"
        else "ALTER TABLE leave_balances ADD COLUMN updated_by VARCHAR(255)"
    )
    with engine.begin() as connection:
        connection.execute(text(statement))


def ensure_leave_type_policy_columns():
    """Safely add configurable leave date policy fields to leave types."""
    inspector = inspect(engine)
    if "leave_types" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("leave_types")}
    dialect = engine.dialect.name
    column_definitions = {
        "allow_future_dates": "BOOLEAN",
        "past_date_limit_days": "INTEGER",
        "future_date_warning": "TEXT",
    }

    statements = []
    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(
                f"ALTER TABLE leave_types ADD COLUMN IF NOT EXISTS {column_name} {definition}"
            )
        else:
            statements.append(f"ALTER TABLE leave_types ADD COLUMN {column_name} {definition}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
