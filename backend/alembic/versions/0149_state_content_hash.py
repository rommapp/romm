"""add content_hash to states

Revision ID: 0149_state_content_hash
Revises: 0148_rom_age_limits
Create Date: 2026-10-06 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0149_state_content_hash"
down_revision = "0148_rom_age_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows stay NULL and are compared by their bytes instead.
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("content_hash", sa.String(length=32), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.drop_column("content_hash", if_exists=True)
