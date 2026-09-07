"""Add the binary identity columns on roms: title_id, save_target and
save_target_layout.

Revision ID: 0116_sigil_title_ids
Revises: 0115_add_steam_metadata
Create Date: 2026-07-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0116_sigil_title_ids"
down_revision = "0115_add_steam_metadata"
branch_labels = None
depends_on = None

SAVE_TARGET_LAYOUT_VALUES = (
    "FOLDER_EXACT",
    "FOLDER_PREFIX",
    "FILE_EXACT",
    "FILE_PREFIX",
    "FOLDER_SPLIT",
)


def _save_target_layout_enum(connection) -> sa.Enum:
    if is_postgresql(connection):
        enum = ENUM(
            *SAVE_TARGET_LAYOUT_VALUES, name="savetargetlayout", create_type=False
        )
        enum.create(connection, checkfirst=True)
        return enum
    return sa.Enum(*SAVE_TARGET_LAYOUT_VALUES, name="savetargetlayout")


def upgrade() -> None:
    connection = op.get_bind()
    save_target_layout_enum = _save_target_layout_enum(connection)

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("title_id", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("save_target", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("save_target_layout", save_target_layout_enum, nullable=True),
            if_not_exists=True,
        )
        batch_op.create_index(
            "idx_roms_title_id",
            ["title_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_title_id", if_exists=True)
        batch_op.drop_column("save_target_layout", if_exists=True)
        batch_op.drop_column("save_target", if_exists=True)
        batch_op.drop_column("title_id", if_exists=True)

    connection = op.get_bind()
    if is_postgresql(connection):
        ENUM(name="savetargetlayout").drop(connection, checkfirst=True)
