"""Metadata columns the recommendations index scores on

Three changes that all rewrite `roms`, done in one pass so the table is
rebuilt once instead of three times:

* IGDB keywords, themes and player perspectives become generated facet
  columns, projected by `roms_metadata` and mirrored into `roms_facets`.
* IGDB's vote count is stored alongside the rating, so the cold-start feed
  can shrink a rating toward the library mean in proportion to how little
  evidence backs it. Without it, sixteen games with one perfect provider
  score outranked every broadly-liked classic.
* Steam joins the COALESCE chains behind the existing generated columns.
  0115 stored `steam_metadata` but left it out of them, so its genres,
  companies, release date and Metacritic score were persisted and surfaced
  nowhere.

The array/date/rating expressions are 0098 and 0112's, with Steam appended
at the lowest precedence. Franchises, collections, age ratings and player
count are untouched, since Steam supplies none of them.

The column expressions live in `utils.roms_columns`, which adds and redefines
them in the single table copy shared by every 5.3.0 revision that widens
`roms`; a database that reached this revision through that copy has nothing
left to rebuild here.

Existing libraries carry no keywords or vote counts until they are fetched:
the columns read the metadata blob, so they stay empty until a rescan or
`tools/backfill_igdb_tags.py` populates the source.

Revision ID: 0123_recommendation_metadata
Revises: 0122_rom_similarity
Create Date: 2026-08-08 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON, is_postgresql
from utils.roms_columns import (
    RATING_COUNT_COLUMN,
    ROMS_METADATA_VIEW_COLUMNS,
    STEAM_METADATA_COLUMN,
    TAG_COLUMNS,
    VIEW,
    ensure_roms_columns,
    rebuild_generated_columns,
    roms_metadata_view_sql,
    steam_fed_columns,
)

# revision identifiers, used by Alembic.
revision = "0123_recommendation_metadata"
down_revision = "0122_rom_similarity"
branch_labels = None
depends_on = None

# roms_facets mirrors whose value this migration can change: the Steam-fed
# columns plus the tag columns it adds.
_FACET_COLUMNS = [
    ("genres", "generated_genres"),
    ("companies", "generated_companies"),
    ("game_modes", "generated_game_modes"),
    ("publishers", "generated_publishers"),
    ("developers", "generated_developers"),
] + [(facet, generated) for generated, facet in TAG_COLUMNS]

# virtual_collection_roms membership types fed by the rebuilt columns.
_VC_TYPES = [
    ("genre", "generated_genres"),
    ("mode", "generated_game_modes"),
    ("company", "generated_companies"),
    ("publisher", "generated_publishers"),
    ("developer", "generated_developers"),
]
_VC_TABLE = "virtual_collection_roms"
_VC_NAME_MAX_LENGTH = 400
_VC_COLUMNS = "rom_id, type, name, path_cover_s, path_cover_l, created_at, updated_at"

# What `roms_metadata` projected before this revision, for the downgrade.
_BASE_VIEW_COLUMNS = [
    ("generated_genres", "genres"),
    ("generated_franchises", "franchises"),
    ("generated_collections", "collections"),
    ("generated_companies", "companies"),
    ("generated_game_modes", "game_modes"),
    ("generated_age_ratings", "age_ratings"),
    ("generated_first_release_date", "first_release_date"),
    ("generated_average_rating", "average_rating"),
    ("generated_player_count", "player_count"),
    ("generated_publishers", "publishers"),
    ("generated_developers", "developers"),
]

# Mirrored into roms_facets by the triggers: 0115's list, in its order, with
# the tag columns appended by the rebuild below.
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
]
_MIRRORED_COLUMNS = _BASE_MIRRORED_COLUMNS + [
    (facet, generated) for generated, facet in TAG_COLUMNS
]

_MYSQL_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


def _rebuild_triggers(pg: bool, mirrored: list[tuple[str, str]]) -> None:
    """Recreate the roms_facets sync triggers over the given column list.

    The triggers copy a fixed set of columns, so adding one means replacing
    them wholesale rather than amending in place.
    """
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


def _sync_facets(pg: bool, columns: list[tuple[str, str]]) -> None:
    """Re-mirror roms_facets from roms.

    The triggers only fire on a write to `roms`, and rebuilding a generated
    column is not one.
    """
    if pg:
        assignments = ", ".join(
            f"{facet} = r.{generated}" for facet, generated in columns
        )
        op.execute(
            f"UPDATE roms_facets f SET {assignments} "  # nosec B608
            "FROM roms r WHERE r.id = f.rom_id"
        )
    else:
        assignments = ", ".join(
            f"f.{facet} = r.{generated}" for facet, generated in columns
        )
        op.execute(
            f"UPDATE roms_facets f JOIN roms r ON r.id = f.rom_id "  # nosec B608
            f"SET {assignments}"
        )


def _has_steam_rows() -> bool:
    probe = f"SELECT 1 FROM roms WHERE {STEAM_METADATA_COLUMN} IS NOT NULL LIMIT 1"  # nosec B608
    return op.get_bind().execute(sa.text(probe)).first() is not None


def _vc_rows(pg: bool) -> str:
    """Membership rows for the Steam ROMs, per 0112's shape."""
    branches = []
    for type_, column in _VC_TYPES:
        if pg:
            array = (
                f"CASE WHEN jsonb_typeof(r.{column}) = 'array' "
                f"THEN r.{column} ELSE '[]'::jsonb END"
            )
            source = f"roms r CROSS JOIN LATERAL jsonb_array_elements_text({array}) AS j(value)"
        else:
            source = (
                f"roms r CROSS JOIN JSON_TABLE(r.{column}, '$[*]' "
                f"COLUMNS (value TEXT PATH '$')) j"
            )
        branches.append(
            f"SELECT DISTINCT r.id, '{type_}', LEFT(j.value, {_VC_NAME_MAX_LENGTH}), "  # nosec B608
            f"r.path_cover_s, r.path_cover_l, NOW(), NOW()\n"
            f"FROM {source}\n"
            f"WHERE r.{STEAM_METADATA_COLUMN} IS NOT NULL AND j.value IS NOT NULL AND j.value != ''"
        )
    return "\nUNION ALL\n".join(branches)


def _refresh_steam_collections(pg: bool) -> None:
    """Rebuild the virtual collections whose membership Steam can change.

    Only Steam-matched rows can move, so the rest are left alone.
    """
    if not _has_steam_rows():
        return

    types = ", ".join(f"'{type_}'" for type_, _ in _VC_TYPES)
    op.execute(
        f"DELETE FROM {_VC_TABLE} WHERE type IN ({types}) "  # nosec B608
        f"AND rom_id IN (SELECT id FROM roms WHERE {STEAM_METADATA_COLUMN} IS NOT NULL)"
    )
    insert = "INSERT INTO" if pg else "INSERT IGNORE INTO"
    conflict = "\nON CONFLICT DO NOTHING" if pg else ""
    op.execute(
        f"{insert} {_VC_TABLE} ({_VC_COLUMNS})\n{_vc_rows(pg)}{conflict}"  # nosec B608
    )


def upgrade() -> None:
    connection = op.get_bind()
    pg = is_postgresql(connection)

    ensure_roms_columns(connection)
    # 0112 may have left the view at its own projection.
    op.execute(f"DROP VIEW IF EXISTS {VIEW}")
    op.execute(roms_metadata_view_sql(pg, ROMS_METADATA_VIEW_COLUMNS))

    for _, facet in TAG_COLUMNS:
        op.add_column(
            "roms_facets",
            sa.Column(facet, CustomJSON(), nullable=True),
            if_not_exists=True,
        )

    _sync_facets(pg, _FACET_COLUMNS)
    _rebuild_triggers(pg, _MIRRORED_COLUMNS)
    _refresh_steam_collections(pg)


def downgrade() -> None:
    connection = op.get_bind()
    pg = is_postgresql(connection)

    rebuild_generated_columns(
        connection,
        add=steam_fed_columns(pg, with_steam=False),
        drop=[name for name, _ in TAG_COLUMNS] + [RATING_COUNT_COLUMN],
        view_columns=_BASE_VIEW_COLUMNS,
    )

    for _, facet in TAG_COLUMNS:
        op.drop_column("roms_facets", facet, if_exists=True)

    _sync_facets(pg, [entry for entry in _FACET_COLUMNS if entry[0] not in {facet for _, facet in TAG_COLUMNS}])  # fmt: skip
    _rebuild_triggers(pg, _BASE_MIRRORED_COLUMNS)
    _refresh_steam_collections(pg)
