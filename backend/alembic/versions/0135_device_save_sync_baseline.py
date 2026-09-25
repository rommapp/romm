"""Record what each side held at the last sync boundary on device_save_sync.

``last_sync_hash`` is the hash the device produced at the boundary (or, in
file-transfer and SSH mode, the hash the server computed of the device's file)
and ``last_sync_server_hash`` is the server save's content_hash at the same
moment. Both stay NULL for existing rows, which is the previous behaviour.

Revision ID: 0135_device_save_sync_baseline
Revises: 0134_gallery_sort_indexes
Create Date: 2026-09-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0135_device_save_sync_baseline"
down_revision = "0134_gallery_sort_indexes"
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
