"""Add FOLDER_SPLIT to the saveusage enum (3DS saves nest the id across
two directory levels).

Revision ID: 0115_sigil_folder_split
Revises: 0114_sigil_title_version
Create Date: 2026-07-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0115_sigil_folder_split"
down_revision = "0114_sigil_title_version"
branch_labels = None
depends_on = None

SAVE_USAGE_VALUES = (
    "FOLDER_EXACT",
    "FOLDER_PREFIX",
    "FILE_EXACT",
    "FILE_PREFIX",
    "FOLDER_SPLIT",
)


def upgrade() -> None:
    connection = op.get_bind()

    if is_postgresql(connection):
        # ALTER TYPE ... ADD VALUE must run outside alembic's transaction.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE saveusage ADD VALUE IF NOT EXISTS 'FOLDER_SPLIT'")
    else:
        save_usage_enum = sa.Enum(*SAVE_USAGE_VALUES, name="saveusage")
        with op.batch_alter_table("roms", schema=None) as batch_op:
            batch_op.alter_column("save_usage", type_=save_usage_enum, nullable=True)


def downgrade() -> None:
    # PostgreSQL cannot drop enum values; leave FOLDER_SPLIT in place. On
    # MariaDB, narrow the enum back after clearing any rows that used it.
    connection = op.get_bind()
    if is_postgresql(connection):
        return

    op.execute("UPDATE roms SET save_usage = NULL WHERE save_usage = 'FOLDER_SPLIT'")
    reverted_enum = sa.Enum(
        "FOLDER_EXACT",
        "FOLDER_PREFIX",
        "FILE_EXACT",
        "FILE_PREFIX",
        name="saveusage",
    )
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column("save_usage", type_=reverted_enum, nullable=True)
