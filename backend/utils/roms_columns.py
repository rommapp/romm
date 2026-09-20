"""The `roms` columns the revisions from 0108 on add, in a single table copy.

Every ALTER TABLE roms copies the table: the FULLTEXT index from 0084 rules out
an in-place add, and a STORED generated column takes ALGORITHM=COPY on every
engine. With a JSON blob per provider on each row, that copy is minutes on a
scraped library, so the first revision to find a column missing adds them all,
and its downgrade removes whatever a chain that stopped short still carries.

A later release that widens `roms` appends to the catalog below rather than
starting its own module, so its columns join the same copy. 0108 remains the
floor the front-loading and `drop_roms_columns` are anchored to.
"""

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.engine.interfaces import ReflectedColumn
from sqlalchemy.schema import CreateColumn

from models.rom import FULL_PATH_HASH_LENGTH, TITLE_ID_MAX_LENGTH
from utils.database import (
    HLTB_MAIN_STORY_COLUMN,
    SORTABLE_NULLABLE_ROM_COLUMNS,
    CustomJSON,
    column_names,
    full_path_digest_sql,
    is_mariadb,
    is_postgresql,
    rom_desc_index_name,
    rom_sort_index_name,
    rom_unset_flag_column,
)

TABLE = "roms"
VIEW = "roms_metadata"

PRIMARY_REGION_COLUMN = "generated_primary_region"
PRIMARY_REGION_LENGTH = 50
FULL_PATH_HASH_COLUMN = "full_path_hash"
RATING_COUNT_COLUMN = "generated_rating_count"

SAVE_TARGET_LAYOUT_COLUMN = "save_target_layout"
SAVE_TARGET_LAYOUT_ENUM = "savetargetlayout"
# A snapshot of `models.rom.SaveTargetLayout`, frozen so the enum this creates
# does not change under a fresh install the day the model grows a member.
SAVE_TARGET_LAYOUT_VALUES = (
    "FOLDER_EXACT",
    "FOLDER_PREFIX",
    "FILE_EXACT",
    "FILE_PREFIX",
    "FOLDER_SPLIT",
)

STEAM_METADATA_COLUMN = "steam_metadata"

# Provider precedence per array column, as 0098 and 0112 left it; 0123
# appended Steam at the lowest precedence.
STEAM_FED_ARRAY_SOURCES: dict[str, list[str]] = {
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

# (generated column, JSON key) for the IGDB tag columns 0123 introduced.
TAG_COLUMNS = [
    ("generated_keywords", "keywords"),
    ("generated_themes", "themes"),
    ("generated_player_perspectives", "player_perspectives"),
]

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
_STEAM_DATE = (STEAM_METADATA_COLUMN, 1000)

# (source, key, multiplier to a 0-100 scale) averaged into the rating.
_RATING_SOURCES = [
    ("igdb_metadata", "total_rating", 1),
    ("moby_metadata", "moby_score", 10),
    ("ss_metadata", "ss_score", 10),
    ("launchbox_metadata", "community_rating", 20),
    ("gamelist_metadata", "rating", 100),
]
# Steam carries the Metacritic score, already on a 0-100 scale.
_STEAM_RATING = (STEAM_METADATA_COLUMN, "total_rating", 1)

# Single-column indexes on generated columns that PostgreSQL drops with the
# column, so a rebuild recreates them.
INDEXED_GENERATED_COLUMNS = [
    "generated_first_release_date",
    "generated_average_rating",
]

# The columns 0123 redefined to read Steam. A table still carrying the older
# expression is rebuilt at the current one.
STEAM_FED_COLUMNS = [*STEAM_FED_ARRAY_SOURCES, *INDEXED_GENERATED_COLUMNS]

# 0112 added the other two Steam-fed columns; these predate 5.3.0, so this
# module redefines them but never adds or drops them.
INHERITED_COLUMNS = frozenset(STEAM_FED_COLUMNS) - {
    "generated_publishers",
    "generated_developers",
}

# Every column `roms_metadata` projects, in the order 0123 left it.
ROMS_METADATA_VIEW_COLUMNS = [
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
    *TAG_COLUMNS,
    (RATING_COUNT_COLUMN, "rating_count"),
]


@dataclass(frozen=True)
class GeneratedColumn:
    name: str
    type_: str
    expression: str

    @property
    def ddl(self) -> str:
        return (
            f"{self.name} {self.type_} GENERATED ALWAYS AS ({self.expression}) STORED"
        )

    @property
    def unset_flag(self) -> "GeneratedColumn":
        """This column's companion flag, over the same expression.

        Repeated rather than referenced: PostgreSQL forbids one generated
        column reading another, and a reference would block the DROP that
        `rebuild_generated_columns` issues.
        """
        return GeneratedColumn(
            rom_unset_flag_column(self.name),
            "BOOLEAN",
            f"({self.expression}) IS NULL",
        )


# ---------------------------------------------------------------------------
# MariaDB / MySQL expressions (0098's, with 0112, 0123 and 0128's additions)
# ---------------------------------------------------------------------------


def _maria_text(source: str, path: str) -> str:
    """Unquoted JSON text carrying the surrounding expression's collation."""
    # JSON_UNQUOTE takes the connection collation and a literal the table's, an
    # illegal mix on a table that is not `general_ci` unless CAST re-derives it.
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
    # STR_TO_DATE is barred from a generated column, so the "YYYYMMDDThhmmss"
    # string is reshaped into a datetime literal and range-checked by hand.
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
    # gained in 8.0.21; the digit check keeps a bad blob value from casting to 0.
    branches = []
    for src in _IGDB_SOURCES:
        val = _maria_text(src, "$.total_rating_count")
        branches.append(
            f"CASE WHEN JSON_CONTAINS_PATH({src}, 'one', '$.total_rating_count') "
            f"AND {val} REGEXP '^[0-9]+$' THEN CAST({val} AS SIGNED) ELSE NULL END"
        )
    return "COALESCE(" + ", ".join(branches) + ", 0)"


def _maria_hltb_main_story() -> str:
    val = _maria_text("hltb_metadata", "$.main_story")
    return (
        f"CASE WHEN JSON_CONTAINS_PATH(hltb_metadata, 'one', '$.main_story') "
        f"AND {val} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {val} REGEXP '^[0-9]+$' "
        f"THEN CAST({val} AS SIGNED) ELSE NULL END"
    )


# JSON_EXTRACT yields a quoted scalar, so JSON_UNQUOTE runs first; LEFT caps a
# value `regions` never did, which would fail the INSERT under strict mode.
_MARIA_PRIMARY_REGION = (
    f"LEFT(JSON_UNQUOTE(JSON_EXTRACT(regions, '$[0]')), {PRIMARY_REGION_LENGTH})"
)


# ---------------------------------------------------------------------------
# PostgreSQL expressions
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
    # The blobs are writable verbatim through the raw-metadata form, and an
    # uncastable value in a generated column would reject every write to the row.
    branches = [
        f"CASE WHEN {src} IS NOT NULL AND {src} ? 'total_rating_count' "
        f"AND ({src} ->> 'total_rating_count') ~ '^[0-9]+$' "
        f"THEN ({src} ->> 'total_rating_count')::bigint ELSE NULL END"
        for src in _IGDB_SOURCES
    ]
    return "COALESCE(" + ", ".join(branches) + ", 0)::bigint"


def _postgres_hltb_main_story() -> str:
    val = "hltb_metadata ->> 'main_story'"
    return (
        f"CASE WHEN hltb_metadata IS NOT NULL AND hltb_metadata ? 'main_story' "
        f"AND ({val}) NOT IN ('null', 'None', '0', '0.0') "
        f"AND ({val}) ~ '^[0-9]+$' "
        f"THEN ({val})::bigint ELSE NULL END"
    )


_POSTGRES_PRIMARY_REGION = f"left(regions ->> 0, {PRIMARY_REGION_LENGTH})"


# ---------------------------------------------------------------------------
# Catalog
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


def steam_fed_columns(pg: bool, *, with_steam: bool) -> list[GeneratedColumn]:
    """The columns 0123 redefined, with or without Steam in their chains."""
    array_expr = _postgres_array_expr if pg else _maria_array_expr
    columns = []
    for name, sources in STEAM_FED_ARRAY_SOURCES.items():
        key = name[len("generated_") :]
        chain = sources + [STEAM_METADATA_COLUMN] if with_steam else sources
        columns.append(
            GeneratedColumn(name, "JSONB" if pg else "JSON", array_expr(key, chain))
        )

    date_expr = _postgres_first_release_date if pg else _maria_first_release_date
    release_date = GeneratedColumn(
        "generated_first_release_date", "BIGINT", date_expr(with_steam)
    )

    rating_expr = _postgres_rating if pg else _maria_rating
    rating_sources = _RATING_SOURCES + ([_STEAM_RATING] if with_steam else [])
    ratings = [rating_expr(src, key, mult) for src, key, mult in rating_sources]
    average_rating = GeneratedColumn(
        "generated_average_rating",
        "DOUBLE PRECISION" if pg else "DOUBLE",
        _average_expr(ratings),
    )

    # A flag repeats its value's expression, so `_reads_steam` finds Steam in
    # both and the pair is always rebuilt together.
    columns += [release_date, release_date.unset_flag]
    columns += [average_rating, average_rating.unset_flag]
    return columns


def generated_columns(pg: bool) -> list[GeneratedColumn]:
    """Every generated column in the catalog, at its current definition."""
    array_expr = _postgres_array_expr if pg else _maria_array_expr
    hltb_main_story = GeneratedColumn(
        HLTB_MAIN_STORY_COLUMN,
        "BIGINT",
        _postgres_hltb_main_story() if pg else _maria_hltb_main_story(),
    )
    return [
        GeneratedColumn(
            PRIMARY_REGION_COLUMN,
            f"VARCHAR({PRIMARY_REGION_LENGTH})",
            _POSTGRES_PRIMARY_REGION if pg else _MARIA_PRIMARY_REGION,
        ),
        *steam_fed_columns(pg, with_steam=True),
        *[
            GeneratedColumn(
                name, "JSONB" if pg else "JSON", array_expr(key, _IGDB_SOURCES)
            )
            for name, key in TAG_COLUMNS
        ],
        GeneratedColumn(
            RATING_COUNT_COLUMN,
            "BIGINT",
            _postgres_rating_count() if pg else _maria_rating_count(),
        ),
        hltb_main_story,
        hltb_main_story.unset_flag,
    ]


def _save_target_layout_type() -> ENUM:
    """The PostgreSQL type behind `save_target_layout`, which the other engines inline."""
    return ENUM(
        *SAVE_TARGET_LAYOUT_VALUES, name=SAVE_TARGET_LAYOUT_ENUM, create_type=False
    )


def drop_save_target_layout_type(conn: sa.Connection) -> None:
    if is_postgresql(conn):
        _save_target_layout_type().drop(conn, checkfirst=True)


# The stored columns in the catalog, minus `full_path_hash`.
PLAIN_COLUMNS = [
    sa.Column("is_physical", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("upc", sa.String(length=64)),
    sa.Column("locked_fields", CustomJSON()),
    sa.Column("demozoo_id", sa.Integer()),
    sa.Column("pouet_id", sa.Integer()),
    sa.Column("csdb_id", sa.Integer()),
    sa.Column("demozoo_metadata", CustomJSON()),
    sa.Column("pouet_metadata", CustomJSON()),
    sa.Column("csdb_metadata", CustomJSON()),
    sa.Column("steam_id", sa.Integer()),
    sa.Column(STEAM_METADATA_COLUMN, CustomJSON()),
    sa.Column("title_id", sa.String(length=TITLE_ID_MAX_LENGTH)),
    sa.Column("save_target", sa.String(length=TITLE_ID_MAX_LENGTH)),
    sa.Column(
        SAVE_TARGET_LAYOUT_COLUMN,
        sa.Enum(*SAVE_TARGET_LAYOUT_VALUES, name=SAVE_TARGET_LAYOUT_ENUM),
    ),
]


def _plain_column_ddl(conn: sa.Connection, column: sa.Column) -> str:
    # CreateColumn needs the column bound to a table to render its DDL.
    bound = column._copy()
    sa.Table(TABLE, sa.MetaData(), bound)
    return CreateColumn(bound).compile(dialect=conn.dialect).string


def _full_path_hash_ddl(conn: sa.Connection) -> str:
    """`full_path_hash`, filled for every existing row where the engine allows."""
    # MariaDB evaluates a column-referencing DEFAULT per row during the copy, so
    # 0126 finds the column filled; PostgreSQL and MySQL refuse such a default.
    ddl = f"{FULL_PATH_HASH_COLUMN} VARCHAR({FULL_PATH_HASH_LENGTH})"
    if is_mariadb(conn):
        return f"{ddl} NOT NULL DEFAULT ({full_path_digest_sql(conn)})"
    return ddl


def roms_metadata_view_sql(pg: bool, columns: list[tuple[str, str]]) -> str:
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
        f"CREATE VIEW {VIEW} AS\n"  # nosec B608
        "SELECT\n"
        "    id AS rom_id,\n"
        "    NOW() AS created_at,\n"
        "    NOW() AS updated_at,\n"
        f"    {projections}\n"
        f"FROM {TABLE}"
    )


def _generated_column_indexes(conn: sa.Connection) -> list[tuple[str, list[str], str]]:
    """(name, columns read, indexed expression) for every generated-column index."""
    indexes = [(f"idx_{TABLE}_{c}", [c], c) for c in INDEXED_GENERATED_COLUMNS]
    for column in SORTABLE_NULLABLE_ROM_COLUMNS:
        flag = rom_unset_flag_column(column)
        # Each spans through to `id`, the gallery's tiebreak: without it
        # PostgreSQL sorts every tie, and unset roms are one tie of everything.
        indexes.append(
            (
                rom_sort_index_name(column),
                [flag, column, "id"],
                f"{flag}, {column}, id",
            )
        )
        # MariaDB and MySQL place NULLs last on DESC already, and an index
        # there is ordered the same way. PostgreSQL needs both spelled out.
        if is_postgresql(conn):
            indexes.append(
                (
                    rom_desc_index_name(column),
                    [column, "id"],
                    f"{column} DESC NULLS LAST, id DESC",
                )
            )
    return indexes


def _drop_index_sql(conn: sa.Connection, name: str) -> str:
    """DROP INDEX, which PostgreSQL spells without the table."""
    return f"DROP INDEX {name}" if is_postgresql(conn) else f"DROP INDEX {name} ON {TABLE}"  # fmt: skip


def _restore_generated_indexes(conn: sa.Connection) -> None:
    """Create or re-widen every generated-column index the table is missing.

    Matches on the columns spanned rather than the name: a rebuild drops the
    index on PostgreSQL but narrows it on MariaDB and MySQL.
    """
    existing = {
        index["name"]: tuple(c for c in index["column_names"] if c)
        for index in sa.inspect(conn).get_indexes(TABLE)
    }
    present = column_names(conn, TABLE)
    for name, columns, expression in _generated_column_indexes(conn):
        if not set(columns) <= present or existing.get(name) == tuple(columns):
            continue
        if name in existing:
            conn.execute(sa.text(_drop_index_sql(conn, name)))
        conn.execute(sa.text(f"CREATE INDEX {name} ON {TABLE} ({expression})"))


def _drop_indexes_spanning(conn: sa.Connection, columns: set[str]) -> None:
    """Drop the indexes a DROP COLUMN would otherwise narrow rather than remove."""
    # PostgreSQL drops an index with its column; MariaDB and MySQL keep a
    # composite one over the columns that remain, unique and all.
    if not columns or is_postgresql(conn):
        return
    for index in sa.inspect(conn).get_indexes(TABLE):
        spanned = {name for name in index["column_names"] if name}
        name = index["name"]
        if name and spanned & columns and not spanned <= columns:
            conn.execute(sa.text(_drop_index_sql(conn, name)))


def rebuild_generated_columns(
    conn: sa.Connection,
    *,
    add: list[GeneratedColumn],
    drop: list[str],
    view_columns: list[tuple[str, str]],
) -> None:
    """Swap generated columns in one ALTER TABLE, around the view over them.

    Args:
        add: columns to (re)define; one already present is dropped first.
        drop: columns to remove outright.
        view_columns: what `roms_metadata` projects afterwards.
    """
    pg = is_postgresql(conn)
    present = column_names(conn, TABLE)
    actions = [
        f"DROP COLUMN {name}"
        for name in [column.name for column in add] + drop
        if name in present
    ] + [f"ADD COLUMN {column.ddl}" for column in add]

    _drop_indexes_spanning(conn, {name for name in drop if name in present})
    # The view projects columns being dropped, so it goes first.
    conn.execute(sa.text(f"DROP VIEW IF EXISTS {VIEW}"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE}\n" + ",\n".join(actions)))  # nosec B608
    _restore_generated_indexes(conn)
    conn.execute(sa.text(roms_metadata_view_sql(pg, view_columns)))


def ensure_roms_columns(conn: sa.Connection) -> None:
    """Add every column of this module the table lacks, in one ALTER TABLE."""
    pg = is_postgresql(conn)
    present = {column["name"]: column for column in sa.inspect(conn).get_columns(TABLE)}

    missing_plain = [column for column in PLAIN_COLUMNS if column.name not in present]
    missing_generated = [
        column for column in generated_columns(pg) if column.name not in present
    ]
    # The engine reports a generated column's expression, so a chain that
    # predates 0123 is recognisable by the provider it does not read yet.
    outdated = [
        column
        for column in steam_fed_columns(pg, with_steam=True)
        if column.name in present and not _reads_steam(present[column.name])
    ]

    actions = [f"DROP COLUMN {column.name}" for column in outdated]
    actions += [
        f"ADD COLUMN {_plain_column_ddl(conn, column)}" for column in missing_plain
    ]
    if FULL_PATH_HASH_COLUMN not in present:
        actions.append(f"ADD COLUMN {_full_path_hash_ddl(conn)}")
    actions += [f"ADD COLUMN {column.ddl}" for column in outdated + missing_generated]

    if actions:
        if pg and any(c.name == SAVE_TARGET_LAYOUT_COLUMN for c in missing_plain):
            _save_target_layout_type().create(conn, checkfirst=True)
        # PostgreSQL will not drop a column the view projects.
        if outdated:
            conn.execute(sa.text(f"DROP VIEW IF EXISTS {VIEW}"))
        conn.execute(
            sa.text(f"ALTER TABLE {TABLE}\n" + ",\n".join(actions))
        )  # nosec B608

    # Outside the block above so a replay after a run that died mid-ALTER
    # still indexes the columns it did add.
    _restore_generated_indexes(conn)

    # Outside the block above so a run that died between the ALTER and this
    # statement gets its view back on the replay.
    if not sa.inspect(conn).has_table(VIEW):
        conn.execute(sa.text(roms_metadata_view_sql(pg, ROMS_METADATA_VIEW_COLUMNS)))

    # The digest default only exists to fill the copy; the model has none. A
    # run that died between the two statements finishes here on the replay.
    if has_server_default(conn, FULL_PATH_HASH_COLUMN):
        conn.execute(
            sa.text(
                f"ALTER TABLE {TABLE} ALTER COLUMN {FULL_PATH_HASH_COLUMN} DROP DEFAULT"
            )
        )


def drop_roms_columns(conn: sa.Connection) -> None:
    """Remove every column this module adds, in one ALTER TABLE.

    The reverse of `ensure_roms_columns`, for 0108's downgrade.
    """
    pg = is_postgresql(conn)
    present = {column["name"]: column for column in sa.inspect(conn).get_columns(TABLE)}

    # Generated columns go first: PostgreSQL will not drop a column one reads.
    owned = [
        *[c.name for c in generated_columns(pg) if c.name not in INHERITED_COLUMNS],
        *[c.name for c in PLAIN_COLUMNS],
        FULL_PATH_HASH_COLUMN,
    ]
    drop = [name for name in owned if name in present]
    steam_reading = [
        column
        for column in steam_fed_columns(pg, with_steam=False)
        if column.name in INHERITED_COLUMNS
        and column.name in present
        and _reads_steam(present[column.name])
    ]

    if drop or steam_reading:
        rebuild_generated_columns(
            conn,
            add=steam_reading,
            drop=drop,
            view_columns=[
                projection
                for projection in ROMS_METADATA_VIEW_COLUMNS
                if projection[0] in present and projection[0] not in drop
            ],
        )
    _drop_sort_indexes(conn)
    drop_save_target_layout_type(conn)


def _drop_sort_indexes(conn: sa.Connection) -> None:
    """Remove the sort indexes, which outlive the columns they were added for.

    A descending one reads an inherited column, so nothing above drops it.
    """
    existing = {index["name"] for index in sa.inspect(conn).get_indexes(TABLE)}
    for column in SORTABLE_NULLABLE_ROM_COLUMNS:
        for name in (rom_sort_index_name(column), rom_desc_index_name(column)):
            if name in existing:
                conn.execute(sa.text(_drop_index_sql(conn, name)))


def _reads_steam(column: ReflectedColumn) -> bool:
    """Whether a reflected generated column already has Steam in its chain."""
    # A column the engine did not report as generated counts as not reading
    # Steam, so `ensure_roms_columns` rebuilds it rather than raising.
    computed = column.get("computed") or {}
    return STEAM_METADATA_COLUMN in computed.get("sqltext", "")


def has_server_default(conn: sa.Connection, column: str) -> bool:
    """Whether `column` still has a server default; only MariaDB is ever given one."""
    # information_schema rather than the inspector, which drops an expression
    # default it cannot parse.
    if not is_mariadb(conn):
        return False
    return bool(
        conn.execute(
            sa.text(
                "SELECT COLUMN_DEFAULT IS NOT NULL FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table "
                "AND COLUMN_NAME = :column"
            ),
            {"table": TABLE, "column": column},
        ).scalar()
    )
