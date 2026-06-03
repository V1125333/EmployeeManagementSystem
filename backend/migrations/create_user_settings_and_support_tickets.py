"""
Create user_settings and support_tickets tables.

Run from backend root:
    python migrations/create_user_settings_and_support_tickets.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402
from app.core.database import engine  # noqa: E402


def migrate():
    dialect = engine.dialect.name
    uuid_type = "UUID" if dialect == "postgresql" else "VARCHAR(36)"
    uuid_default = "DEFAULT gen_random_uuid()" if dialect == "postgresql" else ""
    timestamp_type = "TIMESTAMPTZ" if dialect == "postgresql" else "TIMESTAMP"
    now_expr = "NOW()" if dialect == "postgresql" else "CURRENT_TIMESTAMP"

    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS user_settings (
            id {uuid_type} PRIMARY KEY {uuid_default},
            user_id VARCHAR(36) NOT NULL UNIQUE REFERENCES employees(id) ON DELETE CASCADE,
            time_zone VARCHAR(100) NOT NULL DEFAULT 'America/New_York',
            date_format VARCHAR(20) NOT NULL DEFAULT 'MM/DD/YYYY',
            default_landing_page VARCHAR(100) NOT NULL DEFAULT 'Dashboard',
            theme VARCHAR(20) NOT NULL DEFAULT 'system',
            sidebar_mode VARCHAR(20) NOT NULL DEFAULT 'expanded',
            dashboard_density VARCHAR(20) NOT NULL DEFAULT 'comfortable',
            mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            notification_company_announcements BOOLEAN NOT NULL DEFAULT TRUE,
            notification_leave_updates BOOLEAN NOT NULL DEFAULT TRUE,
            notification_attendance_reminders BOOLEAN NOT NULL DEFAULT TRUE,
            notification_task_assignments BOOLEAN NOT NULL DEFAULT TRUE,
            notification_training_notifications BOOLEAN NOT NULL DEFAULT TRUE,
            notification_project_allocation_updates BOOLEAN NOT NULL DEFAULT TRUE,
            profile_visibility VARCHAR(30) NOT NULL DEFAULT 'Everyone',
            phone_visibility VARCHAR(30) NOT NULL DEFAULT 'Managers Only',
            birthday_visibility VARCHAR(30) NOT NULL DEFAULT 'Everyone',
            created_at {timestamp_type} NOT NULL DEFAULT {now_expr},
            created_by VARCHAR(36) NULL REFERENCES employees(id),
            updated_at {timestamp_type} NOT NULL DEFAULT {now_expr},
            updated_by VARCHAR(36) NULL REFERENCES employees(id),
            CONSTRAINT ck_user_settings_theme CHECK (theme IN ('light', 'dark', 'system')),
            CONSTRAINT ck_user_settings_sidebar_mode CHECK (sidebar_mode IN ('expanded', 'collapsed')),
            CONSTRAINT ck_user_settings_dashboard_density CHECK (dashboard_density IN ('comfortable', 'compact')),
            CONSTRAINT ck_user_settings_date_format CHECK (date_format IN ('MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD')),
            CONSTRAINT ck_user_settings_profile_visibility CHECK (profile_visibility IN ('Everyone', 'Managers Only', 'HR Only', 'Private')),
            CONSTRAINT ck_user_settings_phone_visibility CHECK (phone_visibility IN ('Everyone', 'Managers Only', 'HR Only', 'Private')),
            CONSTRAINT ck_user_settings_birthday_visibility CHECK (birthday_visibility IN ('Everyone', 'Managers Only', 'HR Only', 'Private'))
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id {uuid_type} PRIMARY KEY {uuid_default},
            user_id VARCHAR(36) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            subject VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'Open',
            created_at {timestamp_type} DEFAULT {now_expr},
            created_by VARCHAR(36) REFERENCES employees(id),
            updated_at {timestamp_type} DEFAULT {now_expr},
            updated_by VARCHAR(36) REFERENCES employees(id),
            CONSTRAINT ck_support_tickets_status CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Closed'))
        )
        """,
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    print("Created user_settings and support_tickets tables")


if __name__ == "__main__":
    migrate()
