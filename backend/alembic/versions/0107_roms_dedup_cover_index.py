"""Extend the sibling covering index to cover the group_by_meta_id dedup

0090 added `idx_roms_sibling_cover` for the sibling_roms self-join. The
group_by_meta_id dedup window in `filter_roms` reads the same shape, but two of
its inputs are missing from that index: `flashpoint_id` (the last provider in
the partition's COALESCE chain) and `fs_name_no_ext` (the tiebreaker the window
sorts each partition by). A covering index has to carry every referenced
column, so those two omissions dropped the window to a full scan of the wide
roms row -- JSON metadata blobs and all -- once per query.

The gallery runs that window up to four times per page load (page, count,
char_index, rom_id_index), so the scan is paid repeatedly. Measured on a
92.8k-rom MariaDB copy with a 256 MB buffer pool against a 963 MB roms table:
each of those four queries went 5.4-5.6s -> 0.8-1.1s (21.9s -> 4.0s combined),
with EXPLAIN moving from `type=ALL, key=NULL` to `type=index, Using index`.

Adding `fs_name_no_ext` (varchar 450) widens the index, but real names are far
shorter than the column's maximum: on that dataset the index grew 4 MB -> 7 MB.

The wider index costs the sibling_roms join a little more to scan (~170ms ->
~209ms for a 72-rom page, measured over alternating A/B runs). Keeping the old
narrow index alongside a second dedup-only one recovers that, but the two would
share their first eight columns, and per page load the totals came out the same
(2.13s vs 2.12s), so one index wins on write amplification and on not letting
the two consumers drift apart again.

Revision ID: 0107_roms_dedup_cover_index
Revises: 0106_hash_search_indexes
Create Date: 2026-08-01 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0107_roms_dedup_cover_index"
down_revision = "0106_hash_search_indexes"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_sibling_cover"
OLD_INDEX_COLUMNS = [
    "platform_id",
    "igdb_id",
    "moby_id",
    "ss_id",
    "launchbox_id",
    "ra_id",
    "hasheous_id",
    "tgdb_id",
    "id",
]
NEW_INDEX_COLUMNS = [
    "platform_id",
    "igdb_id",
    "moby_id",
    "ss_id",
    "launchbox_id",
    "ra_id",
    "hasheous_id",
    "tgdb_id",
    "flashpoint_id",
    "fs_name_no_ext",
    "id",
]


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
        batch_op.create_index(
            INDEX_NAME,
            NEW_INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
        batch_op.create_index(
            INDEX_NAME,
            OLD_INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )
