"""add core to states

Revision ID: 0141_state_core
Revises: 0140_device_save_sync_baseline
Create Date: 2026-09-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0141_state_core"
down_revision = "0140_device_save_sync_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows stay NULL, which reads as the platform's default core.
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("core", sa.String(length=50), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.drop_column("core", if_exists=True)
