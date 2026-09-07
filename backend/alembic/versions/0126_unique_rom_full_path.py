"""Widen the unique roms index to (platform_id, fs_path, fs_name)

A custom library structure lets a platform hold identically-named files in
different folders, which the (platform_id, fs_name) index rejected. Adding
fs_path keeps the guarantee that no two roms share a full path, and still
rejects a duplicate physical game (they all live in one folder).

Duplicates that pre-date the widening cannot exist: the narrower index already
forbade them.

Revision ID: 0126_unique_rom_full_path
Revises: 0125_drop_redundant_indexes
Create Date: 2026-09-07 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0126_unique_rom_full_path"
down_revision = "0125_drop_redundant_indexes"
branch_labels = None
depends_on = None

OLD_INDEX_NAME = "idx_roms_platform_id_fs_name"
NEW_INDEX_NAME = "idx_roms_platform_id_fs_path_fs_name"


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            NEW_INDEX_NAME,
            ["platform_id", "fs_path", "fs_name"],
            unique=True,
            if_not_exists=True,
        )
        batch_op.drop_index(OLD_INDEX_NAME, if_exists=True)


def downgrade() -> None:
    connection = op.get_bind()

    # The narrower index cannot tolerate the same name in two folders.
    connection.execute(sa.text("""
            DELETE FROM roms
            WHERE id NOT IN (
                SELECT keep_id FROM (
                    SELECT MIN(id) AS keep_id
                    FROM roms
                    GROUP BY platform_id, fs_name
                ) AS keepers
            )
            """))

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            OLD_INDEX_NAME,
            ["platform_id", "fs_name"],
            unique=True,
            if_not_exists=True,
        )
        batch_op.drop_index(NEW_INDEX_NAME, if_exists=True)
