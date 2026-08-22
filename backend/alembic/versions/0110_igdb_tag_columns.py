"""Surface IGDB keywords, themes and player perspectives as facet columns

The recommendations index scores on `roms_facets` / `roms_metadata` rather than
the raw provider blobs, so these three fields have to travel the same route as
genres and franchises: a STORED generated column on `roms`, exposed by the
`roms_metadata` view and mirrored into `roms_facets` by its triggers.

Only IGDB supplies them (plus `manual_metadata`, so a user override still
wins), which makes the COALESCE chain much shorter than the existing facets.

Existing libraries carry no such data until it is fetched -- the columns are
generated from the metadata blob, so they stay empty until a rescan or
`tools/backfill_igdb_tags.py` populates the source.

Revision ID: 0110_igdb_tag_columns
Revises: 0109_rom_similarity
Create Date: 2026-08-08 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0110_igdb_tag_columns"
down_revision = "0109_rom_similarity"
branch_labels = None
depends_on = None


# (generated column, roms_facets column). A user override in `manual_metadata`
# takes precedence, matching every other generated facet.
_TAG_COLUMNS = [
    ("generated_keywords", "keywords"),
    ("generated_themes", "themes"),
    ("generated_player_perspectives", "player_perspectives"),
]
_SOURCES = ["manual_metadata", "igdb_metadata"]

# Every column the `roms_metadata` view projects, old and new. The view is
# replaced wholesale, so the pre-existing projections have to be restated.
_VIEW_COLUMNS = [
    ("generated_genres", "genres"),
    ("generated_franchises", "franchises"),
    ("generated_collections", "collections"),
    ("generated_companies", "companies"),
    ("generated_game_modes", "game_modes"),
    ("generated_age_ratings", "age_ratings"),
    ("generated_first_release_date", "first_release_date"),
    ("generated_average_rating", "average_rating"),
    ("generated_player_count", "player_count"),
] + _TAG_COLUMNS


def _maria_array_expr(column: str) -> str:
    key = column[len("generated_") :]
    branches = [
        f"CASE WHEN JSON_LENGTH(JSON_EXTRACT({src}, '$.{key}')) > 0 "
        f"THEN JSON_EXTRACT({src}, '$.{key}') ELSE NULL END"
        for src in _SOURCES
    ]
    branches.append("JSON_ARRAY()")
    return "COALESCE(" + ", ".join(branches) + ")"


def _postgres_array_expr(column: str) -> str:
    key = column[len("generated_") :]
    branches = [f"NULLIF({src} -> '{key}', '[]'::jsonb)" for src in _SOURCES]
    branches.append("'[]'::jsonb")
    return "COALESCE(" + ", ".join(branches) + ")"


def _view_sql(is_pg: bool) -> str:
    projections = ",\n    ".join(
        # The view exposed player_count as text and PostgreSQL cannot change a
        # column's type through CREATE OR REPLACE VIEW, so the cast has to stay.
        (
            f"{name}::text AS {alias}"
            if is_pg and alias == "player_count"
            else f"{name} AS {alias}"
        )
        for name, alias in _VIEW_COLUMNS
    )
    return (
        "CREATE OR REPLACE VIEW roms_metadata AS\n"  # nosec B608
        "SELECT\n"
        "    id AS rom_id,\n"
        "    NOW() AS created_at,\n"
        "    NOW() AS updated_at,\n"
        f"    {projections}\n"
        "FROM roms"
    )


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = is_postgresql(bind)
    json_type = "JSONB" if is_pg else "JSON"

    for generated, _ in _TAG_COLUMNS:
        expr = (
            _postgres_array_expr(generated) if is_pg else _maria_array_expr(generated)
        )
        op.execute(
            f"ALTER TABLE roms ADD COLUMN {generated} {json_type} "  # nosec B608
            f"GENERATED ALWAYS AS ({expr}) STORED"
        )

    op.execute(_view_sql(is_pg))

    for _, facet in _TAG_COLUMNS:
        op.add_column("roms_facets", sa.Column(facet, CustomJSON(), nullable=True))

    # The triggers copy a fixed column list, so they are rebuilt rather than
    # amended. Backfill first so existing rows are correct either way.
    _backfill_facets()
    _rebuild_triggers(
        is_pg, _MIRRORED_COLUMNS + [(facet, gen) for gen, facet in _TAG_COLUMNS]
    )


def _backfill_facets() -> None:
    assignments = ", ".join(
        f"f.{facet} = r.{generated}" for generated, facet in _TAG_COLUMNS
    )
    bind = op.get_bind()
    if is_postgresql(bind):
        set_clause = ", ".join(
            f"{facet} = r.{generated}" for generated, facet in _TAG_COLUMNS
        )
        op.execute(
            f"UPDATE roms_facets f SET {set_clause} FROM roms r "  # nosec B608
            "WHERE r.id = f.rom_id"
        )
    else:
        op.execute(
            f"UPDATE roms_facets f JOIN roms r ON r.id = f.rom_id SET {assignments}"  # nosec B608
        )


# Mirrored into roms_facets by the triggers, matching migration 0100's list
# with the three new columns appended.
_MIRRORED_COLUMNS = [
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
    ("igdb_id", "igdb_id"),
    ("ss_id", "ss_id"),
    ("moby_id", "moby_id"),
    ("launchbox_id", "launchbox_id"),
    ("ra_id", "ra_id"),
    ("hasheous_id", "hasheous_id"),
    ("tgdb_id", "tgdb_id"),
    ("flashpoint_id", "flashpoint_id"),
    ("hltb_id", "hltb_id"),
    ("gamelist_id", "gamelist_id"),
    ("libretro_id", "libretro_id"),
]

_MYSQL_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


def _rebuild_triggers(is_pg: bool, mirrored: list[tuple[str, str]]) -> None:
    """Recreate the roms_facets sync triggers over the given column list.

    The triggers copy a fixed set of columns, so adding one means replacing
    them wholesale rather than amending in place.
    """
    targets = ", ".join(target for target, _ in mirrored)
    values = ", ".join(f"NEW.{source}" for _, source in mirrored)

    if is_pg:
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


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = is_postgresql(bind)

    # Drop the view's dependency on the new columns before dropping them.
    remaining = [entry for entry in _VIEW_COLUMNS if entry not in _TAG_COLUMNS]
    projections = ",\n    ".join(
        (
            f"{name}::text AS {alias}"
            if is_pg and alias == "player_count"
            else f"{name} AS {alias}"
        )
        for name, alias in remaining
    )
    op.execute("DROP VIEW IF EXISTS roms_metadata")
    op.execute(
        "CREATE VIEW roms_metadata AS\n"  # nosec B608
        "SELECT\n    id AS rom_id,\n    NOW() AS created_at,\n"
        f"    NOW() AS updated_at,\n    {projections}\nFROM roms"
    )

    for _, facet in _TAG_COLUMNS:
        op.drop_column("roms_facets", facet)
    for generated, _ in _TAG_COLUMNS:
        op.execute(f"ALTER TABLE roms DROP COLUMN {generated}")

    _rebuild_triggers(is_pg, _MIRRORED_COLUMNS)
