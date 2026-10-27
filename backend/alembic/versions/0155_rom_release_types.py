"""Release types: what kind of release each ROM is (homebrew, hack, translation...)

`roms.release_types` holds the `ReleaseType` values a ROM's tags imply, or the
ones an editor set by hand, mirrored into `roms_facets` for the gallery filter.

Revision ID: 0155_rom_release_types
Revises: 0154_ownerless_own_only
Create Date: 2026-10-26 00:00:00.000000

"""

from collections import defaultdict

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON, column_names, is_postgresql
from utils.release_types import compute_release_types
from utils.roms_columns import TAG_COLUMNS, ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0155_rom_release_types"
down_revision = "0154_ownerless_own_only"
branch_labels = None
depends_on = None

COLUMN = "release_types"
BATCH_SIZE = 1000

ROMS = sa.table(
    "roms",
    sa.column("id", sa.Integer()),
    sa.column("tags", CustomJSON()),
    sa.column("regions", CustomJSON()),
    sa.column("manual_metadata", CustomJSON()),
    sa.column(COLUMN, CustomJSON()),
)

# Mirrored into roms_facets by the triggers: 0148's list, in its order.
_BASE_MIRRORED_COLUMNS = [
    ("platform_id", "platform_id"),
    ("genres", "generated_genres"),
    ("franchises", "generated_franchises"),
    ("collections", "generated_collections"),
    ("companies", "generated_companies"),
    ("game_modes", "generated_game_modes"),
    ("age_ratings", "generated_age_ratings"),
    ("player_count", "generated_player_count"),
    ("regions", "regions"),
    ("languages", "languages"),
    ("tags", "tags"),
    ("publishers", "generated_publishers"),
    ("developers", "generated_developers"),
    ("igdb_id", "igdb_id"),
    ("ss_id", "ss_id"),
    ("moby_id", "moby_id"),
    ("launchbox_id", "launchbox_id"),
    ("ra_id", "ra_id"),
    ("hasheous_id", "hasheous_id"),
    ("tgdb_id", "tgdb_id"),
    ("flashpoint_id", "flashpoint_id"),
    ("hltb_id", "hltb_id"),
    ("demozoo_id", "demozoo_id"),
    ("pouet_id", "pouet_id"),
    ("csdb_id", "csdb_id"),
    ("gamelist_id", "gamelist_id"),
    ("libretro_id", "libretro_id"),
    ("steam_id", "steam_id"),
    *[(facet, generated) for generated, facet in TAG_COLUMNS],
    ("min_age", "min_age"),
]

_MYSQL_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


def _rebuild_triggers(pg: bool, mirrored: list[tuple[str, str]]) -> None:
    """Recreate the roms_facets sync triggers over the given column list."""
    targets = ", ".join(target for target, _ in mirrored)
    values = ", ".join(f"NEW.{source}" for _, source in mirrored)

    if pg:
        assignments = ", ".join(
            f"{target} = EXCLUDED.{target}" for target, _ in mirrored
        )
        op.execute(f"""
CREATE OR REPLACE FUNCTION romm_sync_rom_facets() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO roms_facets (rom_id, {targets})
    VALUES (NEW.id, {values})
    ON CONFLICT (rom_id) DO UPDATE SET
        {assignments},
        updated_at = NOW();
    RETURN NULL;
END $$
""")  # nosec B608
        return

    updates = ",\n".join(f"{target} = VALUES({target})" for target, _ in mirrored)
    body = (
        f"INSERT INTO roms_facets (rom_id, {targets})\n"  # nosec B608
        f"VALUES (NEW.id, {values})\n"
        f"ON DUPLICATE KEY UPDATE\n{updates},\nupdated_at = CURRENT_TIMESTAMP"
    )
    for name, timing in _MYSQL_TRIGGERS.items():
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
        op.execute(f"CREATE TRIGGER {name} {timing} ON roms\nFOR EACH ROW\n{body}")


def _fill_release_types(conn: sa.Connection) -> None:
    """Store every ROM's computed list, `[]` included, for the triggers to mirror."""
    last_id = 0
    while rows := conn.execute(
        # A JSON path keeps the rest of the manual metadata blob out of the read.
        sa.select(
            ROMS.c.id,
            ROMS.c.tags,
            ROMS.c.regions,
            ROMS.c.manual_metadata[COLUMN],
        )
        .where(ROMS.c.id > last_id)
        .order_by(ROMS.c.id)
        .limit(BATCH_SIZE)
    ).all():
        # One statement per distinct value, since a round trip per row dominates.
        ids_by_types: defaultdict[tuple[str, ...], list[int]] = defaultdict(list)
        for rom_id, tags, regions, manual in rows:
            types = compute_release_types(
                {"tags": tags, "regions": regions, "manual_metadata": {COLUMN: manual}}
            )
            ids_by_types[tuple(types)].append(rom_id)
        for types, ids in ids_by_types.items():
            conn.execute(
                sa.update(ROMS).where(ROMS.c.id.in_(ids)).values({COLUMN: list(types)})
            )
        last_id = rows[-1][0]


def upgrade() -> None:
    conn = op.get_bind()

    ensure_roms_columns(conn)
    op.add_column(
        "roms_facets",
        sa.Column(COLUMN, CustomJSON(), nullable=True),
        if_not_exists=True,
    )
    _rebuild_triggers(is_postgresql(conn), _BASE_MIRRORED_COLUMNS + [(COLUMN, COLUMN)])
    _fill_release_types(conn)


def downgrade() -> None:
    conn = op.get_bind()

    _rebuild_triggers(is_postgresql(conn), _BASE_MIRRORED_COLUMNS)
    # MySQL has no DROP COLUMN IF EXISTS.
    for table in ("roms_facets", "roms"):
        if COLUMN in column_names(conn, table):
            op.drop_column(table, COLUMN)
