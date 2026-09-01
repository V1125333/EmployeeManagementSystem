"""Legacy schema baseline for already deployed databases.

Revision ID: 20260801_0001
Revises: None
"""

revision = "20260801_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing databases stamp this revision after a backup and schema review.
    # A new empty database is materialized by the following Task 8B revision.
    pass


def downgrade() -> None:
    pass
