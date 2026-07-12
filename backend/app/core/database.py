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


def ensure_account_recovery_tables():
    """Safely add account recovery columns and reset sessions for existing databases."""
    from app.models.password_reset import PasswordResetSession  # noqa: F401
    from app.models.login_challenge import LoginChallengeSession  # noqa: F401
    from app.models.unlock_request import AccountUnlockRequest  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("employees")}
    dialect = engine.dialect.name
    column_definitions = {
        "force_password_change": "BOOLEAN DEFAULT FALSE",
        "password_changed_at": "TIMESTAMP",
        "failed_reset_attempts": "INTEGER DEFAULT 0",
        "locked_until": "TIMESTAMP",
        "failed_login_attempts": "INTEGER DEFAULT 0",
        "account_locked": "BOOLEAN DEFAULT FALSE",
        "locked_at": "TIMESTAMP",
        "locked_reason": "VARCHAR(255)",
        "unlocked_at": "TIMESTAMP",
        "unlocked_by_user_id": "VARCHAR(36)",
    }

    statements = []
    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(f"ALTER TABLE employees ADD COLUMN IF NOT EXISTS {column_name} {definition}")
        else:
            statements.append(f"ALTER TABLE employees ADD COLUMN {column_name} {definition}")

    if dialect == "postgresql":
        statements.extend([
            "CREATE INDEX IF NOT EXISTS ix_password_reset_sessions_employee_id ON password_reset_sessions (employee_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_sessions_reset_token_hash ON password_reset_sessions (reset_token_hash)",
            "CREATE INDEX IF NOT EXISTS ix_password_reset_sessions_expires_at ON password_reset_sessions (expires_at)",
            "CREATE INDEX IF NOT EXISTS ix_login_challenge_sessions_employee_id ON login_challenge_sessions (employee_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_login_challenge_sessions_token_hash ON login_challenge_sessions (token_hash)",
            "CREATE INDEX IF NOT EXISTS ix_unlock_requests_status ON account_unlock_requests (status)",
            "CREATE INDEX IF NOT EXISTS ix_unlock_requests_locked_user ON account_unlock_requests (locked_user_id)",
        ])

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


def ensure_holiday_tables():
    """Create holiday tables and align leave requests for floating/optional holidays."""
    from app.models.operations import CompanyHoliday  # noqa: F401
    from app.models.leave_attendance import LeaveRequest  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    dialect = engine.dialect.name
    statements = []

    if "leave_requests" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("leave_requests")}
        if "holiday_id" not in existing_columns:
            if dialect == "postgresql":
                statements.append("ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS holiday_id VARCHAR(36)")
            else:
                statements.append("ALTER TABLE leave_requests ADD COLUMN holiday_id VARCHAR(36)")

    if dialect == "postgresql" and "company_holidays" in inspector.get_table_names():
        statements.extend([
            "CREATE INDEX IF NOT EXISTS idx_holidays_date ON company_holidays (holiday_date)",
            "CREATE INDEX IF NOT EXISTS idx_holidays_type ON company_holidays (holiday_type)",
        ])

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_allocation_columns():
    """Safely align allocations table with the resource allocation foundation."""
    from app.models.allocation import Allocation  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "allocations" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("allocations")}
    dialect = engine.dialect.name
    column_definitions = {
        "project_name": "VARCHAR(150)",
        "manager_id": "VARCHAR(36)",
        "allocation_role": "VARCHAR(100)",
        "billing_type": "VARCHAR(20)",
        "status": "VARCHAR(20) DEFAULT 'active'",
        "notes": "TEXT",
        "created_by": "VARCHAR(36)",
        "updated_by": "VARCHAR(36)",
    }

    statements = []
    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        if dialect == "postgresql":
            statements.append(f"ALTER TABLE allocations ADD COLUMN IF NOT EXISTS {column_name} {definition}")
        else:
            statements.append(f"ALTER TABLE allocations ADD COLUMN {column_name} {definition}")

    role_source = "role_in_project" if "role_in_project" in existing_columns else "'Team Member'"

    if dialect == "postgresql":
        statements.extend([
            "ALTER TABLE allocations ALTER COLUMN project_id DROP NOT NULL",
            "UPDATE allocations SET is_active = TRUE WHERE is_active IS NULL" if "is_active" in existing_columns else None,
            "ALTER TABLE allocations ALTER COLUMN is_active SET DEFAULT TRUE" if "is_active" in existing_columns else None,
            "UPDATE allocations SET status = 'active' WHERE status IS NULL",
            f"UPDATE allocations SET allocation_role = COALESCE(allocation_role, {role_source}, 'Team Member') WHERE allocation_role IS NULL",
            "UPDATE allocations SET billing_type = COALESCE(billing_type, 'billable') WHERE billing_type IS NULL",
            "UPDATE allocations SET manager_id = COALESCE(manager_id, employee_id) WHERE manager_id IS NULL",
            "UPDATE allocations SET created_by = COALESCE(created_by, employee_id) WHERE created_by IS NULL",
        ])
    else:
        statements.extend([
            "UPDATE allocations SET status = 'active' WHERE status IS NULL",
            f"UPDATE allocations SET allocation_role = COALESCE(allocation_role, {role_source}, 'Team Member') WHERE allocation_role IS NULL",
            "UPDATE allocations SET billing_type = COALESCE(billing_type, 'billable') WHERE billing_type IS NULL",
            "UPDATE allocations SET manager_id = COALESCE(manager_id, employee_id) WHERE manager_id IS NULL",
            "UPDATE allocations SET created_by = COALESCE(created_by, employee_id) WHERE created_by IS NULL",
        ])

    with engine.begin() as connection:
        for statement in statements:
            if not statement:
                continue
            try:
                connection.execute(text(statement))
            except Exception:
                if "DROP NOT NULL" not in statement:
                    raise


def ensure_project_workflow_tables():
    """Safely align project workflow columns and document tables."""
    from app.models.operations import Project, ProjectDocument  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "projects" not in table_names:
        return

    dialect = engine.dialect.name
    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    statements = []

    if "project_manager_id" not in project_columns:
        if dialect == "postgresql":
            statements.append("ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_manager_id VARCHAR(36) REFERENCES employees(id)")
        else:
            statements.append("ALTER TABLE projects ADD COLUMN project_manager_id VARCHAR(36)")

    if dialect == "postgresql":
        statements.extend([
            "CREATE INDEX IF NOT EXISTS idx_projects_manager ON projects (project_manager_id)",
            "CREATE INDEX IF NOT EXISTS idx_pd_project_id ON project_documents (project_id)",
            "CREATE INDEX IF NOT EXISTS idx_pd_is_deleted ON project_documents (is_deleted)",
        ])

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_staffing_fulfillment_columns():
    """Safely add Phase 7 fulfillment columns for existing local/dev databases."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "staffing_requests" not in table_names or "staffing_request_candidates" not in table_names:
        return

    dialect = engine.dialect.name
    request_columns = {column["name"] for column in inspector.get_columns("staffing_requests")}
    candidate_columns = {column["name"] for column in inspector.get_columns("staffing_request_candidates")}

    statements = []
    request_definitions = {
        "fulfilled_allocation_ids": "JSONB NOT NULL DEFAULT '[]'::jsonb" if dialect == "postgresql" else "TEXT DEFAULT '[]'",
        "fulfilled_at": "TIMESTAMP",
        "fulfilled_by": "VARCHAR(36)",
    }
    candidate_definitions = {
        "allocation_id": "VARCHAR(36)",
    }

    for column_name, definition in request_definitions.items():
        if column_name in request_columns:
            continue
        if dialect == "postgresql":
            statements.append(f"ALTER TABLE staffing_requests ADD COLUMN IF NOT EXISTS {column_name} {definition}")
        else:
            statements.append(f"ALTER TABLE staffing_requests ADD COLUMN {column_name} {definition}")

    for column_name, definition in candidate_definitions.items():
        if column_name in candidate_columns:
            continue
        if dialect == "postgresql":
            statements.append(f"ALTER TABLE staffing_request_candidates ADD COLUMN IF NOT EXISTS {column_name} {definition}")
        else:
            statements.append(f"ALTER TABLE staffing_request_candidates ADD COLUMN {column_name} {definition}")

    if dialect == "postgresql":
        statements.extend([
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_staffing_candidate_request_allocation'
              ) THEN
                ALTER TABLE staffing_request_candidates
                  ADD CONSTRAINT uq_staffing_candidate_request_allocation
                  UNIQUE (staffing_request_id, allocation_id);
              END IF;
            END $$;
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_staffing_candidate_allocated_employee ON staffing_request_candidates (staffing_request_id, employee_id) WHERE match_status = 'allocated'",
        ])

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            try:
                connection.execute(text(statement))
            except Exception:
                if dialect != "postgresql" and ("CONSTRAINT" in statement or "INDEX" in statement):
                    continue
                raise


def ensure_employee_request_tables():
    """Create request workflow tables and useful indexes for existing deployments."""
    from app.models.requests import (  # noqa: F401
        EmployeeRequest,
        RequestAttachment,
        RequestComment,
        RequestStatusHistory,
        RequestTicketCounter,
    )

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "postgresql":
        return

    inspector = inspect(engine)
    existing_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ("employee_requests", "request_status_history", "request_comments", "request_attachments")
        if table in inspector.get_table_names()
    }

    statements = []
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_er_employee_id ON employee_requests (employee_id)",
        "CREATE INDEX IF NOT EXISTS idx_er_status ON employee_requests (status)",
        "CREATE INDEX IF NOT EXISTS idx_er_request_type ON employee_requests (request_type)",
        "CREATE INDEX IF NOT EXISTS idx_er_pending ON employee_requests (status) WHERE status = 'pending'",
        "CREATE INDEX IF NOT EXISTS idx_er_ticket_number ON employee_requests (ticket_number)",
        "CREATE INDEX IF NOT EXISTS idx_er_current_owner ON employee_requests (current_owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_er_pending_since ON employee_requests (pending_since)",
        "CREATE INDEX IF NOT EXISTS idx_rsh_request_id ON request_status_history (request_id)",
        "CREATE INDEX IF NOT EXISTS idx_rc_request_id ON request_comments (request_id)",
        "CREATE INDEX IF NOT EXISTS idx_ra_request_id ON request_attachments (request_id)",
    ]

    request_columns = {
        "wfh_from_date": "DATE",
        "wfh_to_date": "DATE",
        "wfh_reason": "TEXT",
        "wfh_note": "TEXT",
        "sp_date": "DATE",
        "sp_start_time": "TIME",
        "sp_end_time": "TIME",
        "sp_reason": "TEXT",
        "sp_duration_minutes": "INTEGER",
        "ot_date": "DATE",
        "ot_start_time": "TIME",
        "ot_end_time": "TIME",
        "ot_project_id": "VARCHAR(36)",
        "ot_reason": "TEXT",
        "ot_duration_minutes": "INTEGER",
        "exp_date": "DATE",
        "exp_category": "VARCHAR(80)",
        "exp_amount": "NUMERIC(10, 2)",
        "exp_currency": "VARCHAR(10)",
        "exp_description": "TEXT",
        "exp_paid_at": "TIMESTAMP",
        "exp_paid_by_id": "VARCHAR(36)",
        "reviewed_by_id": "VARCHAR(36)",
        "reviewed_at": "TIMESTAMP",
        "reviewer_notes": "TEXT",
        "ticket_number": "VARCHAR(30)",
        "current_owner_id": "VARCHAR(36)",
        "submitted_to_id": "VARCHAR(36)",
        "pending_since": "TIMESTAMP",
    }
    history_columns = {
        "from_status": "VARCHAR(20)",
        "to_status": "VARCHAR(20)",
        "changed_by_id": "VARCHAR(36)",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    comment_columns = {
        "author_id": "VARCHAR(36)",
        "body": "TEXT",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    attachment_columns = {
        "uploaded_by_id": "VARCHAR(36)",
        "original_file_name": "VARCHAR(255)",
        "stored_file_name": "VARCHAR(255)",
        "file_extension": "VARCHAR(20)",
        "file_size_bytes": "INTEGER",
        "mime_type": "VARCHAR(120)",
        "checksum_sha256": "VARCHAR(64)",
        "storage_provider": "VARCHAR(30) DEFAULT 'local'",
        "storage_path": "TEXT",
        "file_url": "TEXT",
        "document_type": "VARCHAR(50) DEFAULT 'OTHER'",
        "is_deleted": "BOOLEAN DEFAULT FALSE",
        "deleted_at": "TIMESTAMP",
        "deleted_by_id": "VARCHAR(36)",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }

    for column, definition in request_columns.items():
        if column not in existing_columns.get("employee_requests", set()):
            statements.append(f"ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS {column} {definition}")
    for column, definition in history_columns.items():
        if column not in existing_columns.get("request_status_history", set()):
            statements.append(f"ALTER TABLE request_status_history ADD COLUMN IF NOT EXISTS {column} {definition}")
    for column, definition in comment_columns.items():
        if column not in existing_columns.get("request_comments", set()):
            statements.append(f"ALTER TABLE request_comments ADD COLUMN IF NOT EXISTS {column} {definition}")
    for column, definition in attachment_columns.items():
        if column not in existing_columns.get("request_attachments", set()):
            statements.append(f"ALTER TABLE request_attachments ADD COLUMN IF NOT EXISTS {column} {definition}")

    legacy_history_columns = existing_columns.get("request_status_history", set())
    legacy_comment_columns = existing_columns.get("request_comments", set())
    legacy_attachment_columns = existing_columns.get("request_attachments", set())
    if "action" in legacy_history_columns:
        statements.append("ALTER TABLE request_status_history ALTER COLUMN action DROP NOT NULL")
    if "performed_by" in legacy_history_columns:
        statements.append("ALTER TABLE request_status_history ALTER COLUMN performed_by DROP NOT NULL")
        statements.append("UPDATE request_status_history SET changed_by_id = COALESCE(changed_by_id, performed_by) WHERE changed_by_id IS NULL AND performed_by IS NOT NULL")
    if "performed_at" in legacy_history_columns:
        statements.append("ALTER TABLE request_status_history ALTER COLUMN performed_at DROP NOT NULL")
        statements.append("UPDATE request_status_history SET created_at = COALESCE(created_at, performed_at) WHERE created_at IS NULL AND performed_at IS NOT NULL")
    if "new_status" in legacy_history_columns:
        statements.append("ALTER TABLE request_status_history ALTER COLUMN new_status DROP NOT NULL")
        statements.append("UPDATE request_status_history SET to_status = COALESCE(to_status, new_status) WHERE to_status IS NULL AND new_status IS NOT NULL")
    if "old_status" in legacy_history_columns:
        statements.append("UPDATE request_status_history SET from_status = COALESCE(from_status, old_status) WHERE from_status IS NULL AND old_status IS NOT NULL")
    if "comment" in legacy_comment_columns:
        statements.append("ALTER TABLE request_comments ALTER COLUMN comment DROP NOT NULL")
        statements.append("UPDATE request_comments SET body = COALESCE(body, comment) WHERE body IS NULL AND comment IS NOT NULL")
    if "created_by" in legacy_comment_columns:
        statements.append("ALTER TABLE request_comments ALTER COLUMN created_by DROP NOT NULL")
        statements.append("UPDATE request_comments SET author_id = COALESCE(author_id, created_by) WHERE author_id IS NULL AND created_by IS NOT NULL")
    if "file_path" in legacy_attachment_columns:
        statements.append("ALTER TABLE request_attachments ALTER COLUMN file_path DROP NOT NULL")
        statements.append("UPDATE request_attachments SET storage_path = COALESCE(storage_path, file_path) WHERE storage_path IS NULL AND file_path IS NOT NULL")
    if "content_type" in legacy_attachment_columns:
        statements.append("UPDATE request_attachments SET mime_type = COALESCE(mime_type, content_type) WHERE mime_type IS NULL AND content_type IS NOT NULL")
    if "uploaded_by" in legacy_attachment_columns:
        statements.append("ALTER TABLE request_attachments ALTER COLUMN uploaded_by DROP NOT NULL")
        statements.append("UPDATE request_attachments SET uploaded_by_id = COALESCE(uploaded_by_id, uploaded_by) WHERE uploaded_by_id IS NULL AND uploaded_by IS NOT NULL")
    if "file_name" in legacy_attachment_columns:
        statements.append("ALTER TABLE request_attachments ALTER COLUMN file_name DROP NOT NULL")
        statements.append("UPDATE request_attachments SET original_file_name = COALESCE(original_file_name, file_name) WHERE original_file_name IS NULL AND file_name IS NOT NULL")
    statements.extend([
        "UPDATE request_attachments SET original_file_name = COALESCE(original_file_name, stored_file_name, storage_path, id || '_attachment') WHERE original_file_name IS NULL",
        "UPDATE request_attachments SET stored_file_name = COALESCE(stored_file_name, storage_path, id || '_attachment') WHERE stored_file_name IS NULL",
        "UPDATE request_attachments SET storage_provider = COALESCE(storage_provider, 'local') WHERE storage_provider IS NULL",
        "UPDATE request_attachments SET document_type = COALESCE(document_type, 'OTHER') WHERE document_type IS NULL",
        "UPDATE request_attachments SET is_deleted = COALESCE(is_deleted, FALSE) WHERE is_deleted IS NULL",
        "UPDATE request_attachments SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE created_at IS NULL",
        "UPDATE request_attachments SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL",
    ])

    statements.extend(index_statements)

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
