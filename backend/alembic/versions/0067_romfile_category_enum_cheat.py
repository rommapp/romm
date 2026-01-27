"""Update rom_file.category column enum to include cheats

Revision ID: 0067_romfile_category_enum_cheat
Revises: 0066_fix_empty_flashpoint_id
Create Date: 2026-01-25 10:03:00.00000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0067_romfile_category_enum_cheat"
down_revision = "0066_fix_empty_flashpoint_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    if is_postgresql(connection):
        rom_file_category_enum = ENUM(
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
            name="romfilecategory",
            create_type=False,
        )
        rom_file_category_enum.create(connection, checkfirst=True)
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
            name="romfilecategory",
        )

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column("category", type_=rom_file_category_enum, nullable=True)


def downgrade() -> None:
    pass
