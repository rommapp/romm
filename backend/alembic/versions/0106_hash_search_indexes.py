"""Index the hash columns searched by the gallery search box

Searching by a CRC32/MD5/SHA-1/RA digest now matches the hash columns on
``roms`` and ``rom_files``. Neither table had an index on any of them, so every
such search scanned both tables in full.

Revision ID: 0106_hash_search_indexes
Revises: 0105_fix_gamelist_epoch_ms
Create Date: 2026-07-31 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0106_hash_search_indexes"
down_revision = "0105_fix_gamelist_epoch_ms"
branch_labels = None
depends_on = None

HASH_INDEXES: dict[str, tuple[str, ...]] = {
    "roms": ("crc_hash", "md5_hash", "sha1_hash", "ra_hash"),
    "rom_files": ("crc_hash", "md5_hash", "sha1_hash", "ra_hash", "chd_sha1_hash"),
}


def upgrade() -> None:
    for table, columns in HASH_INDEXES.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in columns:
                batch_op.create_index(
                    f"idx_{table}_{column}",
                    [column],
                    unique=False,
                    if_not_exists=True,
                )


def downgrade() -> None:
    for table, columns in HASH_INDEXES.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in columns:
                batch_op.drop_index(f"idx_{table}_{column}", if_exists=True)
