"""Add is_verified column to firmware table

Revision ID: 0050_firmware_add_is_verified
Revises: 0049_add_fs_size_bytes
Create Date: 2025-08-22 04:42:22.367888

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0050_firmware_add_is_verified"
down_revision = "0049_add_fs_size_bytes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_verified", sa.Boolean(), nullable=True))

    # Calculate is_verified for all firmware
    from handler.database import db_firmware_handler
    from models.firmware import Firmware

    all_firmware = db_firmware_handler.list_firmware()
    verified_firmware_ids = []

    for firmware in all_firmware:
        is_verified = Firmware.verify_file_hashes(
            platform_slug=firmware.platform.slug,
            file_name=firmware.file_name,
            file_size_bytes=firmware.file_size_bytes,
            md5_hash=firmware.md5_hash,
            sha1_hash=firmware.sha1_hash,
            crc_hash=firmware.crc_hash,
        )
        if is_verified:
            verified_firmware_ids.append(firmware.id)

    op.execute("UPDATE firmware SET is_verified = 0")
    op.execute(
        f"UPDATE firmware SET is_verified = 1 WHERE id IN ({','.join(map(str, verified_firmware_ids))})"
    )

    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.alter_column("is_verified", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.drop_column("is_verified")
