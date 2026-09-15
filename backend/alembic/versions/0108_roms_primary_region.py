"""Add a generated primary_region column and cover it in the dedup index

Region priority decides which sibling represents its group in the gallery, so
the group_by_meta_id dedup window has to read each rom's region. `roms.regions`
is JSON, which no covering index can carry (a prefix index cannot answer
JSON_CONTAINS on its own), and 0107 measured what one uncovered reference costs
that window: the plan drops from `type=index, Using index` to `type=ALL,
key=NULL`, four times per gallery page load.

A STORED generated column over `regions[0]` gives the window a scalar the index
can cover. The engine computes it at write time and keeps it in sync, so no
scan hook and no backfill are needed: ALTER TABLE populates existing rows, and
multi-region names like "(USA, Europe)" resolve to the first tag, which is the
release's primary market.

`idx_roms_sibling_cover` grows by a varchar(50), well inside both the InnoDB
3072-byte key limit and PostgreSQL's btree tuple limit.

The column's expression lives in `utils.roms_columns`, which adds it along with
every other column the 5.3.0 revisions put on `roms` in a single table copy. The
downgrade takes back whatever of that set is still there: a chain that stopped
before a later revision leaves that revision's columns to this one.

Revision ID: 0108_roms_primary_region
Revises: 0107_roms_dedup_cover_index
Create Date: 2026-08-21 00:00:00.000000

"""

from alembic import op  # type: ignore[attr-defined]

from utils.roms_columns import (
    PRIMARY_REGION_COLUMN,
    drop_roms_columns,
    ensure_roms_columns,
)

# revision identifiers, used by Alembic.
revision = "0108_roms_primary_region"
down_revision = "0107_roms_dedup_cover_index"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_sibling_cover"
_INDEX_HEAD = [
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
]
OLD_INDEX_COLUMNS = [*_INDEX_HEAD, "id"]
NEW_INDEX_COLUMNS = [*_INDEX_HEAD, PRIMARY_REGION_COLUMN, "id"]


def _rebuild_index(columns: list[str]) -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
        batch_op.create_index(
            INDEX_NAME,
            columns,
            unique=False,
            if_not_exists=True,
        )


def upgrade() -> None:
    ensure_roms_columns(op.get_bind())
    _rebuild_index(NEW_INDEX_COLUMNS)


def downgrade() -> None:
    _rebuild_index(OLD_INDEX_COLUMNS)
    drop_roms_columns(op.get_bind())
