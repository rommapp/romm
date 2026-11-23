"""Record the capabilities a device sends when it registers or updates itself.

Revision ID: 0141_device_capabilities
Revises: 0140_device_save_sync_baseline
Create Date: 2026-09-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0141_device_capabilities"
down_revision = "0140_device_save_sync_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("capabilities", sa.JSON(), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("capabilities", if_exists=True)
