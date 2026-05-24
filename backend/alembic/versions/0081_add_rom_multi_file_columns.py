"""Add multi_file and top_level_file_count to roms

Revision ID: 0081_add_rom_multi_file_columns
Revises: 0080_add_chd_sha1_hash
Create Date: 2026-05-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0081_add_rom_multi_file_columns"
down_revision = "0080_add_chd_sha1_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "multi_file", sa.Boolean(), nullable=False, server_default="0"
            ),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column(
                "top_level_file_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            if_not_exists=True,
        )

    # A rom is folder-based ("multi_file") if any of its rom_files lives at a
    # path other than the rom's fs_path (which is the per-platform roms dir).
    op.execute(
        sa.text(
            """
            UPDATE roms SET multi_file = EXISTS (
                SELECT 1 FROM rom_files
                WHERE rom_files.rom_id = roms.id
                  AND rom_files.file_path <> roms.fs_path
            )
            """
        )
    )

    # A rom_file is "top level" when it either IS the rom (single-file rom,
    # file's full path equals rom's full path) or lives directly inside the
    # rom's folder (file_path equals rom's full path).
    op.execute(
        sa.text(
            """
            UPDATE roms SET top_level_file_count = (
                SELECT COUNT(*) FROM rom_files
                WHERE rom_files.rom_id = roms.id
                  AND (
                    CONCAT(rom_files.file_path, '/', rom_files.file_name)
                      = CONCAT(roms.fs_path, '/', roms.fs_name)
                    OR rom_files.file_path
                      = CONCAT(roms.fs_path, '/', roms.fs_name)
                  )
            )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("top_level_file_count", if_exists=True)
        batch_op.drop_column("multi_file", if_exists=True)
