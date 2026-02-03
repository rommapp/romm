"""Update rom_file.category column enum

Revision ID: 0062_rom_file_category_enum
Revises: 0061_manual_metadata
Create Date: 2026-01-03 10:03:00.00000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0062_rom_file_category_enum"
down_revision = "0061_manual_metadata"
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
            name="romfilecategory",
            create_type=False,
        )
        rom_file_category_enum.create(connection, checkfirst=True)

        # remove bad values before alter
        op.execute(
            """
            UPDATE rom_files
            SET category = NULL
            WHERE category IS NOT NULL
            AND category NOT IN ('GAME', 'DLC', 'HACK', 'MANUAL', 'PATCH', 'UPDATE', 'MOD', 'DEMO', 'TRANSLATION', 'PROTOTYPE')
            """
        )

        # postgres being picky about needing USING
        op.execute(
            """
            ALTER TABLE rom_files
            ALTER COLUMN category TYPE romfilecategory
            USING category::text::romfilecategory
            """
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
            name="romfilecategory",
        )

        with op.batch_alter_table("rom_files", schema=None) as batch_op:
            batch_op.alter_column(
                "category", type_=rom_file_category_enum, nullable=True
            )


def downgrade() -> None:
    pass
