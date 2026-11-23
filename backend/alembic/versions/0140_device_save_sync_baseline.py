"""Record what each side held at the last sync boundary on device_save_sync.

Existing rows keep NULL, meaning unknown.

Revision ID: 0140_device_save_sync_baseline
Revises: 0139_rom_user_pinned_media
Create Date: 2026-09-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0140_device_save_sync_baseline"
down_revision = "0139_rom_user_pinned_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_save_sync", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_sync_hash", sa.String(32), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("last_sync_server_hash", sa.String(32), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("device_save_sync", schema=None) as batch_op:
        batch_op.drop_column("last_sync_server_hash", if_exists=True)
        batch_op.drop_column("last_sync_hash", if_exists=True)
