"""Add collections.is_open

Revision ID: 0162_open_collections
Revises: 0161_save_channels
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0162_open_collections"
down_revision = "0161_save_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("collections") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_open", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("collections") as batch_op:
        batch_op.drop_column("is_open")
