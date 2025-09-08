"""Add is_verified column to firmware table

Revision ID: 0050_firmware_add_is_verified
Revises: 0049_add_fs_size_bytes
Create Date: 2025-08-22 04:42:22.367888

"""

import sqlalchemy as sa
from alembic import op

from models.firmware import Firmware
from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0050_firmware_add_is_verified"
down_revision = "0049_add_fs_size_bytes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_verified", sa.Boolean(), nullable=True))

    # Get all firmware records with their hash information
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
        SELECT f.id, p.slug as platform_slug, f.file_name, f.file_size_bytes, f.md5_hash, f.sha1_hash, f.crc_hash
        FROM firmware f
        JOIN platforms p ON f.platform_id = p.id
        """
        )
    )

    all_firmware = result.fetchall()
    verified_firmware_ids = []

    for firmware in all_firmware:
        is_verified = Firmware.verify_file_hashes(
            platform_slug=firmware.platform_slug,
            file_name=firmware.file_name,
            file_size_bytes=firmware.file_size_bytes,
            md5_hash=firmware.md5_hash,
            sha1_hash=firmware.sha1_hash,
            crc_hash=firmware.crc_hash,
        )
        if is_verified:
            verified_firmware_ids.append(firmware.id)

    # Set all firmware as not verified initially
    if is_postgresql(connection):
        op.execute(sa.text("UPDATE firmware SET is_verified = FALSE"))
    else:
        op.execute(sa.text("UPDATE firmware SET is_verified = 0"))

    if verified_firmware_ids:
        placeholders = ",".join(
            [":id" + str(i) for i in range(len(verified_firmware_ids))]
        )
        params = {
            f"id{i}": verified_firmware_ids[i]
            for i in range(len(verified_firmware_ids))
        }
        if is_postgresql(connection):
            op.execute(
                sa.text(
                    # trunk-ignore(bandit/B608)
                    f"UPDATE firmware SET is_verified = TRUE WHERE id IN ({placeholders})"
                ).bindparams(**params)
            )
        else:
            op.execute(
                sa.text(
                    # trunk-ignore(bandit/B608)
                    f"UPDATE firmware SET is_verified = 1 WHERE id IN ({placeholders})"
                ).bindparams(**params)
            )

    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.alter_column("is_verified", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.drop_column("is_verified")
