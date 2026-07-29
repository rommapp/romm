"""Add device_id FK to client_tokens

Revision ID: 0089_client_tokens_device_id
Revises: 0088_devices_client_identifier
Create Date: 2026-04-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0089_client_tokens_device_id"
down_revision = "0088_devices_client_identifier"
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
    # A new column inherits the client_tokens table's collation, which can
    # differ from devices.id when the tables were created under different
    # server defaults (MariaDB 11.6+ switched utf8mb4 to uca1400), so pin it
    # to the referenced column's collation.
    collation = None if is_postgresql(conn) else _devices_id_collation(conn)
    column_type = sa.String(length=255, collation=collation)

    with op.batch_alter_table("client_tokens", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("device_id", column_type, nullable=True),
            if_not_exists=True,
        )
        if collation is not None:
            # Also fix the column when a previous run created it with a
            # mismatched collation and then failed on the FK.
            batch_op.alter_column(
                "device_id",
                existing_type=sa.String(length=255),
                type_=column_type,
                existing_nullable=True,
            )
        batch_op.create_foreign_key(
            "fk_client_tokens_device_id",
            "devices",
            ["device_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_client_tokens_device_id",
            ["device_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("client_tokens", schema=None) as batch_op:
        # Drop FK before the backing index -- MariaDB refuses otherwise
        batch_op.drop_constraint("fk_client_tokens_device_id", type_="foreignkey")
        batch_op.drop_index("ix_client_tokens_device_id", if_exists=True)
        batch_op.drop_column("device_id", if_exists=True)
