"""Add canonical employee classification and role validation constraints.

Revision ID: 20260905_0004
Revises: 20260816_0003

The migration deliberately does not rewrite roles.  Operators must review the
generated RBAC report and normalize data before enabling the role constraint.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260905_0004"
down_revision = "20260816_0003"
branch_labels = None
depends_on = None

CANONICAL_ROLES = (
    "employee", "manager", "project_manager", "resource_manager",
    "hr_admin", "system_admin", "super_admin",
)
EMPLOYMENT_TYPES = (
    "full_time", "part_time", "contractor", "intern", "trainee", "consultant",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("employees")}
    if "employment_type" not in columns:
        op.add_column("employees", sa.Column("employment_type", sa.String(50), nullable=True))
    # Safe classification backfill only. Role changes are intentionally manual.
    if "workforce_type" in columns:
        op.execute(sa.text("""
            UPDATE employees SET employment_type = CASE
              WHEN lower(replace(replace(workforce_type, '-', '_'), ' ', '_')) IN ('trainee', 'intern', 'contractor', 'consultant', 'full_time', 'part_time')
                THEN lower(replace(replace(workforce_type, '-', '_'), ' ', '_'))
              WHEN lower(replace(replace(workforce_type, '-', '_'), ' ', '_')) = 'contract' THEN 'contractor'
              WHEN lower(replace(replace(workforce_type, '-', '_'), ' ', '_')) = 'full_time_employee' THEN 'full_time'
              WHEN lower(replace(replace(workforce_type, '-', '_'), ' ', '_')) = 'part_time_employee' THEN 'part_time'
              ELSE NULL
            END
            WHERE employment_type IS NULL
        """))
    if bind.dialect.name == "postgresql":
        roles = ", ".join(f"'{role}'" for role in CANONICAL_ROLES)
        employment_types = ", ".join(f"'{kind}'" for kind in EMPLOYMENT_TYPES)
        op.execute(sa.text(
            f"ALTER TABLE employees ADD CONSTRAINT ck_employees_canonical_role CHECK (role IN ({roles})) NOT VALID"
        ))
        op.execute(sa.text(
            f"ALTER TABLE employees ADD CONSTRAINT ck_employees_employment_type CHECK (employment_type IS NULL OR employment_type IN ({employment_types})) NOT VALID"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_employees_employment_type", "employees", type_="check")
        op.drop_constraint("ck_employees_canonical_role", "employees", type_="check")
    if "employment_type" in {column["name"] for column in sa.inspect(bind).get_columns("employees")}:
        op.drop_column("employees", "employment_type")
