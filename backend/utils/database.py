import json
from datetime import date
from typing import Any, Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement, func

# Single-column foreign keys that MariaDB/MySQL index implicitly but PostgreSQL
# does not, so 0124 creates them there only and no model declares them.
POSTGRESQL_FK_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("collections", "ix_collections_user_id", "user_id"),
    ("smart_collections", "ix_smart_collections_user_id", "user_id"),
    ("rom_notes", "ix_rom_notes_user_id", "user_id"),
    ("firmware", "ix_firmware_platform_id", "platform_id"),
    ("collections_roms", "ix_collections_roms_rom_id", "rom_id"),
    ("music_playlist_tracks", "ix_music_playlist_tracks_rom_file_id", "rom_file_id"),
    ("music_favorite_tracks", "ix_music_favorite_tracks_rom_file_id", "rom_file_id"),
    ("play_sessions", "ix_play_sessions_rom_id", "rom_id"),
    ("play_sessions", "ix_play_sessions_device_id", "device_id"),
    ("play_sessions", "ix_play_sessions_sync_session_id", "sync_session_id"),
    ("saves", "ix_saves_user_id", "user_id"),
    ("states", "ix_states_user_id", "user_id"),
    ("screenshots", "ix_screenshots_user_id", "user_id"),
    ("rom_file_user", "ix_rom_file_user_user_id", "user_id"),
    ("memory_cards", "ix_memory_cards_platform_id", "platform_id"),
    (
        "streaming_container_adoptions",
        "ix_streaming_container_adoptions_decided_by_user_id",
        "decided_by_user_id",
    ),
)

# Indexes that exist in some databases but cannot be declared on a model.
AUTOGENERATE_EXEMPT_INDEX_NAMES = frozenset(
    # Search indexes built per dialect in 0084: FULLTEXT on MySQL/MariaDB,
    # pg_trgm GIN on PostgreSQL. No portable model declaration exists.
    {"idx_roms_name_fs_name_fulltext", "idx_roms_name_trgm", "idx_roms_fs_name_trgm"}
) | frozenset(name for _, name, _ in POSTGRESQL_FK_INDEXES)


def CustomJSON(**kwargs: Any) -> sa.JSON:
    """Custom SQLAlchemy JSON type that uses JSONB on PostgreSQL."""
    return sa.JSON(**kwargs).with_variant(sa_pg.JSONB(**kwargs), "postgresql")


def is_db_version_compatible(
    conn: sa.Connection,
    min_version: tuple[int, ...] | None = None,
) -> bool:
    """Check if the database server version complies with the given version constraints."""
    if min_version is None:
        return True
    server_version = conn.engine.dialect.server_version_info
    return bool(server_version and server_version >= min_version)


def is_postgresql(
    conn: sa.Connection, min_version: tuple[int, ...] | None = None
) -> bool:
    if conn.engine.name != "postgresql":
        return False
    return is_db_version_compatible(conn, min_version=min_version)


def is_mysql(conn: sa.Connection, min_version: tuple[int, ...] | None = None) -> bool:
    if conn.engine.name != "mysql":
        return False
    return is_db_version_compatible(conn, min_version=min_version)


def is_mariadb(conn: sa.Connection, min_version: tuple[int, ...] | None = None) -> bool:
    if conn.engine.name != "mariadb":
        return False
    return is_db_version_compatible(conn, min_version=min_version)


def full_path_digest_sql(conn: sa.Connection) -> str:
    """`models.rom.compute_full_path_hash` spelled in SQL, for 0126's backfill.

    `test_migrations` pins this to the Python function it mirrors.
    """
    if is_postgresql(conn):
        return "encode(sha256(convert_to(fs_path || '/' || fs_name, 'UTF8')), 'hex')"
    return "SHA2(CONCAT(fs_path, '/', fs_name), 256)"


def json_array_contains_value(
    column: sa.Column | Any, value: str | int, *, session: Session
) -> ColumnElement:
    """Check if a JSON array column contains the given value."""
    conn = session.get_bind()
    if is_postgresql(conn):
        # In PostgreSQL, string values can be checked for containment using the `?` operator.
        # For other types, we use the `@>` operator.
        if isinstance(value, str):
            return sa.type_coerce(column, sa_pg.JSONB).has_key(value)
        return sa.type_coerce(column, sa_pg.JSONB).contains(
            func.cast(value, sa_pg.JSONB)
        )
    elif is_mysql(conn) or is_mariadb(conn):
        # In MySQL and MariaDB, JSON_CONTAINS requires a JSON-formatted string (even if it's an int).
        return func.json_contains(column, json.dumps(value))

    raise NotImplementedError(
        f"json_array_contains_value is not implemented for engine: {conn.engine.name}"
    )


def json_array_contains_any(
    column: sa.Column | Any, values: Sequence[str] | Sequence[int], *, session: Session
) -> ColumnElement:
    """Check if a JSON array column contains any of the given values."""
    if not values:
        return sa.false()

    # Optimize for single value case
    if len(values) == 1:
        return json_array_contains_value(column, values[0], session=session)

    conn = session.get_bind()
    if is_postgresql(conn):
        # In PostgreSQL, string arrays can be checked for overlap using the `?|` operator.
        # For other types, we combine element-wise checks with OR.
        if isinstance(values[0], str):
            return sa.type_coerce(column, sa_pg.JSONB).has_any(
                sa.type_coerce(values, sa_pg.ARRAY(sa_pg.TEXT))
            )
        return sa.or_(
            *[json_array_contains_value(column, v, session=session) for v in values]
        )
    elif is_mysql(conn) or is_mariadb(conn, min_version=(10, 9)):
        # In MySQL and MariaDB, JSON_OVERLAPS requires a JSON-formatted string (even if it's an int).
        return func.json_overlaps(column, json.dumps(values))
    elif is_mariadb(conn):
        # MariaDB before 10.9 does not have JSON_OVERLAPS, so we fall back to element-wise checks.
        return sa.or_(
            *[json_array_contains_value(column, v, session=session) for v in values]
        )

    raise NotImplementedError(
        f"json_array_contains_any is not implemented for engine: {conn.engine.name}"
    )


def json_array_contains_all(
    column: sa.Column | Any, values: Sequence[Any], *, session: Session
) -> ColumnElement:
    """Check if a JSON array column contains all of the given values."""
    if not values:
        return sa.false()

    conn = session.get_bind()
    if is_postgresql(conn):
        # In PostgreSQL, string arrays can be checked for containment using the `?&` operator.
        # For other types, we combine element-wise checks with AND.
        if isinstance(values[0], str):
            return sa.type_coerce(column, sa_pg.JSONB).has_all(
                sa.type_coerce(values, sa_pg.ARRAY(sa_pg.TEXT))
            )
        return sa.and_(
            *[json_array_contains_value(column, v, session=session) for v in values]
        )
    elif is_mysql(conn) or is_mariadb(conn):
        # In MySQL and MariaDB, JSON_CONTAINS requires a JSON-formatted string (even if it's an int).
        return func.json_contains(column, json.dumps(values))

    raise NotImplementedError(
        f"json_array_contains_all is not implemented for engine: {conn.engine.name}"
    )


MS_PER_DAY = 86_400_000

# Tennis for Two (1958) predates the epoch, so the oldest ranges are negative.
EARLIEST_RELEASE_YEAR = 1958

# The range union has to be finite, so "any year" stops here.
LATEST_RELEASE_YEAR = 2100

_EPOCH = date(1970, 1, 1)


def day_of_year_ranges(
    month: int, day: int, *, before_year: int
) -> list[tuple[int, int]]:
    """Half-open epoch-millisecond ranges covering (month, day) in each earlier year.

    Ranges rather than `MONTH()/DAY()` on the value, because they are sargable
    and emit no SQL date function, so every dialect plans them the same way.

    Args:
        month: Calendar month, 1-12.
        day: Day of the month, 1-31.
        before_year: Exclusive upper bound on the years covered.

    Returns:
        Ascending (start, end) pairs, skipping years the date does not exist in,
        so an impossible date yields none at all.
    """
    ranges: list[tuple[int, int]] = []
    for year in range(EARLIEST_RELEASE_YEAR, before_year):
        try:
            start = (date(year, month, day) - _EPOCH).days * MS_PER_DAY
        except ValueError:
            continue
        ranges.append((start, start + MS_PER_DAY))

    return ranges


def release_day_ranges(
    days: Sequence[tuple[int, int]], *, before_year: int | None = None
) -> list[tuple[int, int]]:
    """Epoch-millisecond ranges covering every day in `days`, in every year.

    Args:
        days: (month, day) pairs to match.
        before_year: Exclusive upper bound on the years covered, defaulting to
            `LATEST_RELEASE_YEAR`.

    Returns:
        (start, end) pairs, skipping years a date does not exist in.
    """
    bound = LATEST_RELEASE_YEAR if before_year is None else before_year

    return [
        day_range
        for month, day in days
        for day_range in day_of_year_ranges(month, day, before_year=bound)
    ]


def epoch_ms_in_ranges(
    column: sa.Column | Any, ranges: Sequence[tuple[int, int]]
) -> ColumnElement:
    """Match an epoch-millisecond column against any of the given half-open ranges."""
    if not ranges:
        return sa.false()

    return sa.or_(
        *[sa.and_(column >= start, column < end) for start, end in sorted(ranges)]
    )


LIKE_ESCAPE_CHAR = "\\"


def escape_like(term: str) -> str:
    """Escape LIKE wildcards so a search term matches literally (pass escape=LIKE_ESCAPE_CHAR to like())."""
    return (
        term.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{LIKE_ESCAPE_CHAR}%")
        .replace("_", f"{LIKE_ESCAPE_CHAR}_")
    )


def safe_str_to_bool(value: Any, default: bool = False) -> bool:
    """Safely convert a value to bool, returning default if conversion fails."""
    try:
        return value.strip().lower() in ("1", "true", "yes", "on")
    except (ValueError, TypeError, AttributeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default if conversion fails."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int, returning default if conversion fails."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
