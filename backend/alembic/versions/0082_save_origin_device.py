"""Track the device that created a save

Revision ID: 0082_save_origin_device
Revises: 0081_add_archive_members
Create Date: 2026-06-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

revision = "0082_save_origin_device"
down_revision = "0081_add_archive_members"
branch_labels = None
depends_on = None


def _devices_id_collation(conn) -> str | None:
    return conn.execute(
        sa.text(
            "SELECT COLLATION_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'devices' "
            "AND COLUMN_NAME = 'id'"
        )
    ).scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # On MariaDB/MySQL an FK requires both VARCHAR columns to share a collation.
    # A new column inherits the saves table's collation, which can differ from
    # devices.id (e.g. saves predates the MariaDB 11.6+ uca1400 default while
    # devices does not), so pin it to the referenced column's collation.
    collation = None if is_postgresql(conn) else _devices_id_collation(conn)
    column_type = sa.String(length=255, collation=collation)

    # Order matters on MariaDB: the index must exist before the FK (it backs the
    # constraint), so create column -> index -> FK.
    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("origin_device_id", column_type, nullable=True),
            if_not_exists=True,
        )
        if collation is not None:
            # Also fix the column when a previous run created it with a
            # mismatched collation and then failed on the FK.
            batch_op.alter_column(
                "origin_device_id",
                existing_type=sa.String(length=255),
                type_=column_type,
                existing_nullable=True,
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
