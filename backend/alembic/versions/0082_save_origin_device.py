"""Track the device that created a save

Revision ID: 0082_save_origin_device
Revises: 0081_add_archive_members
Create Date: 2026-06-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0082_save_origin_device"
down_revision = "0081_add_archive_members"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Order matters on MariaDB: the index must exist before the FK (it backs the
    # constraint), so create column -> index -> FK.
    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("origin_device_id", sa.String(length=255), nullable=True),
            if_not_exists=True,
        )
        batch_op.create_index(
            "ix_saves_origin_device_id", ["origin_device_id"], if_not_exists=True
        )
        batch_op.create_foreign_key(
            "fk_saves_origin_device_id",
            "devices",
            ["origin_device_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Drop the FK before the index it backs, then the column.
    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.drop_constraint("fk_saves_origin_device_id", type_="foreignkey")
        batch_op.drop_index("ix_saves_origin_device_id", if_exists=True)
        batch_op.drop_column("origin_device_id", if_exists=True)
