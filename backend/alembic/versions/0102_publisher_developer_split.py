"""Split company metadata into distinct publishers and developers

``companies`` amalgamates the publisher and the developer of a game into one
list at ingestion, so the distinction (which providers like ScreenScraper,
RetroAchievements, LaunchBox, Flashpoint, gamelist and IGDB do expose) was lost
and could not be round-tripped to external tools. See issue #3518.

The handlers now also emit ``publishers`` and ``developers`` alongside the
existing (unchanged) ``companies`` list. This migration threads the two new
fields through the read pipeline that 0098/0100/0101 built:

- Two STORED generated columns on ``roms`` (``generated_publishers`` /
  ``generated_developers``), coalescing ``$.publishers`` / ``$.developers``
  across the same provider blobs ``generated_companies`` already reads.
- The ``roms_metadata`` view projects them (appended, so nothing else shifts).
- ``roms_facets`` mirrors them; its sync triggers are rebuilt to carry them.
- ``virtual_collection_roms`` gains ``publisher`` / ``developer`` membership
  types (backfilled once here, then kept current by the rebuilt triggers). The
  ``virtual_collections`` view groups by ``(type, name)`` generically, so it
  surfaces the new types with no change of its own.

Existing rows only carry ``companies`` until their ROMs are re-scanned: the raw
provider blobs predate the new keys, so the generated columns read empty for
them. ``companies`` stays fully populated meanwhile.

Revision ID: 0102_publisher_developer_split
Revises: 0101_virtual_collection_roms
Create Date: 2026-07-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0102_publisher_developer_split"
down_revision = "0101_virtual_collection_roms"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Generated columns on roms (mirrors 0098's company source precedence/exprs)
# ---------------------------------------------------------------------------

# (generated column, JSON key) added by this migration.
_NEW_GENERATED = [
    ("generated_publishers", "publishers"),
    ("generated_developers", "developers"),
]

# Same provider blobs (and precedence) that back generated_companies in 0098.
_COMPANY_SOURCES = [
    "manual_metadata",
    "igdb_metadata",
    "ss_metadata",
    "ra_metadata",
    "launchbox_metadata",
    "flashpoint_metadata",
    "gamelist_metadata",
]


def _maria_array_expr(key: str) -> str:
    branches = [
        f"CASE WHEN JSON_LENGTH(JSON_EXTRACT({src}, '$.{key}')) > 0 "
        f"THEN JSON_EXTRACT({src}, '$.{key}') ELSE NULL END"
        for src in _COMPANY_SOURCES
    ]
    branches.append("JSON_ARRAY()")
    return "COALESCE(\n    " + ",\n    ".join(branches) + "\n)"


def _postgres_array_expr(key: str) -> str:
    branches = [f"NULLIF({src} -> '{key}', '[]'::jsonb)" for src in _COMPANY_SOURCES]
    branches.append("'[]'::jsonb")
    return "COALESCE(\n    " + ",\n    ".join(branches) + "\n)"


def _add_generated_columns(pg: bool) -> None:
    json_type = "JSONB" if pg else "JSON"
    expr = _postgres_array_expr if pg else _maria_array_expr
    adds = ",\n".join(
        f"ADD COLUMN {name} {json_type} GENERATED ALWAYS AS ({expr(key)}) STORED"
        for name, key in _NEW_GENERATED
    )
    op.execute(f"ALTER TABLE roms\n{adds}")  # nosec B608


def _drop_generated_columns() -> None:
    drops = ",\n".join(f"DROP COLUMN {name}" for name, _ in _NEW_GENERATED)
    op.execute(f"ALTER TABLE roms\n{drops}")  # nosec B608


# ---------------------------------------------------------------------------
# roms_metadata view (verbatim 0098 projection; publishers/developers appended)
# ---------------------------------------------------------------------------

# 0098 column order, kept intact so the appended columns don't shift the rest.
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
]
_NEW_VIEW_COLUMNS = [
    ("generated_publishers", "publishers"),
    ("generated_developers", "developers"),
]


def _roms_metadata_view_sql(pg: bool, include_new: bool) -> str:
    columns = _BASE_VIEW_COLUMNS + (_NEW_VIEW_COLUMNS if include_new else [])
    projections = []
    for name, alias in columns:
        # player_count is text in the view (0098 note), cast to match on PG.
        if pg and alias == "player_count":
            projections.append(f"{name}::text AS {alias}")
        else:
            projections.append(f"{name} AS {alias}")
    projection = ",\n    ".join(projections)
    return (
        "CREATE VIEW roms_metadata AS\n"  # nosec B608
        "SELECT\n"
        "    id AS rom_id,\n"
        "    NOW() AS created_at,\n"
        "    NOW() AS updated_at,\n"
        f"    {projection}\n"
        "FROM roms"
    )


def _rebuild_roms_metadata_view(pg: bool, include_new: bool) -> None:
    # DROP + CREATE (not REPLACE): PG's CREATE OR REPLACE VIEW cannot drop the
    # trailing columns on downgrade. Nothing depends on this view.
    op.execute("DROP VIEW IF EXISTS roms_metadata")
    op.execute(_roms_metadata_view_sql(pg, include_new))


# ---------------------------------------------------------------------------
# roms_facets mirror (mirrors 0100; publishers/developers added)
# ---------------------------------------------------------------------------

_FACETS_BASE = [
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
]
_FACETS_NEW = [
    ("publishers", "generated_publishers"),
    ("developers", "generated_developers"),
]

_MYSQL_FACETS_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


def _facets_columns(include_new: bool) -> list[tuple[str, str]]:
    # publishers/developers slot right after companies to keep the table tidy.
    if not include_new:
        return _FACETS_BASE
    out: list[tuple[str, str]] = []
    for target, source in _FACETS_BASE:
        out.append((target, source))
        if target == "companies":
            out.extend(_FACETS_NEW)
    return out


def _rebuild_facets_triggers(pg: bool, include_new: bool) -> None:
    columns = _facets_columns(include_new)
    targets = ", ".join(target for target, _ in columns)
    if pg:
        op.execute("DROP TRIGGER IF EXISTS roms_facets_sync ON roms")
        op.execute("DROP FUNCTION IF EXISTS romm_sync_rom_facets()")
        values = ", ".join(f"NEW.{source}" for _, source in columns)
        assignments = ", ".join(
            f"{target} = EXCLUDED.{target}" for target, _ in columns
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
        op.execute(
            "CREATE TRIGGER roms_facets_sync AFTER INSERT OR UPDATE ON roms\n"
            "    FOR EACH ROW EXECUTE FUNCTION romm_sync_rom_facets()"
        )
    else:
        for name in _MYSQL_FACETS_TRIGGERS:
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
        values = ", ".join(f"NEW.{source}" for _, source in columns)
        updates = ",\n".join(f"{target} = VALUES({target})" for target, _ in columns)
        body = (
            f"INSERT INTO roms_facets (rom_id, {targets})\n"  # nosec B608
            f"VALUES (NEW.id, {values})\n"
            f"ON DUPLICATE KEY UPDATE\n{updates},\nupdated_at = CURRENT_TIMESTAMP"
        )
        for name, timing in _MYSQL_FACETS_TRIGGERS.items():
            op.execute(f"CREATE TRIGGER {name} {timing} ON roms\nFOR EACH ROW\n{body}")


def _backfill_facets_new_columns(pg: bool) -> None:
    if pg:
        op.execute(
            "UPDATE roms_facets f SET\n"
            "    publishers = r.generated_publishers,\n"
            "    developers = r.generated_developers\n"
            "FROM roms r WHERE r.id = f.rom_id"
        )
    else:
        op.execute(
            "UPDATE roms_facets f JOIN roms r ON r.id = f.rom_id SET\n"
            "    f.publishers = r.generated_publishers,\n"
            "    f.developers = r.generated_developers"
        )


# ---------------------------------------------------------------------------
# virtual_collection_roms membership (mirrors 0101; publisher/developer added)
# ---------------------------------------------------------------------------

TABLE = "virtual_collection_roms"
NAME_MAX_LENGTH = 400
_VC_COLUMNS = "rom_id, type, name, path_cover_s, path_cover_l, created_at, updated_at"

_VC_BASE_TYPES = [
    ("genre", "generated_genres"),
    ("franchise", "generated_franchises"),
    ("collection", "generated_collections"),
    ("mode", "generated_game_modes"),
    ("company", "generated_companies"),
]
_VC_NEW_TYPES = [
    ("publisher", "generated_publishers"),
    ("developer", "generated_developers"),
]
_VC_ALL_TYPES = _VC_BASE_TYPES + _VC_NEW_TYPES


def _mysql_vc_rows(row: str, from_roms: bool, types: list[tuple[str, str]]) -> str:
    branches = []
    for type_, column in types:
        json_table = (
            f"JSON_TABLE({row}.{column}, '$[*]' COLUMNS (value TEXT PATH '$')) j"
        )
        source = f"roms r CROSS JOIN {json_table}" if from_roms else json_table
        branches.append(
            f"SELECT DISTINCT {row}.id, '{type_}', LEFT(j.value, {NAME_MAX_LENGTH}), "  # nosec B608
            f"{row}.path_cover_s, {row}.path_cover_l, NOW(), NOW()\n"
            f"FROM {source}\n"
            f"WHERE j.value IS NOT NULL AND j.value != ''"
        )
    return "\nUNION ALL\n".join(branches)


def _postgres_vc_rows(row: str, from_roms: bool, types: list[tuple[str, str]]) -> str:
    branches = []
    for type_, column in types:
        array = (
            f"CASE WHEN jsonb_typeof({row}.{column}) = 'array' "
            f"THEN {row}.{column} ELSE '[]'::jsonb END"
        )
        elements = f"jsonb_array_elements_text({array}) AS j(value)"
        source = f"roms r CROSS JOIN LATERAL {elements}" if from_roms else elements
        branches.append(
            f"SELECT DISTINCT {row}.id, '{type_}', LEFT(j.value, {NAME_MAX_LENGTH}), "  # nosec B608
            f"{row}.path_cover_s, {row}.path_cover_l, NOW(), NOW()\n"
            f"FROM {source}\n"
            f"WHERE j.value IS NOT NULL AND j.value != ''"
        )
    return "\nUNION ALL\n".join(branches)


def _vc_tracked_columns(types: list[tuple[str, str]]) -> list[str]:
    return [column for _, column in types] + ["path_cover_s", "path_cover_l"]


def _rebuild_vc_triggers(pg: bool, types: list[tuple[str, str]]) -> None:
    tracked = _vc_tracked_columns(types)
    if pg:
        op.execute("DROP TRIGGER IF EXISTS virtual_collection_roms_aiu ON roms")
        op.execute("DROP FUNCTION IF EXISTS romm_sync_virtual_collection_roms()")
        unchanged = " AND ".join(
            f"NEW.{c} IS NOT DISTINCT FROM OLD.{c}" for c in tracked
        )
        op.execute(f"""
CREATE OR REPLACE FUNCTION romm_sync_virtual_collection_roms() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF {unchanged} THEN
            RETURN NULL;
        END IF;
        DELETE FROM {TABLE} WHERE rom_id = NEW.id;
    END IF;

    INSERT INTO {TABLE} ({_VC_COLUMNS})
    {_postgres_vc_rows("NEW", False, types)}
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END $$
""")  # nosec B608
        op.execute(
            "CREATE TRIGGER virtual_collection_roms_aiu AFTER INSERT OR UPDATE ON roms\n"
            "FOR EACH ROW EXECUTE FUNCTION romm_sync_virtual_collection_roms()"
        )
    else:
        op.execute("DROP TRIGGER IF EXISTS virtual_collection_roms_ai")
        op.execute("DROP TRIGGER IF EXISTS virtual_collection_roms_au")
        insert = (
            f"INSERT IGNORE INTO {TABLE} ({_VC_COLUMNS})\n"  # nosec B608
            f"{_mysql_vc_rows('NEW', False, types)}"
        )
        unchanged = " AND ".join(f"NEW.{c} <=> OLD.{c}" for c in tracked)
        op.execute(
            f"CREATE TRIGGER virtual_collection_roms_ai AFTER INSERT ON roms\n"  # nosec B608
            f"FOR EACH ROW\n{insert}"
        )
        op.execute(
            f"CREATE TRIGGER virtual_collection_roms_au AFTER UPDATE ON roms\n"  # nosec B608
            f"FOR EACH ROW\nBEGIN\n"
            f"IF NOT ({unchanged}) THEN\n"
            f"DELETE FROM {TABLE} WHERE rom_id = NEW.id;\n"
            f"{insert};\n"
            f"END IF;\n"
            f"END"
        )


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def upgrade() -> None:
    pg = is_postgresql(op.get_bind())

    _add_generated_columns(pg)
    _rebuild_roms_metadata_view(pg, include_new=True)

    op.add_column("roms_facets", sa.Column("publishers", CustomJSON(), nullable=True))
    op.add_column("roms_facets", sa.Column("developers", CustomJSON(), nullable=True))
    _backfill_facets_new_columns(pg)
    _rebuild_facets_triggers(pg, include_new=True)

    # Backfill only the new types so existing membership rows aren't duplicated.
    rows = (
        _postgres_vc_rows("r", True, _VC_NEW_TYPES)
        if pg
        else _mysql_vc_rows("r", True, _VC_NEW_TYPES)
    )
    conflict = "ON CONFLICT DO NOTHING" if pg else ""
    insert = "INSERT INTO" if pg else "INSERT IGNORE INTO"
    op.execute(f"{insert} {TABLE} ({_VC_COLUMNS})\n{rows}\n{conflict}")  # nosec B608
    _rebuild_vc_triggers(pg, _VC_ALL_TYPES)


def downgrade() -> None:
    pg = is_postgresql(op.get_bind())

    op.execute(
        f"DELETE FROM {TABLE} WHERE type IN ('publisher', 'developer')"  # nosec B608
    )
    _rebuild_vc_triggers(pg, _VC_BASE_TYPES)

    _rebuild_facets_triggers(pg, include_new=False)
    op.drop_column("roms_facets", "developers")
    op.drop_column("roms_facets", "publishers")

    _rebuild_roms_metadata_view(pg, include_new=False)
    _drop_generated_columns()
