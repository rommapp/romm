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

Cross-engine notes:
- MariaDB JSON_EXTRACT returns a quoted scalar, so JSON_UNQUOTE runs before the
  result reaches the varchar.
- Both expressions truncate with LEFT, because `regions` has no length cap of
  its own: an unrecognized `[Reg-...]` tag is kept verbatim, and a value longer
  than the column would otherwise fail the INSERT under strict mode.

Revision ID: 0108_roms_primary_region
Revises: 0107_roms_dedup_cover_index
Create Date: 2026-08-21 00:00:00.000000

"""

from alembic import op  # type: ignore[attr-defined]

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0108_roms_primary_region"
down_revision = "0107_roms_dedup_cover_index"
branch_labels = None
depends_on = None

COLUMN_NAME = "generated_primary_region"
COLUMN_LENGTH = 50

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
NEW_INDEX_COLUMNS = [*_INDEX_HEAD, COLUMN_NAME, "id"]

_MARIA_EXPR = f"LEFT(JSON_UNQUOTE(JSON_EXTRACT(regions, '$[0]')), {COLUMN_LENGTH})"
_POSTGRES_EXPR = f"left(regions ->> 0, {COLUMN_LENGTH})"


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
    expr = _POSTGRES_EXPR if is_postgresql(op.get_bind()) else _MARIA_EXPR
    op.execute(
        f"ALTER TABLE roms ADD COLUMN {COLUMN_NAME} VARCHAR({COLUMN_LENGTH}) "  # nosec B608
        f"GENERATED ALWAYS AS ({expr}) STORED"
    )
    _rebuild_index(NEW_INDEX_COLUMNS)


def downgrade() -> None:
    _rebuild_index(OLD_INDEX_COLUMNS)
    op.execute(f"ALTER TABLE roms DROP COLUMN {COLUMN_NAME}")  # nosec B608
