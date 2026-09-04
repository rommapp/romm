"""Feed Steam's metadata into the generated facet columns

0115 stored ``steam_metadata`` but left it out of the COALESCE chains behind
the ``generated_*`` columns, because changing a STORED generated column
rebuilds the ``roms`` table. 0120 and 0121 already pay that cost, so Steam's
genres, companies, developers, publishers, game modes, release date and
Metacritic score are wired in here rather than in a rebuild of their own.
Until now they were persisted but surfaced nowhere: the details page, the
gallery filters and the recommendations index all read the generated columns.

Steam takes the lowest precedence in every chain, after the providers 0098 and
0112 list. Franchises, collections, age ratings and player count are
untouched, since Steam supplies none of them.

PostgreSQL cannot change a generated column's expression in place, so on both
engines the columns are dropped and re-added in one ALTER TABLE, with the view
and indexes that depend on them recreated around it. Only rows carrying Steam
metadata can change value, so the facet and virtual-collection refreshes are
limited to those.

Revision ID: 0122_steam_facet_sources
Revises: 0121_rating_count_column
Create Date: 2026-09-03 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0122_steam_facet_sources"
down_revision = "0121_rating_count_column"
branch_labels = None
depends_on = None

_STEAM = "steam_metadata"

# Provider precedence per array column, as 0098 and 0112 left it. Steam is
# appended to each chain when the columns are rebuilt with it.
_ARRAY_SOURCES: dict[str, list[str]] = {
    "generated_genres": [
        "manual_metadata",
        "igdb_metadata",
        "moby_metadata",
        "ss_metadata",
        "launchbox_metadata",
        "ra_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    ],
    "generated_companies": [
        "manual_metadata",
        "igdb_metadata",
        "ss_metadata",
        "ra_metadata",
        "launchbox_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    ],
    "generated_game_modes": [
        "manual_metadata",
        "igdb_metadata",
        "ss_metadata",
        "flashpoint_metadata",
    ],
    "generated_publishers": [
        "manual_metadata",
        "igdb_metadata",
        "ss_metadata",
        "ra_metadata",
        "launchbox_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    ],
    "generated_developers": [
        "manual_metadata",
        "igdb_metadata",
        "ss_metadata",
        "ra_metadata",
        "launchbox_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    ],
}

# (source, multiplier to milliseconds) for the integer release-date branches.
# The gamelist string branch follows them; Steam, in epoch seconds, comes last.
_DATE_SOURCES = [
    ("manual_metadata", 1),
    ("igdb_metadata", 1000),
    ("ss_metadata", 1000),
    ("ra_metadata", 1000),
    ("launchbox_metadata", 1000),
    ("flashpoint_metadata", 1000),
]
_STEAM_DATE = (_STEAM, 1000)

# (source, key, multiplier to a 0-100 scale) averaged into the rating.
_RATING_SOURCES = [
    ("igdb_metadata", "total_rating", 1),
    ("moby_metadata", "moby_score", 10),
    ("ss_metadata", "ss_score", 10),
    ("launchbox_metadata", "community_rating", 20),
    ("gamelist_metadata", "rating", 100),
]
# Steam carries the Metacritic score, already on a 0-100 scale.
_STEAM_RATING = (_STEAM, "total_rating", 1)

# Dropped with their columns on PostgreSQL, so recreated after the rebuild.
_INDEXED_COLUMNS = ["generated_first_release_date", "generated_average_rating"]

# roms_facets mirrors of the rebuilt columns, refreshed for the Steam rows.
_FACET_COLUMNS = [
    ("genres", "generated_genres"),
    ("companies", "generated_companies"),
    ("game_modes", "generated_game_modes"),
    ("publishers", "generated_publishers"),
    ("developers", "generated_developers"),
]

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

# Restated in full because the view is recreated, in the order 0121 left it.
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
    ("generated_publishers", "publishers"),
    ("generated_developers", "developers"),
    ("generated_keywords", "keywords"),
    ("generated_themes", "themes"),
    ("generated_player_perspectives", "player_perspectives"),
    ("generated_rating_count", "rating_count"),
]


# ---------------------------------------------------------------------------
# MariaDB / MySQL expressions (verbatim from 0098 and 0112, Steam appended)
# ---------------------------------------------------------------------------


def _maria_array_expr(key: str, sources: list[str]) -> str:
    branches = [
        f"CASE WHEN JSON_LENGTH(JSON_EXTRACT({src}, '$.{key}')) > 0 "
        f"THEN JSON_EXTRACT({src}, '$.{key}') ELSE NULL END"
        for src in sources
    ]
    branches.append("JSON_ARRAY()")
    return "COALESCE(\n    " + ",\n    ".join(branches) + "\n)"


def _maria_int_date_branch(src: str, mult: int) -> str:
    val = f"JSON_UNQUOTE(JSON_EXTRACT({src}, '$.first_release_date'))"
    cast = f"CAST({val} AS SIGNED)"
    if mult != 1:
        cast = f"{cast} * {mult}"
    return (
        f"WHEN JSON_CONTAINS_PATH({src}, 'one', '$.first_release_date') "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} REGEXP '^[0-9]+$' THEN {cast}"
    )


def _maria_gamelist_date_branch() -> str:
    gl = "JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.first_release_date'))"
    # STR_TO_DATE is barred from a generated column, so the fixed-width
    # "YYYYMMDDThhmmss" string is reshaped into a datetime literal and
    # range-checked by hand; invalid dates fall through to NULL. See 0098.
    parts = [
        f"SUBSTRING({gl}, 1, 4)",
        "'-'",
        f"SUBSTRING({gl}, 5, 2)",
        "'-'",
        f"SUBSTRING({gl}, 7, 2)",
        "' '",
        f"SUBSTRING({gl}, 10, 2)",
        "':'",
        f"SUBSTRING({gl}, 12, 2)",
        "':'",
        f"SUBSTRING({gl}, 14, 2)",
    ]
    gl_datetime = "CONCAT(" + ", ".join(parts) + ")"
    year, month, day = (f"CAST(SUBSTRING({gl}, {p}, {n}) AS SIGNED)" for p, n in ((1, 4), (5, 2), (7, 2)))  # fmt: skip
    hour, minute, second = (f"CAST(SUBSTRING({gl}, {p}, 2) AS SIGNED)" for p in (10, 12, 14))  # fmt: skip
    leap = f"(({year} % 4 = 0 AND {year} % 100 != 0) OR {year} % 400 = 0)"
    days_in_month = (
        f"CASE {month} WHEN 2 THEN IF({leap}, 29, 28) "
        f"WHEN 4 THEN 30 WHEN 6 THEN 30 WHEN 9 THEN 30 WHEN 11 THEN 30 "
        f"ELSE 31 END"
    )
    calendar_valid = (
        f"{year} >= 1 AND {month} BETWEEN 1 AND 12 "
        f"AND {day} BETWEEN 1 AND ({days_in_month}) "
        f"AND {hour} <= 23 AND {minute} <= 59 AND {second} <= 59"
    )
    return (
        f"WHEN JSON_CONTAINS_PATH(gamelist_metadata, 'one', '$.first_release_date') "
        f"AND {gl} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {gl} REGEXP '^[0-9]{{8}}T[0-9]{{6}}$' "
        f"AND {calendar_valid} "
        f"THEN TIMESTAMPDIFF(SECOND, '1970-01-01 00:00:00', {gl_datetime}) * 1000"
    )


def _maria_first_release_date(with_steam: bool) -> str:
    branches = [_maria_int_date_branch(src, mult) for src, mult in _DATE_SOURCES]
    branches.append(_maria_gamelist_date_branch())
    if with_steam:
        branches.append(_maria_int_date_branch(*_STEAM_DATE))
    return "CASE\n    " + "\n    ".join(branches) + "\n    ELSE NULL END"


def _maria_rating(source: str, key: str, multiplier: int) -> str:
    val = f"JSON_UNQUOTE(JSON_EXTRACT({source}, '$.{key}'))"
    cast = f"CAST({val} AS DECIMAL(10,2))"
    if multiplier != 1:
        cast = f"{cast} * {multiplier}"
    return (
        f"CASE WHEN JSON_CONTAINS_PATH({source}, 'one', '$.{key}') "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} REGEXP '^[0-9]+(\\\\.[0-9]+)?$' THEN {cast} ELSE NULL END"
    )


# ---------------------------------------------------------------------------
# PostgreSQL expressions (verbatim from 0098 and 0112, Steam appended)
# ---------------------------------------------------------------------------


def _postgres_array_expr(key: str, sources: list[str]) -> str:
    branches = [f"NULLIF({src} -> '{key}', '[]'::jsonb)" for src in sources]
    branches.append("'[]'::jsonb")
    return "COALESCE(\n    " + ",\n    ".join(branches) + "\n)"


def _postgres_int_date_branch(src: str, mult: int) -> str:
    val = f"{src} ->> 'first_release_date'"
    cast = f"({val})::bigint"
    if mult != 1:
        cast = f"{cast} * {mult}"
    return (
        f"WHEN {src} IS NOT NULL AND {src} ? 'first_release_date' "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} ~ '^[0-9]+$' THEN {cast}"
    )


def _postgres_first_release_date(with_steam: bool) -> str:
    branches = [_postgres_int_date_branch(src, mult) for src, mult in _DATE_SOURCES]
    gl = "gamelist_metadata ->> 'first_release_date'"
    # romm_gamelist_epoch_ms is the IMMUTABLE parser 0098 installed.
    branches.append(
        f"WHEN gamelist_metadata IS NOT NULL AND gamelist_metadata ? 'first_release_date' "
        f"AND {gl} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {gl} ~ '^[0-9]{{8}}T[0-9]{{6}}$' "
        f"THEN romm_gamelist_epoch_ms({gl})"
    )
    if with_steam:
        branches.append(_postgres_int_date_branch(*_STEAM_DATE))
    return "CASE\n    " + "\n    ".join(branches) + "\n    ELSE NULL END"


def _postgres_rating(source: str, key: str, multiplier: int) -> str:
    val = f"{source} ->> '{key}'"
    cast = f"({val})::float"
    if multiplier != 1:
        cast = f"{cast} * {multiplier}"
    return (
        f"CASE WHEN {source} IS NOT NULL AND {source} ? '{key}' "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} ~ '^[0-9]+(\\.[0-9]+)?$' THEN {cast} ELSE NULL END"
    )


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


def _average_expr(ratings: list[str]) -> str:
    any_present = " OR ".join(f"({r}) IS NOT NULL" for r in ratings)
    numerator = " + ".join(f"COALESCE({r}, 0)" for r in ratings)
    denominator = " + ".join(
        f"CASE WHEN ({r}) IS NOT NULL THEN 1 ELSE 0 END" for r in ratings
    )
    return (
        f"CASE WHEN ({any_present}) "
        f"THEN ({numerator}) / ({denominator}) ELSE NULL END"
    )


def _generated_columns(pg: bool, with_steam: bool) -> list[tuple[str, str, str]]:
    """(name, type, expression) for every column this migration rebuilds."""
    array_expr = _postgres_array_expr if pg else _maria_array_expr
    columns: list[tuple[str, str, str]] = []
    for name, sources in _ARRAY_SOURCES.items():
        key = name[len("generated_") :]
        chain = sources + [_STEAM] if with_steam else sources
        columns.append((name, "JSONB" if pg else "JSON", array_expr(key, chain)))

    date_expr = _postgres_first_release_date if pg else _maria_first_release_date
    columns.append(("generated_first_release_date", "BIGINT", date_expr(with_steam)))

    rating_expr = _postgres_rating if pg else _maria_rating
    rating_sources = _RATING_SOURCES + ([_STEAM_RATING] if with_steam else [])
    ratings = [rating_expr(src, key, mult) for src, key, mult in rating_sources]
    columns.append(
        (
            "generated_average_rating",
            "DOUBLE PRECISION" if pg else "DOUBLE",
            _average_expr(ratings),
        )
    )
    return columns


def _view_sql(pg: bool) -> str:
    projections = ",\n    ".join(
        # 0098 exposed player_count as text; kept so later CREATE OR REPLACE
        # VIEW statements on PostgreSQL still match the column's type.
        (
            f"{name}::text AS {alias}"
            if pg and alias == "player_count"
            else f"{name} AS {alias}"
        )
        for name, alias in _VIEW_COLUMNS
    )
    return (
        "CREATE VIEW roms_metadata AS\n"  # nosec B608
        "SELECT\n"
        "    id AS rom_id,\n"
        "    NOW() AS created_at,\n"
        "    NOW() AS updated_at,\n"
        f"    {projections}\n"
        "FROM roms"
    )


def _rebuild_generated_columns(pg: bool, with_steam: bool) -> None:
    columns = _generated_columns(pg, with_steam)

    # The view projects the columns being dropped, so it goes first.
    op.execute("DROP VIEW IF EXISTS roms_metadata")

    actions = [f"DROP COLUMN {name}" for name, _, _ in columns] + [
        f"ADD COLUMN {name} {type_} GENERATED ALWAYS AS ({expr}) STORED"
        for name, type_, expr in columns
    ]
    op.execute("ALTER TABLE roms\n" + ",\n".join(actions))  # nosec B608

    # MariaDB carries a single-column index across the drop and re-add;
    # PostgreSQL drops it with the column.
    existing = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("roms")
    }
    for column in _INDEXED_COLUMNS:
        if f"idx_roms_{column}" not in existing:
            op.create_index(f"idx_roms_{column}", "roms", [column])

    op.execute(_view_sql(pg))


def _has_steam_rows() -> bool:
    probe = f"SELECT 1 FROM roms WHERE {_STEAM} IS NOT NULL LIMIT 1"  # nosec B608
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
            f"WHERE r.{_STEAM} IS NOT NULL AND j.value IS NOT NULL AND j.value != ''"
        )
    return "\nUNION ALL\n".join(branches)


def _refresh_steam_rows(pg: bool) -> None:
    """Re-mirror the rows whose generated values can have changed.

    The roms_facets and virtual_collection_roms triggers only fire on a write
    to roms, and the rebuild above is not one.
    """
    if not _has_steam_rows():
        return

    if pg:
        assignments = ", ".join(
            f"{facet} = r.{generated}" for facet, generated in _FACET_COLUMNS
        )
        op.execute(
            f"UPDATE roms_facets f SET {assignments} "  # nosec B608
            f"FROM roms r WHERE r.id = f.rom_id AND r.{_STEAM} IS NOT NULL"
        )
    else:
        assignments = ", ".join(
            f"f.{facet} = r.{generated}" for facet, generated in _FACET_COLUMNS
        )
        op.execute(
            f"UPDATE roms_facets f JOIN roms r ON r.id = f.rom_id "  # nosec B608
            f"SET {assignments} WHERE r.{_STEAM} IS NOT NULL"
        )

    types = ", ".join(f"'{type_}'" for type_, _ in _VC_TYPES)
    op.execute(
        f"DELETE FROM {_VC_TABLE} WHERE type IN ({types}) "  # nosec B608
        f"AND rom_id IN (SELECT id FROM roms WHERE {_STEAM} IS NOT NULL)"
    )
    insert = "INSERT INTO" if pg else "INSERT IGNORE INTO"
    conflict = "\nON CONFLICT DO NOTHING" if pg else ""
    op.execute(
        f"{insert} {_VC_TABLE} ({_VC_COLUMNS})\n{_vc_rows(pg)}{conflict}"  # nosec B608
    )


def upgrade() -> None:
    pg = is_postgresql(op.get_bind())
    _rebuild_generated_columns(pg, with_steam=True)
    _refresh_steam_rows(pg)


def downgrade() -> None:
    pg = is_postgresql(op.get_bind())
    _rebuild_generated_columns(pg, with_steam=False)
    _refresh_steam_rows(pg)
