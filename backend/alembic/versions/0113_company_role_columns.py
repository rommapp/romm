"""Split companies into developers and publishers for recommendation scoring

`companies` flattens every IGDB involvement role into one list, so a studio
that made a game is indistinguishable from a label that shipped it or a
regional distributor that boxed it. The roles carry very different weight for
similarity: a developer's games genuinely resemble each other, while a
publisher spans everything it ever shipped.

The distinction is not academic. On a 15k-game library the most common
"company" is Tec Toy, Sega's Brazilian distributor, on 774 games, ahead of
Nintendo on 756 -- dense enough that IDF alone does not suppress them, so
matches get explained as "same distributor".

`companies` stays exactly as it is for display; these are additive, and the
scorer prefers them where present and falls back to the merged list where a
game was matched by a provider that reports no roles.

Revision ID: 0113_company_role_columns
Revises: 0112_rating_count_column
Create Date: 2026-08-08 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0113_company_role_columns"
down_revision = "0112_rating_count_column"
branch_labels = None
depends_on = None

# (generated column, roms_facets column). Only IGDB reports roles, plus
# manual_metadata so a user override still wins.
_ROLE_COLUMNS = [
    ("generated_developers", "developers"),
    ("generated_publishers", "publishers"),
]
_SOURCES = ["manual_metadata", "igdb_metadata"]

# Restated in full: CREATE OR REPLACE VIEW rewrites every projection.
_VIEW_COLUMNS = [
    ("generated_genres", "genres"),
    ("generated_franchises", "franchises"),
    ("generated_collections", "collections"),
    ("generated_companies", "companies"),
    ("generated_game_modes", "game_modes"),
    ("generated_age_ratings", "age_ratings"),
    ("generated_keywords", "keywords"),
    ("generated_themes", "themes"),
    ("generated_player_perspectives", "player_perspectives"),
    ("generated_first_release_date", "first_release_date"),
    ("generated_average_rating", "average_rating"),
    ("generated_player_count", "player_count"),
    ("generated_rating_count", "rating_count"),
]

# Mirrored into roms_facets by the triggers. Matches migration 0109's list
# with the two role columns appended.
_MIRRORED_COLUMNS = [
    ("platform_id", "platform_id"),
    ("genres", "generated_genres"),
    ("franchises", "generated_franchises"),
    ("collections", "generated_collections"),
    ("companies", "generated_companies"),
    ("game_modes", "generated_game_modes"),
    ("age_ratings", "generated_age_ratings"),
    ("keywords", "generated_keywords"),
    ("themes", "generated_themes"),
    ("player_perspectives", "generated_player_perspectives"),
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


def _maria_expr(column: str) -> str:
    key = column[len("generated_") :]
    branches = [
        f"CASE WHEN JSON_LENGTH(JSON_EXTRACT({src}, '$.{key}')) > 0 "
        f"THEN JSON_EXTRACT({src}, '$.{key}') ELSE NULL END"
        for src in _SOURCES
    ]
    branches.append("JSON_ARRAY()")
    return "COALESCE(" + ", ".join(branches) + ")"


def _postgres_expr(column: str) -> str:
    key = column[len("generated_") :]
    branches = [f"NULLIF({src} -> '{key}', '[]'::jsonb)" for src in _SOURCES]
    branches.append("'[]'::jsonb")
    return "COALESCE(" + ", ".join(branches) + ")"


def _view_sql(is_pg: bool, columns: list[tuple[str, str]]) -> str:
    projections = ",\n    ".join(
        # The view exposed player_count as text and PostgreSQL cannot change a
        # column's type through CREATE OR REPLACE VIEW.
        (
            f"{name}::text AS {alias}"
            if is_pg and alias == "player_count"
            else f"{name} AS {alias}"
        )
        for name, alias in columns
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


def _rebuild_triggers(is_pg: bool, mirrored: list[tuple[str, str]]) -> None:
    """Recreate the roms_facets sync triggers over the given column list."""
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


def upgrade() -> None:
    is_pg = is_postgresql(op.get_bind())
    json_type = "JSONB" if is_pg else "JSON"

    for generated, _ in _ROLE_COLUMNS:
        expr = _postgres_expr(generated) if is_pg else _maria_expr(generated)
        op.execute(
            f"ALTER TABLE roms ADD COLUMN {generated} {json_type} "  # nosec B608
            f"GENERATED ALWAYS AS ({expr}) STORED"
        )

    op.execute(_view_sql(is_pg, _VIEW_COLUMNS + [(g, f) for g, f in _ROLE_COLUMNS]))

    for _, facet in _ROLE_COLUMNS:
        op.add_column("roms_facets", sa.Column(facet, CustomJSON(), nullable=True))

    _backfill_facets(is_pg)
    _rebuild_triggers(
        is_pg, _MIRRORED_COLUMNS + [(facet, gen) for gen, facet in _ROLE_COLUMNS]
    )


def _backfill_facets(is_pg: bool) -> None:
    if is_pg:
        assignments = ", ".join(
            f"{facet} = r.{generated}" for generated, facet in _ROLE_COLUMNS
        )
        op.execute(
            f"UPDATE roms_facets f SET {assignments} FROM roms r "  # nosec B608
            "WHERE r.id = f.rom_id"
        )
        return

    assignments = ", ".join(
        f"f.{facet} = r.{generated}" for generated, facet in _ROLE_COLUMNS
    )
    op.execute(
        f"UPDATE roms_facets f JOIN roms r ON r.id = f.rom_id SET {assignments}"  # nosec B608
    )


def downgrade() -> None:
    is_pg = is_postgresql(op.get_bind())

    op.execute("DROP VIEW IF EXISTS roms_metadata")
    op.execute(_view_sql(is_pg, _VIEW_COLUMNS).replace("CREATE OR REPLACE", "CREATE"))

    for _, facet in _ROLE_COLUMNS:
        op.drop_column("roms_facets", facet)
    for generated, _ in _ROLE_COLUMNS:
        op.execute(f"ALTER TABLE roms DROP COLUMN {generated}")

    _rebuild_triggers(is_pg, _MIRRORED_COLUMNS)
