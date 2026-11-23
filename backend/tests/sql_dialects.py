"""Dialects for query-shape tests: the suite runs one database at a time, so
each engine's spelling is pinned by compiling for it explicitly."""

from typing import Any

from sqlalchemy import ClauseElement
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.dialects.postgresql import psycopg
from sqlalchemy.engine import Dialect

# Named binds keep the expected SQL identical across dialects. PostgreSQL uses
# the production psycopg driver, which adds bind casts psycopg2 does not.
MARIADB_DIALECT: Dialect = MariaDBDialect(paramstyle="named")
POSTGRESQL_DIALECT: Dialect = psycopg.dialect(paramstyle="named")


def compile_sql(
    statement: ClauseElement, dialect: Dialect, **compile_kwargs: Any
) -> str:
    return str(statement.compile(dialect=dialect, compile_kwargs=compile_kwargs))
