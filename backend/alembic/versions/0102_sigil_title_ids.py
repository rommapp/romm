"""Add sigil-extracted title id columns: per-file title_id/save_id on
rom_files, plus rom-level title_id/save_id/save_usage on roms.

Revision ID: 0102_sigil_title_ids
Revises: 0101_virtual_collection_roms
Create Date: 2026-07-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0102_sigil_title_ids"
down_revision = "0101_virtual_collection_roms"
branch_labels = None
depends_on = None

SAVE_USAGE_VALUES = ("FOLDER_EXACT", "FOLDER_PREFIX", "FILE_EXACT", "FILE_PREFIX")


def _save_usage_enum(connection) -> sa.Enum:
    if is_postgresql(connection):
        enum = ENUM(*SAVE_USAGE_VALUES, name="saveusage", create_type=False)
        enum.create(connection, checkfirst=True)
        return enum
    return sa.Enum(*SAVE_USAGE_VALUES, name="saveusage")


def upgrade() -> None:
    connection = op.get_bind()
    save_usage_enum = _save_usage_enum(connection)

    op.add_column(
        "rom_files",
        sa.Column("title_id", sa.String(length=100), nullable=True),
        if_not_exists=True,
    )
    op.add_column(
        "rom_files",
        sa.Column("save_id", sa.String(length=100), nullable=True),
        if_not_exists=True,
    )
    op.add_column(
        "roms",
        sa.Column("title_id", sa.String(length=100), nullable=True),
        if_not_exists=True,
    )
    op.add_column(
        "roms",
        sa.Column("save_id", sa.String(length=100), nullable=True),
        if_not_exists=True,
    )
    op.add_column(
        "roms",
        sa.Column("save_usage", save_usage_enum, nullable=True),
        if_not_exists=True,
    )

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.create_index(
            "idx_rom_files_title_id",
            ["title_id"],
            unique=False,
            if_not_exists=True,
        )
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            "idx_roms_title_id",
            ["title_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_title_id", if_exists=True)
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_index("idx_rom_files_title_id", if_exists=True)

    op.drop_column("roms", "save_usage", if_exists=True)
    op.drop_column("roms", "save_id", if_exists=True)
    op.drop_column("roms", "title_id", if_exists=True)
    op.drop_column("rom_files", "save_id", if_exists=True)
    op.drop_column("rom_files", "title_id", if_exists=True)

    connection = op.get_bind()
    if is_postgresql(connection):
        ENUM(name="saveusage").drop(connection, checkfirst=True)
