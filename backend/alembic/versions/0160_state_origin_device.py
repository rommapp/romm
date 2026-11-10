"""Track the device that wrote a state

Revision ID: 0160_state_origin_device
Revises: 0159_client_tokens_fk_cascade
Create Date: 2026-11-09 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

revision = "0160_state_origin_device"
down_revision = "0159_client_tokens_fk_cascade"
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

    # On MariaDB/MySQL an FK requires both VARCHAR columns to share a collation,
    # and states can predate the collation devices.id was created with.
    collation = None if is_postgresql(conn) else _devices_id_collation(conn)
    column_type = sa.String(length=255, collation=collation)

    # MariaDB needs the index before the FK it backs.
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("origin_device_id", column_type, nullable=True),
            if_not_exists=True,
        )
        batch_op.create_index(
            "ix_states_origin_device_id", ["origin_device_id"], if_not_exists=True
        )
        batch_op.create_foreign_key(
            "fk_states_origin_device_id",
            "devices",
            ["origin_device_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.drop_constraint("fk_states_origin_device_id", type_="foreignkey")
        batch_op.drop_index("ix_states_origin_device_id", if_exists=True)
        batch_op.drop_column("origin_device_id", if_exists=True)
