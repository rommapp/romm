"""Update rom_file.category column enum to include soundtracks, and add
audio_meta JSON column for tag/duration/cover metadata.

Revision ID: 0080_rom_category_soundtrack
Revises: 0079_add_rom_files_rom_id_index
Create Date: 2026-04-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0080_rom_category_soundtrack"
down_revision = "0079_add_rom_files_rom_id_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    if is_postgresql(connection):
        # `ALTER TYPE ... ADD VALUE` must run outside a transaction in PostgreSQL.
        # autocommit_block breaks out of alembic's wrapping transaction for
        # exactly this operation.
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE romfilecategory ADD VALUE IF NOT EXISTS 'SOUNDTRACK'"
            )

        # audio_meta column (added separately so the enum change sticks even
        # if the JSON column already exists from a partial prior run).
        op.add_column(
            "rom_files",
            sa.Column("audio_meta", CustomJSON(), nullable=True),
            if_not_exists=True,
        )
    else:
        rom_file_category_enum = sa.Enum(
            "GAME",
            "DLC",
            "HACK",
            "MANUAL",
            "PATCH",
            "UPDATE",
            "MOD",
            "DEMO",
            "TRANSLATION",
            "PROTOTYPE",
            "CHEAT",
            "SOUNDTRACK",
            name="romfilecategory",
        )
        with op.batch_alter_table("rom_files", schema=None) as batch_op:
            batch_op.alter_column(
                "category", type_=rom_file_category_enum, nullable=True
            )
            batch_op.add_column(
                sa.Column("audio_meta", CustomJSON(), nullable=True),
                if_not_exists=True,
            )


def downgrade() -> None:
    # PostgreSQL cannot remove enum values, so on downgrade we only drop the
    # audio_meta column and leave SOUNDTRACK in the enum. Any rows that still
    # hold the new value keep working; a re-upgrade is a no-op.
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_column("audio_meta", if_exists=True)
