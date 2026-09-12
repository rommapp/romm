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

COLUMN_NAME = "full_path_hash"
LOOKUP_INDEX_NAME = "idx_roms_platform_id_fs_name"
UNIQUE_INDEX_NAME = "idx_roms_platform_id_full_path_hash"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    column = next(
        (
            column
            for column in inspector.get_columns("roms")
            if column["name"] == COLUMN_NAME
        ),
        None,
    )
    indexes = {index["name"]: index for index in inspector.get_indexes("roms")}

    # Every step is guarded so a re-run after a partial failure recovers
    # cleanly. MySQL/MariaDB auto-commit each DDL statement, so a crash
    # mid-migration leaves the column behind without advancing the alembic
    # version, and an unguarded ADD COLUMN then fails every start after it.
    if column is None:
        op.add_column(
            "roms",
            sa.Column(COLUMN_NAME, sa.String(length=FULL_PATH_HASH_LENGTH)),
        )

    connection.execute(
        sa.text(
            f"UPDATE roms SET {COLUMN_NAME} = {full_path_digest_sql(connection)} "  # nosec B608
            f"WHERE {COLUMN_NAME} IS NULL"
        )
    )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        if column is None or column["nullable"]:
            batch_op.alter_column(
                COLUMN_NAME,
                existing_type=sa.String(length=FULL_PATH_HASH_LENGTH),
                nullable=False,
            )
        if UNIQUE_INDEX_NAME not in indexes:
            batch_op.create_index(
                UNIQUE_INDEX_NAME,
                ["platform_id", COLUMN_NAME],
                unique=True,
                if_not_exists=True,
            )
        # 0091 made this index unique; the digest carries that role now.
        if LOOKUP_INDEX_NAME not in indexes or indexes[LOOKUP_INDEX_NAME]["unique"]:
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
