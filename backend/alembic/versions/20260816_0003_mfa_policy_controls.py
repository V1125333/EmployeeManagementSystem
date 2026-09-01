"""Add organization and per-user MFA policy controls.

Revision ID: 20260816_0003
Revises: 20260801_0002
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260816_0003"
down_revision = "20260801_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "organization_security_policy" not in tables:
        op.create_table(
            "organization_security_policy",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("allow_user_mfa_opt_out", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
        )
        op.execute(
            sa.text(
                "INSERT INTO organization_security_policy "
                "(id, mfa_enabled, allow_user_mfa_opt_out) "
                "VALUES ('organization', true, true)"
            )
        )
    # Existing behavior required MFA whenever a TOTP secret existed. Preserve
    # that behavior until each user explicitly opts out.
    if "user_settings" in tables:
        op.execute(sa.text("UPDATE user_settings SET mfa_enabled = true"))
    if "employees" in tables:
        employee_columns = {column["name"] for column in sa.inspect(bind).get_columns("employees")}
        if {"mfa_enabled", "totp_secret"} <= employee_columns:
            op.execute(sa.text("UPDATE employees SET mfa_enabled = true WHERE totp_secret IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("organization_security_policy")
