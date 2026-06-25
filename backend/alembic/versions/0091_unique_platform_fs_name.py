"""Enforce unique (platform_id, fs_name) on roms

A platform folder can't physically hold two entries with the same name, so a
ROM is uniquely identified by (platform_id, fs_name). The index covering this
pair was non-unique, which let two concurrent scans (e.g. the manual scan the
patcher fires after uploading a patched ROM, racing a filesystem-watcher or
scheduled scan) both insert the same ROM, producing duplicate library entries.

This migration removes any pre-existing duplicates (keeping the lowest id) and
upgrades the index to unique so the duplicate can never be created again.

Revision ID: 0091_unique_platform_fs_name
Revises: 0090_roms_sibling_cover_index
Create Date: 2026-06-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0091_unique_platform_fs_name"
down_revision = "0090_roms_sibling_cover_index"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_platform_id_fs_name"
INDEX_COLUMNS = ["platform_id", "fs_name"]


def upgrade() -> None:
    connection = op.get_bind()

    # Drop duplicate roms sharing (platform_id, fs_name), keeping the lowest id.
    # The nested derived table is required so MySQL/MariaDB don't reject reading
    # the same table being deleted from; it's a valid no-op on PostgreSQL too.
    # Dependent rows (files, user props, assets, collections, ...) are removed by
    # their ON DELETE CASCADE foreign keys.
    connection.execute(
        sa.text(
            """
            DELETE FROM roms
            WHERE id NOT IN (
                SELECT keep_id FROM (
                    SELECT MIN(id) AS keep_id
                    FROM roms
                    GROUP BY platform_id, fs_name
                ) AS keepers
            )
            """
        )
    )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
        batch_op.create_index(
            INDEX_NAME,
            INDEX_COLUMNS,
            unique=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
        batch_op.create_index(
            INDEX_NAME,
            INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )
