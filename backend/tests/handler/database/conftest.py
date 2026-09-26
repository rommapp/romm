"""Dialects for query-shape tests: the suite runs one database at a time, so
each engine's spelling is pinned by compiling for it explicitly."""

from sqlalchemy import ClauseElement
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.engine import Dialect

# Named binds keep the expected SQL identical across dialects.
MARIADB_DIALECT: Dialect = MariaDBDialect(paramstyle="named")
POSTGRESQL_DIALECT: Dialect = postgresql.dialect(paramstyle="named")


def compile_sql(statement: ClauseElement, dialect: Dialect) -> str:
    return str(statement.compile(dialect=dialect))
