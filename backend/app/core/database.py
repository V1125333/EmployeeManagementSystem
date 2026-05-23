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
