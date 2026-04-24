"""Add client_device_identifier to devices

Revision ID: 0080_devices_client_identifier
Revises: 0079_add_rom_files_rom_id_index
Create Date: 2026-04-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0084_devices_client_identifier"
down_revision = "0083_rom_category_soundtrack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("client_device_identifier", sa.String(length=255), nullable=True),
            if_not_exists=True,
        )
        batch_op.create_index(
            "ix_devices_user_client_identifier",
            ["user_id", "client_device_identifier"],
            unique=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_index("ix_devices_user_client_identifier", if_exists=True)
        batch_op.drop_column("client_device_identifier", if_exists=True)
