"""Add netplayid column to users table

Revision ID: 0073_add_netplayid
Revises: 0072_client_tokens
Create Date: 2026-03-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0073_add_netplayid"
down_revision = "0072_client_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add netplayid column to users table if it does not exist."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]
    if "netplayid" not in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "netplayid",
                    sa.String(length=255),
                    nullable=True,
                    unique=True,
                    index=True,
                )
            )


def downgrade() -> None:
    """Remove netplayid column from users table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]
    if "netplayid" in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("netplayid")
