"""Add the per-file title id and rom-converto metadata columns on rom_files.

Revision ID: 0147_rom_file_binary_metadata
Revises: 0146_roms_search_aliases
Create Date: 2026-09-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0147_rom_file_binary_metadata"
down_revision = "0146_roms_search_aliases"
branch_labels = None
depends_on = None


def _columns() -> list[sa.Column]:
    return [
        sa.Column("title_id", sa.String(length=100), nullable=True),
        # BigInteger: Switch title versions are u32 and can exceed signed int32.
        sa.Column("title_version", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("serial", sa.String(length=255), nullable=True),
        # A `RomFileContentType` value, stored as plain text.
        sa.Column("content_type", sa.String(length=20), nullable=True),
        sa.Column("display_version", sa.String(length=255), nullable=True),
        sa.Column("regions", CustomJSON(), nullable=True),
        sa.Column("languages", CustomJSON(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("min_firmware_version", sa.String(length=255), nullable=True),
        sa.Column("is_compressed", sa.Boolean(), nullable=True),
        sa.Column("compression", sa.String(length=255), nullable=True),
        sa.Column("file_format", sa.String(length=255), nullable=True),
        sa.Column("uncompressed_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("converto_read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("icon_path", sa.String(length=1024), nullable=True),
        sa.Column("banner_path", sa.String(length=1024), nullable=True),
        sa.Column("background_path", sa.String(length=1024), nullable=True),
    ]


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        for column in _columns():
            batch_op.add_column(column, if_not_exists=True)
        batch_op.create_index(
            "idx_rom_files_title_id",
            ["title_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_index("idx_rom_files_title_id", if_exists=True)
        for column in reversed(_columns()):
            batch_op.drop_column(column.name, if_exists=True)
