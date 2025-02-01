from typing import Any

import json
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement, func


def CustomJSON(**kwargs: Any) -> sa.JSON:
    """Custom SQLAlchemy JSON type that uses JSONB on PostgreSQL."""
    return sa.JSON(**kwargs).with_variant(sa_pg.JSONB(**kwargs), "postgresql")


def is_postgresql(conn: sa.Connection) -> bool:
    return conn.engine.name == "postgresql"


def is_mysql(conn: sa.Connection) -> bool:
    return conn.engine.name == "mysql"


def json_array_contains_value(
    column: sa.Column, value: Any, *, session: Session
) -> ColumnElement:
    """Check if a JSON array column contains a single value."""
    conn = session.get_bind()
    if is_postgresql(conn):
        # In PostgreSQL, string values can be checked for containment using the `?` operator.
        # For other types, we use the `@>` operator.
        if isinstance(value, str):
            return sa.type_coerce(column, sa_pg.JSONB).has_key(value)
        return sa.type_coerce(column, sa_pg.JSONB).contains(
            func.cast(value, sa_pg.JSONB)
        )
    elif is_mysql(conn):
        # In MySQL, JSON.contains() requires a JSON-formatted string (even if it's an int)
        return func.json_contains(column, json.dumps(value))
    return func.json_contains(column, value)


def safe_float(value, default=0.0):
    """Safely convert a value to float, returning default if conversion fails."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """Safely convert a value to int, returning default if conversion fails."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
