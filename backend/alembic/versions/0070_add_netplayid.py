"""add netplayid to users table

Revision ID: 0070_add_netplayid
Revises: 0070_ss_age_ratings
Create Date: 2026-01-18 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0070_add_netplayid"
down_revision = "0070_ss_age_ratings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add netplayid column to users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "netplayid",
                sa.String(length=255),
                nullable=True,
                unique=True,
                index=True
            )
        )


def downgrade() -> None:
    """Remove netplayid column from users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("netplayid")