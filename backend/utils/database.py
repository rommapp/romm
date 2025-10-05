import json
from typing import Any, Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement, func


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


def json_array_contains_value(
    column: sa.Column, value: str | int, *, session: Session
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
    column: sa.Column, values: Sequence[str] | Sequence[int], *, session: Session
) -> ColumnElement:
    """Check if a JSON array column contains any of the given values."""
    if not values:
        return sa.false()

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
    column: sa.Column, values: Sequence[Any], *, session: Session
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
