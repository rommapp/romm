"""Materialize roms_metadata derivations as STORED generated columns

The ``roms_metadata`` VIEW re-derived its facet columns by JSON-parsing up to
eight raw provider-metadata blobs on every ``roms`` row, on every query. On
large libraries that made galleries, search, and sorts CPU-bound and slow.

This moves the per-row derivation into STORED generated columns on ``roms``
(``rm_*``), which the database engine computes once at write time and keeps in
sync automatically (no application hook, no background job). ``roms_metadata``
is redefined as a thin projection over those columns, so the ``RomMetadata``
model, every handler query, and the ``virtual_collections`` view are unchanged
and simply inherit the speedup. Indexes on the release-date, rating, and
player-count columns back the corresponding sorts and facet filters.

Cross-engine notes:
- MariaDB ``JSON_UNQUOTE`` is applied before every numeric ``CAST`` so a
  STORED column INSERT does not hit strict-mode truncation on quoted values
  (a plain ``SELECT`` from the old view silently produced ``0`` instead).
- PostgreSQL ``to_timestamp(text, text)`` is ``STABLE`` and so illegal in a
  generated column; the gamelist date is parsed through an ``IMMUTABLE`` UTC
  wrapper function instead.

Revision ID: 0098_generated_metadata_columns
Revises: 0097_roms_platform_fs_size_index
Create Date: 2026-07-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0098_generated_metadata_columns"
down_revision = "0097_roms_platform_fs_size_index"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# MariaDB / MySQL generated-column expressions
# ---------------------------------------------------------------------------

_MY_ARRAY_COALESCE = {
    "rm_genres": [
        "manual_metadata",
        "igdb_metadata",
        "moby_metadata",
        "ss_metadata",
        "launchbox_metadata",
        "ra_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    ],
    "rm_franchises": [
        "manual_metadata",
        "igdb_metadata",
        "ss_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    ],
    "rm_companies": [
        "manual_metadata",
        "igdb_metadata",
        "ss_metadata",
        "ra_metadata",
        "launchbox_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    ],
    "rm_game_modes": [
        "manual_metadata",
        "igdb_metadata",
        "ss_metadata",
        "flashpoint_metadata",
    ],
}


def _my_array_expr(column: str, sources: list[str]) -> str:
    key = column[len("rm_") :]
    branches = [
        f"CASE WHEN JSON_LENGTH(JSON_EXTRACT({src}, '$.{key}')) > 0 "
        f"THEN JSON_EXTRACT({src}, '$.{key}') ELSE NULL END"
        for src in sources
    ]
    branches.append("JSON_ARRAY()")
    return "COALESCE(\n    " + ",\n    ".join(branches) + "\n)"


def _my_first_release_date() -> str:
    # (source, multiplier, integer-only regex flag)
    int_sources = [
        ("manual_metadata", 1),
        ("igdb_metadata", 1000),
        ("ss_metadata", 1000),
        ("ra_metadata", 1000),
        ("launchbox_metadata", 1000),
        ("flashpoint_metadata", 1000),
    ]
    branches = []
    for src, mult in int_sources:
        val = f"JSON_UNQUOTE(JSON_EXTRACT({src}, '$.first_release_date'))"
        cast = f"CAST({val} AS SIGNED)"
        if mult != 1:
            cast = f"{cast} * {mult}"
        branches.append(
            f"WHEN JSON_CONTAINS_PATH({src}, 'one', '$.first_release_date') "
            f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
            f"AND {val} REGEXP '^[0-9]+$' THEN {cast}"
        )
    gl = "JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.first_release_date'))"
    # TIMESTAMPDIFF from the UTC epoch is pure calendar arithmetic, so (unlike
    # UNIX_TIMESTAMP) the stored value does not depend on the session time zone.
    branches.append(
        f"WHEN JSON_CONTAINS_PATH(gamelist_metadata, 'one', '$.first_release_date') "
        f"AND {gl} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {gl} REGEXP '^[0-9]{{8}}T[0-9]{{6}}$' "
        f"THEN TIMESTAMPDIFF(SECOND, '1970-01-01 00:00:00', STR_TO_DATE({gl}, '%Y%m%dT%H%i%S')) * 1000"
    )
    return "CASE\n    " + "\n    ".join(branches) + "\n    ELSE NULL END"


def _my_rating(source: str, key: str, multiplier: int) -> str:
    val = f"JSON_UNQUOTE(JSON_EXTRACT({source}, '$.{key}'))"
    cast = f"CAST({val} AS DECIMAL(10,2))"
    if multiplier != 1:
        cast = f"{cast} * {multiplier}"
    return (
        f"CASE WHEN JSON_CONTAINS_PATH({source}, 'one', '$.{key}') "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} REGEXP '^[0-9]+(\\\\.[0-9]+)?$' THEN {cast} ELSE NULL END"
    )


_MY_RATINGS = [
    _my_rating("igdb_metadata", "total_rating", 1),
    _my_rating("moby_metadata", "moby_score", 10),
    _my_rating("ss_metadata", "ss_score", 10),
    _my_rating("launchbox_metadata", "community_rating", 20),
    _my_rating("gamelist_metadata", "rating", 100),
]


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


_MY_AGE_RATINGS = """COALESCE(
    JSON_EXTRACT(manual_metadata, '$.age_ratings'),
    CASE WHEN JSON_CONTAINS_PATH(igdb_metadata, 'one', '$.age_ratings')
        AND JSON_LENGTH(JSON_EXTRACT(igdb_metadata, '$.age_ratings')) > 0
        THEN IF(
            JSON_TYPE(JSON_EXTRACT(igdb_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
            JSON_EXTRACT(igdb_metadata, '$.age_ratings[*].rating'),
            JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.age_ratings[*].rating')))
        ) ELSE NULL END,
    CASE WHEN JSON_CONTAINS_PATH(ss_metadata, 'one', '$.age_ratings')
        AND JSON_LENGTH(JSON_EXTRACT(ss_metadata, '$.age_ratings')) > 0
        THEN IF(
            JSON_TYPE(JSON_EXTRACT(ss_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
            JSON_EXTRACT(ss_metadata, '$.age_ratings[*].rating'),
            JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.age_ratings[*].rating')))
        ) ELSE NULL END,
    CASE WHEN JSON_CONTAINS_PATH(launchbox_metadata, 'one', '$.esrb')
        AND JSON_EXTRACT(launchbox_metadata, '$.esrb') IS NOT NULL
        AND JSON_EXTRACT(launchbox_metadata, '$.esrb') != ''
        THEN JSON_ARRAY(JSON_EXTRACT(launchbox_metadata, '$.esrb')) ELSE NULL END,
    JSON_ARRAY()
)"""

_MY_PLAYER_COUNT = """COALESCE(
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(manual_metadata, '$.player_count')), '1'),
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.player_count')), '1'),
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.player_count')), '1'),
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.player_count')), '1'),
    '1'
)"""


def _mysql_columns() -> list[tuple[str, str, str]]:
    """Return (name, type, expression) for each MariaDB generated column."""
    cols: list[tuple[str, str, str]] = []
    for name, sources in _MY_ARRAY_COALESCE.items():
        cols.append((name, "JSON", _my_array_expr(name, sources)))
    cols.append(
        (
            "rm_collections",
            "JSON",
            "COALESCE(JSON_EXTRACT(igdb_metadata, '$.collections'), JSON_ARRAY())",
        )
    )
    cols.append(("rm_age_ratings", "JSON", _MY_AGE_RATINGS))
    cols.append(("rm_first_release_date", "BIGINT", _my_first_release_date()))
    cols.append(("rm_average_rating", "DOUBLE", _average_expr(_MY_RATINGS)))
    cols.append(("rm_player_count", "VARCHAR(100)", _MY_PLAYER_COUNT))
    return cols


# ---------------------------------------------------------------------------
# PostgreSQL generated-column expressions
# ---------------------------------------------------------------------------

_PG_ARRAY_COALESCE = _MY_ARRAY_COALESCE  # same source precedence per column


def _pg_array_expr(column: str, sources: list[str]) -> str:
    key = column[len("rm_") :]
    branches = [f"NULLIF({src} -> '{key}', '[]'::jsonb)" for src in sources]
    branches.append("'[]'::jsonb")
    return "COALESCE(\n    " + ",\n    ".join(branches) + "\n)"


def _pg_first_release_date() -> str:
    int_sources = [
        ("manual_metadata", 1),
        ("igdb_metadata", 1000),
        ("ss_metadata", 1000),
        ("ra_metadata", 1000),
        ("launchbox_metadata", 1000),
        ("flashpoint_metadata", 1000),
    ]
    branches = []
    for src, mult in int_sources:
        val = f"{src} ->> 'first_release_date'"
        cast = f"({val})::bigint"
        if mult != 1:
            cast = f"{cast} * {mult}"
        branches.append(
            f"WHEN {src} IS NOT NULL AND {src} ? 'first_release_date' "
            f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
            f"AND {val} ~ '^[0-9]+$' THEN {cast}"
        )
    gl = "gamelist_metadata ->> 'first_release_date'"
    branches.append(
        f"WHEN gamelist_metadata IS NOT NULL AND gamelist_metadata ? 'first_release_date' "
        f"AND {gl} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {gl} ~ '^[0-9]{{8}}T[0-9]{{6}}$' "
        f"THEN romm_gamelist_epoch_ms({gl})"
    )
    return "CASE\n    " + "\n    ".join(branches) + "\n    ELSE NULL END"


def _pg_rating(source: str, key: str, multiplier: int) -> str:
    val = f"{source} ->> '{key}'"
    cast = f"({val})::float"
    if multiplier != 1:
        cast = f"{cast} * {multiplier}"
    return (
        f"CASE WHEN {source} IS NOT NULL AND {source} ? '{key}' "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} ~ '^[0-9]+(\\.[0-9]+)?$' THEN {cast} ELSE NULL END"
    )


_PG_RATINGS = [
    _pg_rating("igdb_metadata", "total_rating", 1),
    _pg_rating("moby_metadata", "moby_score", 10),
    _pg_rating("ss_metadata", "ss_score", 10),
    _pg_rating("launchbox_metadata", "community_rating", 20),
    _pg_rating("gamelist_metadata", "rating", 100),
]

# jsonb_build_array is STABLE (not usable in a generated column), so the whole
# age-ratings derivation is wrapped in an IMMUTABLE helper. The computation is
# deterministic on its inputs; the STABLE marking of jsonb_build_array is only a
# conservative default for its timestamp-typed overloads, which we never hit.
_PG_AGE_RATINGS = (
    "romm_age_ratings(manual_metadata, igdb_metadata, ss_metadata, launchbox_metadata)"
)

_PG_PLAYER_COUNT = """COALESCE(
    NULLIF(manual_metadata ->> 'player_count', '1'),
    NULLIF(ss_metadata ->> 'player_count', '1'),
    NULLIF(igdb_metadata ->> 'player_count', '1'),
    NULLIF(gamelist_metadata ->> 'player_count', '1'),
    '1'
)"""


def _pg_columns() -> list[tuple[str, str, str]]:
    cols: list[tuple[str, str, str]] = []
    for name, sources in _PG_ARRAY_COALESCE.items():
        cols.append((name, "JSONB", _pg_array_expr(name, sources)))
    cols.append(
        (
            "rm_collections",
            "JSONB",
            "COALESCE((igdb_metadata -> 'collections'), '[]'::jsonb)",
        )
    )
    cols.append(("rm_age_ratings", "JSONB", _PG_AGE_RATINGS))
    cols.append(("rm_first_release_date", "BIGINT", _pg_first_release_date()))
    cols.append(("rm_average_rating", "DOUBLE PRECISION", _average_expr(_PG_RATINGS)))
    cols.append(("rm_player_count", "VARCHAR(100)", _PG_PLAYER_COUNT))
    return cols


# Order of columns in the roms_metadata projection (name -> view alias).
_VIEW_COLUMNS = [
    ("rm_genres", "genres"),
    ("rm_franchises", "franchises"),
    ("rm_collections", "collections"),
    ("rm_companies", "companies"),
    ("rm_game_modes", "game_modes"),
    ("rm_age_ratings", "age_ratings"),
    ("rm_first_release_date", "first_release_date"),
    ("rm_average_rating", "average_rating"),
    ("rm_player_count", "player_count"),
]

_INDEXED_COLUMNS = [
    "rm_first_release_date",
    "rm_average_rating",
    "rm_player_count",
]


def _thin_view_sql(is_pg: bool) -> str:
    projections = []
    for name, alias in _VIEW_COLUMNS:
        # PostgreSQL CREATE OR REPLACE VIEW cannot change a column's type, and
        # the legacy view exposed player_count as text; cast to match so the
        # replace succeeds (and the downgrade can replace back).
        if is_pg and alias == "player_count":
            projections.append(f"{name}::text AS {alias}")
        else:
            projections.append(f"{name} AS {alias}")
    projection = ",\n    ".join(projections)
    return (
        "CREATE OR REPLACE VIEW roms_metadata AS\n"  # nosec B608
        "SELECT\n"
        "    id AS rom_id,\n"
        "    NOW() AS created_at,\n"
        "    NOW() AS updated_at,\n"
        f"    {projection}\n"
        "FROM roms"
    )


# Parse a gamelist "YYYYMMDDThhmmss" string as a UTC epoch in milliseconds.
# make_timestamp is IMMUTABLE and the components are interpreted as UTC, so the
# stored value is deterministic regardless of the writer's session time zone
# (to_timestamp() is only STABLE and would freeze a session-local value).
_GAMELIST_EPOCH_FN = """
CREATE OR REPLACE FUNCTION romm_gamelist_epoch_ms(s text) RETURNS bigint
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT (extract(epoch FROM make_timestamp(
        substr(s, 1, 4)::int, substr(s, 5, 2)::int, substr(s, 7, 2)::int,
        substr(s, 10, 2)::int, substr(s, 12, 2)::int, substr(s, 14, 2)::int
    ) AT TIME ZONE 'UTC') * 1000)::bigint
$$
"""

_AGE_RATINGS_FN = """
CREATE OR REPLACE FUNCTION romm_age_ratings(manual jsonb, igdb jsonb, ss jsonb, launchbox jsonb)
    RETURNS jsonb LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT COALESCE(
        (manual -> 'age_ratings'),
        CASE WHEN igdb IS NOT NULL AND igdb ? 'age_ratings'
            AND jsonb_array_length(igdb -> 'age_ratings') > 0
            THEN jsonb_path_query_array(igdb, '$.age_ratings[*].rating') ELSE NULL END,
        CASE WHEN ss IS NOT NULL AND ss ? 'age_ratings'
            AND jsonb_array_length(ss -> 'age_ratings') > 0
            THEN jsonb_path_query_array(ss, '$.age_ratings[*].rating') ELSE NULL END,
        CASE WHEN launchbox IS NOT NULL AND launchbox ? 'esrb'
            AND launchbox ->> 'esrb' IS NOT NULL
            AND launchbox ->> 'esrb' != ''
            THEN jsonb_build_array(launchbox ->> 'esrb') ELSE NULL END,
        '[]'::jsonb
    )
$$
"""


def upgrade() -> None:
    connection = op.get_bind()

    pg = is_postgresql(connection)
    if pg:
        connection.execute(sa.text(_GAMELIST_EPOCH_FN))
        connection.execute(sa.text(_AGE_RATINGS_FN))
        columns = _pg_columns()
    else:
        columns = _mysql_columns()

    adds = ",\n".join(
        f"ADD COLUMN {name} {type_} GENERATED ALWAYS AS ({expr}) STORED"
        for name, type_, expr in columns
    )
    op.execute(f"ALTER TABLE roms\n{adds}")  # nosec B608

    for col in _INDEXED_COLUMNS:
        op.create_index(f"idx_roms_{col}", "roms", [col])

    op.execute(_thin_view_sql(pg))


def downgrade() -> None:
    connection = op.get_bind()

    # Restore the derive-on-read view before dropping the columns it no longer
    # references, so virtual_collections (which depends on it) stays valid.
    if is_postgresql(connection):
        op.execute(_PG_LEGACY_VIEW)
    else:
        op.execute(_MY_LEGACY_VIEW)

    for col in _INDEXED_COLUMNS:
        op.drop_index(f"idx_roms_{col}", table_name="roms")

    drops = ",\n".join(f"DROP COLUMN {name}" for name, _, _ in _mysql_columns())
    op.execute(f"ALTER TABLE roms\n{drops}")  # nosec B608

    if is_postgresql(connection):
        op.execute("DROP FUNCTION IF EXISTS romm_gamelist_epoch_ms(text)")
        op.execute(
            "DROP FUNCTION IF EXISTS romm_age_ratings(jsonb, jsonb, jsonb, jsonb)"
        )


# ---------------------------------------------------------------------------
# Legacy derive-on-read view definitions (verbatim from 0074), used only by
# downgrade() to restore the pre-0098 behavior.
# ---------------------------------------------------------------------------

_PG_LEGACY_VIEW = """
CREATE OR REPLACE VIEW roms_metadata AS
SELECT
    r.id AS rom_id,
    NOW() AS created_at,
    NOW() AS updated_at,
    COALESCE(
        NULLIF(r.manual_metadata -> 'genres', '[]'::jsonb),
        NULLIF(r.igdb_metadata -> 'genres', '[]'::jsonb),
        NULLIF(r.moby_metadata -> 'genres', '[]'::jsonb),
        NULLIF(r.ss_metadata -> 'genres', '[]'::jsonb),
        NULLIF(r.launchbox_metadata -> 'genres', '[]'::jsonb),
        NULLIF(r.ra_metadata -> 'genres', '[]'::jsonb),
        NULLIF(r.flashpoint_metadata -> 'genres', '[]'::jsonb),
        NULLIF(r.gamelist_metadata -> 'genres', '[]'::jsonb),
        '[]'::jsonb
    ) AS genres,
    COALESCE(
        NULLIF(r.manual_metadata -> 'franchises', '[]'::jsonb),
        NULLIF(r.igdb_metadata -> 'franchises', '[]'::jsonb),
        NULLIF(r.ss_metadata -> 'franchises', '[]'::jsonb),
        NULLIF(r.flashpoint_metadata -> 'franchises', '[]'::jsonb),
        NULLIF(r.gamelist_metadata -> 'franchises', '[]'::jsonb),
        '[]'::jsonb
    ) AS franchises,
    COALESCE(
        (r.igdb_metadata -> 'collections'),
        '[]'::jsonb
    ) AS collections,
    COALESCE(
        NULLIF(r.manual_metadata -> 'companies', '[]'::jsonb),
        NULLIF(r.igdb_metadata -> 'companies', '[]'::jsonb),
        NULLIF(r.ss_metadata -> 'companies', '[]'::jsonb),
        NULLIF(r.ra_metadata -> 'companies', '[]'::jsonb),
        NULLIF(r.launchbox_metadata -> 'companies', '[]'::jsonb),
        NULLIF(r.flashpoint_metadata -> 'companies', '[]'::jsonb),
        NULLIF(r.gamelist_metadata -> 'companies', '[]'::jsonb),
        '[]'::jsonb
    ) AS companies,
    COALESCE(
        NULLIF(r.manual_metadata -> 'game_modes', '[]'::jsonb),
        NULLIF(r.igdb_metadata -> 'game_modes', '[]'::jsonb),
        NULLIF(r.ss_metadata -> 'game_modes', '[]'::jsonb),
        NULLIF(r.flashpoint_metadata -> 'game_modes', '[]'::jsonb),
        '[]'::jsonb
    ) AS game_modes,
    COALESCE(
        (r.manual_metadata -> 'age_ratings'),
        CASE
            WHEN r.igdb_metadata IS NOT NULL
                AND r.igdb_metadata ? 'age_ratings'
                AND jsonb_array_length(r.igdb_metadata -> 'age_ratings') > 0
            THEN jsonb_path_query_array(r.igdb_metadata, '$.age_ratings[*].rating')
            ELSE NULL
        END,
        CASE
            WHEN r.ss_metadata IS NOT NULL
                AND r.ss_metadata ? 'age_ratings'
                AND jsonb_array_length(r.ss_metadata -> 'age_ratings') > 0
            THEN jsonb_path_query_array(r.ss_metadata, '$.age_ratings[*].rating')
            ELSE NULL
        END,
        CASE
            WHEN r.launchbox_metadata IS NOT NULL
                AND r.launchbox_metadata ? 'esrb'
                AND r.launchbox_metadata ->> 'esrb' IS NOT NULL
                AND r.launchbox_metadata ->> 'esrb' != ''
            THEN jsonb_build_array(r.launchbox_metadata ->> 'esrb')
            ELSE NULL
        END,
        '[]'::jsonb
    ) AS age_ratings,
    CASE
        WHEN r.manual_metadata IS NOT NULL AND r.manual_metadata ? 'first_release_date' AND
            r.manual_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
            r.manual_metadata ->> 'first_release_date' ~ '^[0-9]+$'
        THEN (r.manual_metadata ->> 'first_release_date')::bigint
        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'first_release_date' AND
            r.igdb_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
            r.igdb_metadata ->> 'first_release_date' ~ '^[0-9]+$'
        THEN (r.igdb_metadata ->> 'first_release_date')::bigint * 1000
        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'first_release_date' AND
            r.ss_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
            r.ss_metadata ->> 'first_release_date' ~ '^[0-9]+$'
        THEN (r.ss_metadata ->> 'first_release_date')::bigint * 1000
        WHEN r.ra_metadata IS NOT NULL AND r.ra_metadata ? 'first_release_date' AND
            r.ra_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
            r.ra_metadata ->> 'first_release_date' ~ '^[0-9]+$'
        THEN (r.ra_metadata ->> 'first_release_date')::bigint * 1000
        WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'first_release_date' AND
            r.launchbox_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
            r.launchbox_metadata ->> 'first_release_date' ~ '^[0-9]+$'
        THEN (r.launchbox_metadata ->> 'first_release_date')::bigint * 1000
        WHEN r.flashpoint_metadata IS NOT NULL AND r.flashpoint_metadata ? 'first_release_date' AND
            r.flashpoint_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
            r.flashpoint_metadata ->> 'first_release_date' ~ '^[0-9]+$'
        THEN (r.flashpoint_metadata ->> 'first_release_date')::bigint * 1000
        WHEN r.gamelist_metadata IS NOT NULL
            AND r.gamelist_metadata ? 'first_release_date'
            AND r.gamelist_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0')
            AND r.gamelist_metadata ->> 'first_release_date' ~ '^[0-9]{8}T[0-9]{6}$'
        THEN (extract(epoch FROM to_timestamp(r.gamelist_metadata ->> 'first_release_date', 'YYYYMMDD"T"HH24MISS')) * 1000)::bigint
        ELSE NULL
    END AS first_release_date,
    CASE
        WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL OR launchbox_rating IS NOT NULL OR gamelist_rating IS NOT NULL) THEN
            (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0) + COALESCE(launchbox_rating, 0) + COALESCE(gamelist_rating, 0)) /
            (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN launchbox_rating IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN gamelist_rating IS NOT NULL THEN 1 ELSE 0 END)
        ELSE NULL
    END AS average_rating,
    COALESCE(
        NULLIF(r.manual_metadata ->> 'player_count', '1'),
        NULLIF(r.ss_metadata ->> 'player_count', '1'),
        NULLIF(r.igdb_metadata ->> 'player_count', '1'),
        NULLIF(r.gamelist_metadata ->> 'player_count', '1'),
        '1'
    ) AS player_count
FROM (
    SELECT
        r.id,
        r.manual_metadata,
        r.igdb_metadata,
        r.moby_metadata,
        r.ss_metadata,
        r.ra_metadata,
        r.launchbox_metadata,
        r.flashpoint_metadata,
        r.gamelist_metadata,
        CASE
            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating' AND
                r.igdb_metadata ->> 'total_rating' NOT IN ('null', 'None', '0', '0.0') AND
                r.igdb_metadata ->> 'total_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
            THEN (r.igdb_metadata ->> 'total_rating')::float
            ELSE NULL
        END AS igdb_rating,
        CASE
            WHEN r.moby_metadata IS NOT NULL AND r.moby_metadata ? 'moby_score' AND
                r.moby_metadata ->> 'moby_score' NOT IN ('null', 'None', '0', '0.0') AND
                r.moby_metadata ->> 'moby_score' ~ '^[0-9]+(\\.[0-9]+)?$'
            THEN (r.moby_metadata ->> 'moby_score')::float * 10
            ELSE NULL
        END AS moby_rating,
        CASE
            WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'ss_score' AND
                r.ss_metadata ->> 'ss_score' NOT IN ('null', 'None', '0', '0.0') AND
                r.ss_metadata ->> 'ss_score' ~ '^[0-9]+(\\.[0-9]+)?$'
            THEN (r.ss_metadata ->> 'ss_score')::float * 10
            ELSE NULL
        END AS ss_rating,
        CASE
            WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'community_rating' AND
                r.launchbox_metadata ->> 'community_rating' NOT IN ('null', 'None', '0', '0.0') AND
                r.launchbox_metadata ->> 'community_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
            THEN (r.launchbox_metadata ->> 'community_rating')::float * 20
            ELSE NULL
        END AS launchbox_rating,
        CASE
            WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'rating' AND
                r.gamelist_metadata ->> 'rating' NOT IN ('null', 'None', '0', '0.0') AND
                r.gamelist_metadata ->> 'rating' ~ '^[0-9]+(\\.[0-9]+)?$'
            THEN (r.gamelist_metadata ->> 'rating')::float * 100
            ELSE NULL
        END AS gamelist_rating
    FROM roms r
) AS r
"""

_MY_LEGACY_VIEW = """
CREATE OR REPLACE VIEW roms_metadata AS
    SELECT
        r.id as rom_id,
        NOW() AS created_at,
        NOW() AS updated_at,
        COALESCE(
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.genres') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.genres') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.moby_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.moby_metadata, '$.genres') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.genres') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.launchbox_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.launchbox_metadata, '$.genres') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ra_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.ra_metadata, '$.genres') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.genres') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.genres') ELSE NULL END,
            JSON_ARRAY()
        ) AS genres,
        COALESCE(
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.franchises') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.franchises') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.franchises') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.franchises') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.franchises') ELSE NULL END,
            JSON_ARRAY()
        ) AS franchises,
        COALESCE(
            JSON_EXTRACT(r.igdb_metadata, '$.collections'),
            JSON_ARRAY()
        ) AS collections,
        COALESCE(
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.companies') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.companies') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.companies') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ra_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.ra_metadata, '$.companies') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.launchbox_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.launchbox_metadata, '$.companies') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.companies') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.companies') ELSE NULL END,
            JSON_ARRAY()
        ) AS companies,
        COALESCE(
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.game_modes') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.game_modes') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.game_modes') ELSE NULL END,
            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.game_modes') ELSE NULL END,
            JSON_ARRAY()
        ) AS game_modes,
        COALESCE(
            JSON_EXTRACT(r.manual_metadata, '$.age_ratings'),
            CASE
                WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.age_ratings')
                    AND JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings')) > 0
                THEN IF(
                        JSON_TYPE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                        JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating'),
                        JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')))
                    )
                ELSE NULL
            END,
            CASE
                WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.age_ratings')
                    AND JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.age_ratings')) > 0
                THEN IF(
                        JSON_TYPE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                        JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating'),
                        JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')))
                    )
                ELSE NULL
            END,
            CASE
                WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.esrb')
                    AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') IS NOT NULL
                    AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') != ''
                THEN JSON_ARRAY(JSON_EXTRACT(r.launchbox_metadata, '$.esrb'))
                ELSE NULL
            END,
            JSON_ARRAY()
        ) AS age_ratings,
        CASE
            WHEN JSON_CONTAINS_PATH(r.manual_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_EXTRACT(r.manual_metadata, '$.first_release_date') AS SIGNED)
            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date') AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_EXTRACT(r.ss_metadata, '$.first_release_date') AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.ra_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ra_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ra_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_EXTRACT(r.ra_metadata, '$.first_release_date') AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date') AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.flashpoint_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date') AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.gamelist_metadata, 'one', '$.first_release_date')
                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')) REGEXP '^[0-9]{8}T[0-9]{6}$'
            THEN UNIX_TIMESTAMP(
                STR_TO_DATE(
                    JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')),
                    '%Y%m%dT%H%i%S'
                )
            ) * 1000
            ELSE NULL
        END AS first_release_date,
        CASE
            WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL OR launchbox_rating IS NOT NULL OR gamelist_rating IS NOT NULL) THEN
                (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0) + COALESCE(launchbox_rating, 0) + COALESCE(gamelist_rating, 0)) /
                (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN launchbox_rating IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN gamelist_rating IS NOT NULL THEN 1 ELSE 0 END)
            ELSE NULL
        END AS average_rating,
        COALESCE(
            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.player_count')), '1'),
            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.player_count')), '1'),
            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.player_count')), '1'),
            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.player_count')), '1'),
            '1'
        ) AS player_count
    FROM (
        SELECT
            id,
            manual_metadata,
            igdb_metadata,
            moby_metadata,
            ss_metadata,
            ra_metadata,
            launchbox_metadata,
            flashpoint_metadata,
            gamelist_metadata,
            CASE
                WHEN JSON_CONTAINS_PATH(igdb_metadata, 'one', '$.total_rating') AND
                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_EXTRACT(igdb_metadata, '$.total_rating') AS DECIMAL(10,2))
                ELSE NULL
            END AS igdb_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(moby_metadata, 'one', '$.moby_score') AND
                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_EXTRACT(moby_metadata, '$.moby_score') AS DECIMAL(10,2)) * 10
                ELSE NULL
            END AS moby_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(ss_metadata, 'one', '$.ss_score') AND
                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_EXTRACT(ss_metadata, '$.ss_score') AS DECIMAL(10,2)) * 10
                ELSE NULL
            END AS ss_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(launchbox_metadata, 'one', '$.community_rating') AND
                    JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_EXTRACT(launchbox_metadata, '$.community_rating') AS DECIMAL(10,2)) * 20
                ELSE NULL
            END AS launchbox_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(gamelist_metadata, 'one', '$.rating') AND
                    JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.rating')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_EXTRACT(gamelist_metadata, '$.rating') AS DECIMAL(10,2)) * 100
                ELSE NULL
            END AS gamelist_rating
        FROM roms
    ) AS r
"""
