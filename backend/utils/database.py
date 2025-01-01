from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement, func


def CustomJSON(**kwargs: Any) -> sa.JSON:
    """Custom SQLAlchemy JSON type that uses JSONB on PostgreSQL."""
    return sa.JSON(**kwargs).with_variant(sa_pg.JSONB(**kwargs), "postgresql")


def is_postgresql(conn: sa.Connection) -> bool:
    return conn.engine.name == "postgresql"


def json_array_contains_value(
    column: sa.Column, value: Any, *, session: Session
) -> ColumnElement:
    """Check if a JSON array column contains a single value."""
    conn = session.get_bind()
    if is_postgresql(conn):
        return sa.type_coerce(column, sa_pg.JSONB()).has_key(value)
    return func.json_contains(column, value)
