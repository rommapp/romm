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

PostgreSQL cannot change a generated column's expression in place, so the
Steam-fed columns are dropped and re-added; the new columns are plain adds
in the same ALTER TABLE. The view and the indexes that depend on them are
recreated around it.

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

# revision identifiers, used by Alembic.
revision = "0123_recommendation_metadata"
down_revision = "0122_rom_similarity"
branch_labels = None
depends_on = None

_STEAM = "steam_metadata"

# Provider precedence per rebuilt array column, as 0098 and 0112 left it.
# Steam is appended to each chain when the columns are rebuilt with it.
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

# Only IGDB supplies the tags and the vote count, plus `manual_metadata` so a
# user override still wins.
_IGDB_SOURCES = ["manual_metadata", "igdb_metadata"]

# (generated column, roms_facets column) for the columns this migration adds.
_TAG_COLUMNS = [
    ("generated_keywords", "keywords"),
    ("generated_themes", "themes"),
    ("generated_player_perspectives", "player_perspectives"),
]
_RATING_COUNT_COLUMN = "generated_rating_count"

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

# roms_facets mirrors whose value this migration can change: the Steam-fed
# columns plus the tag columns it adds.
_FACET_COLUMNS = [
    ("genres", "generated_genres"),
    ("companies", "generated_companies"),
    ("game_modes", "generated_game_modes"),
    ("publishers", "generated_publishers"),
    ("developers", "generated_developers"),
] + [(facet, generated) for generated, facet in _TAG_COLUMNS]

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

# Every column `roms_metadata` projects, in the order 0121 left it with the
# new ones appended. The view is recreated, so the old projections have to be
# restated.
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
_VIEW_COLUMNS = (
    _BASE_VIEW_COLUMNS + _TAG_COLUMNS + [(_RATING_COUNT_COLUMN, "rating_count")]
)

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
    (facet, generated) for generated, facet in _TAG_COLUMNS
]

_MYSQL_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


# ---------------------------------------------------------------------------
# MariaDB / MySQL expressions (verbatim from 0098 and 0112, Steam appended)
# ---------------------------------------------------------------------------


def _maria_text(source: str, path: str) -> str:
    """Unquoted JSON text carrying the surrounding expression's collation.

    0098's helper, needed for the same reason: MariaDB gives JSON_UNQUOTE the
    connection charset's default collation while a literal in a generated
    column takes the table's, so comparing them is an illegal mix on a table
    that is not `general_ci`.
    """
    return f"CAST(JSON_UNQUOTE(JSON_EXTRACT({source}, '{path}')) AS CHAR)"


def _maria_array_expr(key: str, sources: list[str]) -> str:
    branches = [
        f"CASE WHEN JSON_LENGTH(JSON_EXTRACT({src}, '$.{key}')) > 0 "
        f"THEN JSON_EXTRACT({src}, '$.{key}') ELSE NULL END"
        for src in sources
    ]
    branches.append("JSON_ARRAY()")
    return "COALESCE(\n    " + ",\n    ".join(branches) + "\n)"


def _maria_int_date_branch(src: str, mult: int) -> str:
    val = _maria_text(src, "$.first_release_date")
    cast = f"CAST({val} AS SIGNED)"
    if mult != 1:
        cast = f"{cast} * {mult}"
    return (
        f"WHEN JSON_CONTAINS_PATH({src}, 'one', '$.first_release_date') "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} REGEXP '^[0-9]+$' THEN {cast}"
    )


def _maria_gamelist_date_branch() -> str:
    gl = _maria_text("gamelist_metadata", "$.first_release_date")
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
    val = _maria_text(source, f"$.{key}")
    cast = f"CAST({val} AS DECIMAL(10,2))"
    if multiplier != 1:
        cast = f"{cast} * {multiplier}"
    return (
        f"CASE WHEN JSON_CONTAINS_PATH({source}, 'one', '$.{key}') "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} REGEXP '^[0-9]+(\\\\.[0-9]+)?$' THEN {cast} ELSE NULL END"
    )


def _maria_rating_count() -> str:
    # JSON_UNQUOTE(JSON_EXTRACT(...)) rather than JSON_VALUE, which MySQL only
    # gained in 8.0.21; digit-checked before the cast like every other numeric
    # branch here, so a non-numeric blob value falls through instead of casting
    # to a silent 0.
    branches = []
    for src in _IGDB_SOURCES:
        val = _maria_text(src, "$.total_rating_count")
        branches.append(
            f"CASE WHEN JSON_CONTAINS_PATH({src}, 'one', '$.total_rating_count') "
            f"AND {val} REGEXP '^[0-9]+$' THEN CAST({val} AS SIGNED) ELSE NULL END"
        )
    return "COALESCE(" + ", ".join(branches) + ", 0)"


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


def _postgres_rating_count() -> str:
    # Digit-checked before the cast, as every other numeric branch here is:
    # the blobs are writable verbatim through the raw-metadata form, and an
    # uncastable value in a generated column rejects every write to the row.
    branches = [
        f"CASE WHEN {src} IS NOT NULL AND {src} ? 'total_rating_count' "
        f"AND ({src} ->> 'total_rating_count') ~ '^[0-9]+$' "
        f"THEN ({src} ->> 'total_rating_count')::bigint ELSE NULL END"
        for src in _IGDB_SOURCES
    ]
    return "COALESCE(" + ", ".join(branches) + ", 0)::bigint"


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


def _rebuilt_columns(pg: bool, with_steam: bool) -> list[tuple[str, str, str]]:
    """(name, type, expression) for the columns whose expression Steam changes.

    PostgreSQL cannot alter a generated expression, so these are dropped and
    re-added rather than modified.
    """
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


def _added_columns(pg: bool) -> list[tuple[str, str, str]]:
    """(name, type, expression) for the columns this migration introduces."""
    array_expr = _postgres_array_expr if pg else _maria_array_expr
    columns = [
        (name, "JSONB" if pg else "JSON", array_expr(facet, _IGDB_SOURCES))
        for name, facet in _TAG_COLUMNS
    ]
    count_expr = _postgres_rating_count() if pg else _maria_rating_count()
    columns.append((_RATING_COUNT_COLUMN, "BIGINT", count_expr))
    return columns


def _view_sql(pg: bool, columns: list[tuple[str, str]]) -> str:
    projections = ",\n    ".join(
        # 0098 exposed player_count as text; kept so later CREATE OR REPLACE
        # VIEW statements on PostgreSQL still match the column's type.
        (
            f"{name}::text AS {alias}"
            if pg and alias == "player_count"
            else f"{name} AS {alias}"
        )
        for name, alias in columns
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


def _rebuild_columns(
    pg: bool,
    *,
    with_steam: bool,
    add: list[tuple[str, str, str]],
    drop: list[str],
    view_columns: list[tuple[str, str]],
) -> None:
    """Swap every generated column this migration touches in one ALTER TABLE.

    Each STORED generated column costs a full table rebuild, so they are
    batched: adding them one migration at a time rewrote `roms` three times.
    """
    rebuilt = _rebuilt_columns(pg, with_steam)

    # The view projects the columns being dropped, so it goes first.
    op.execute("DROP VIEW IF EXISTS roms_metadata")

    actions = (
        [f"DROP COLUMN {name}" for name, _, _ in rebuilt]
        + [f"DROP COLUMN {name}" for name in drop]
        + [
            f"ADD COLUMN {name} {type_} GENERATED ALWAYS AS ({expr}) STORED"
            for name, type_, expr in rebuilt + add
        ]
    )
    op.execute("ALTER TABLE roms\n" + ",\n".join(actions))  # nosec B608

    # MariaDB carries a single-column index across the drop and re-add;
    # PostgreSQL drops it with the column.
    existing = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("roms")
    }
    for column in _INDEXED_COLUMNS:
        if f"idx_roms_{column}" not in existing:
            op.create_index(f"idx_roms_{column}", "roms", [column])

    op.execute(_view_sql(pg, view_columns))


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


def _refresh_steam_collections(pg: bool) -> None:
    """Rebuild the virtual collections whose membership Steam can change.

    Only Steam-matched rows can move, so the rest are left alone.
    """
    if not _has_steam_rows():
        return

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

    _rebuild_columns(
        pg,
        with_steam=True,
        add=_added_columns(pg),
        drop=[],
        view_columns=_VIEW_COLUMNS,
    )

    for _, facet in _TAG_COLUMNS:
        op.add_column("roms_facets", sa.Column(facet, CustomJSON(), nullable=True))

    _sync_facets(pg, _FACET_COLUMNS)
    _rebuild_triggers(pg, _MIRRORED_COLUMNS)
    _refresh_steam_collections(pg)


def downgrade() -> None:
    pg = is_postgresql(op.get_bind())

    _rebuild_columns(
        pg,
        with_steam=False,
        add=[],
        drop=[name for name, _ in _TAG_COLUMNS] + [_RATING_COUNT_COLUMN],
        view_columns=_BASE_VIEW_COLUMNS,
    )

    for _, facet in _TAG_COLUMNS:
        op.drop_column("roms_facets", facet)

    _sync_facets(pg, [entry for entry in _FACET_COLUMNS if entry[0] not in {facet for _, facet in _TAG_COLUMNS}])  # fmt: skip
    _rebuild_triggers(pg, _BASE_MIRRORED_COLUMNS)
    _refresh_steam_collections(pg)
