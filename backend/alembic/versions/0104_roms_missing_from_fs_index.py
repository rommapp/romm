"""Add composite index on roms (missing_from_fs, name_sort_key)

Settings -> Library Management -> Missing filters every request on
``missing_from_fs`` and orders it by ``name_sort_key``. Neither column was part
of an index covering that filter, so both the char index and the ordered id
index scanned the whole ``roms`` table, which carries every provider's raw
metadata blobs and is multi-gigabyte on a large library.

Revision ID: 0104_roms_missing_from_fs_index
Revises: 0103_roms_facets_provider_ids
Create Date: 2026-07-30 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0104_roms_missing_from_fs_index"
down_revision = "0103_roms_facets_provider_ids"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_missing_from_fs"
INDEX_COLUMNS = ["missing_from_fs", "name_sort_key"]


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            INDEX_NAME,
            INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
