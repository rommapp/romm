"""Update rom_file.category column enum to include screenshots.

Revision ID: 0085_rom_category_screenshot
Revises: 0084_add_roms_search_index
Create Date: 2026-06-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0085_rom_category_screenshot"
down_revision = "0084_add_roms_search_index"
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
                "ALTER TYPE romfilecategory ADD VALUE IF NOT EXISTS 'SCREENSHOT'"
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
            "SCREENSHOT",
            name="romfilecategory",
        )
        with op.batch_alter_table("rom_files", schema=None) as batch_op:
            batch_op.alter_column(
                "category", type_=rom_file_category_enum, nullable=True
            )


def downgrade() -> None:
    # PostgreSQL cannot remove enum values, so the downgrade is a no-op there.
    # On other backends, narrow the enum back to its pre-screenshot set. Any
    # rows still holding the new value would block this, but the upload flow
    # is additive and a re-upgrade is a no-op.
    connection = op.get_bind()

    if is_postgresql(connection):
        return

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
        batch_op.alter_column("category", type_=rom_file_category_enum, nullable=True)
