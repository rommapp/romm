"""Key the unique roms index on the full path instead of the file name

A custom library structure lets a platform hold identically-named files in
different folders. The path is indexed through a digest because fs_path plus
fs_name is 5804 bytes of utf8mb4, over InnoDB's 3072-byte key limit; the
(platform_id, fs_name) index stays for the scan loop, demoted to non-unique.

Revision ID: 0126_unique_rom_full_path
Revises: 0125_drop_redundant_indexes
Create Date: 2026-09-07 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from models.rom import FULL_PATH_HASH_LENGTH
from utils.database import full_path_digest_sql

# revision identifiers, used by Alembic.
revision = "0126_unique_rom_full_path"
down_revision = "0125_drop_redundant_indexes"
branch_labels = None
depends_on = None

LOOKUP_INDEX_NAME = "idx_roms_platform_id_fs_name"
UNIQUE_INDEX_NAME = "idx_roms_platform_id_full_path_hash"


def upgrade() -> None:
    op.add_column(
        "roms",
        sa.Column("full_path_hash", sa.String(length=FULL_PATH_HASH_LENGTH)),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            f"UPDATE roms SET full_path_hash = {full_path_digest_sql(connection)}"  # nosec B608
        )
    )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "full_path_hash",
            existing_type=sa.String(length=FULL_PATH_HASH_LENGTH),
            nullable=False,
        )
        batch_op.create_index(
            UNIQUE_INDEX_NAME,
            ["platform_id", "full_path_hash"],
            unique=True,
            if_not_exists=True,
        )
        batch_op.drop_index(LOOKUP_INDEX_NAME, if_exists=True)
        batch_op.create_index(
            LOOKUP_INDEX_NAME,
            ["platform_id", "fs_name"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()

    # Refuse rather than delete the roms a narrower index cannot hold, along
    # with their saves, notes and collection membership.
    duplicates = connection.execute(sa.text("""
            SELECT COUNT(*) FROM (
                SELECT platform_id, fs_name
                FROM roms
                GROUP BY platform_id, fs_name
                HAVING COUNT(*) > 1
            ) AS dupes
            """)).scalar_one()
    if duplicates:
        raise RuntimeError(
            f"Cannot downgrade: {duplicates} file name(s) are shared by more "
            "than one rom on the same platform, which this revision's unique "
            "index forbids. Group the roms table by platform_id and fs_name to "
            "find them, then move or delete the extra copies and retry."
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(LOOKUP_INDEX_NAME, if_exists=True)
        batch_op.create_index(
            LOOKUP_INDEX_NAME,
            ["platform_id", "fs_name"],
            unique=True,
            if_not_exists=True,
        )
        batch_op.drop_index(UNIQUE_INDEX_NAME, if_exists=True)

    op.drop_column("roms", "full_path_hash")
