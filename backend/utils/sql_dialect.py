"""SQL that each engine renders in its own spelling.

Query code builds these like any other expression and never branches on the
driver; the per-dialect choice happens when the statement is compiled.
"""

import json
from collections.abc import Callable, Collection, Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy import SQLColumnExpression
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import ClauseElement, ColumnElement, func
from sqlalchemy.sql.compiler import DDLCompiler, SQLCompiler
from sqlalchemy.sql.ddl import ExecutableDDLElement
from sqlalchemy.sql.elements import ClauseList
from sqlalchemy.sql.operators import OperatorType
from sqlalchemy.sql.visitors import InternalTraversal

# A JSON column holding an array: `Mapped[list[str] | None]`, `Mapped[set[int]]`...
type JsonArrayColumn = SQLColumnExpression[Collection[Any] | None]
type JsonArrayValues = Sequence[str] | Sequence[int]


def _compiles_on_mysql_family[F: Callable[..., str]](
    construct: type[ClauseElement],
) -> Callable[[F], F]:
    """Register a compiler for both MySQL and MariaDB.

    `@compiles(..., "mysql")` alone misses MariaDB, whose dialect is named
    `mariadb` even though it inherits MySQL's compiler.
    """

    def decorate(fn: F) -> F:
        return compiles(construct, "mariadb")(compiles(construct, "mysql")(fn))

    return decorate


class DialectCase[T](ColumnElement[T]):
    """`mysql` on MySQL and MariaDB, `postgresql` on every other engine.

    Both branches are built up front so their bind parameters are part of the
    statement's cache key. The construct takes the type of `postgresql`.
    """

    inherit_cache = True
    _traverse_internals = [
        ("postgresql", InternalTraversal.dp_clauseelement),
        ("mysql", InternalTraversal.dp_clauseelement),
    ]

    def __init__(self, *, postgresql: ColumnElement[T], mysql: ClauseElement) -> None:
        self.postgresql = postgresql
        self.mysql = mysql
        self.type = postgresql.type

    # Group and negate each branch on its own terms, so `NOT` or `AND` around
    # an `OR` branch keeps its precedence.
    def self_group(self, against: OperatorType | None = None) -> ColumnElement[T]:
        return DialectCase(
            postgresql=self.postgresql.self_group(against=against),
            mysql=self.mysql.self_group(against=against),
        )

    def _negate(self) -> ColumnElement[T]:
        return DialectCase(
            postgresql=self.postgresql._negate(), mysql=self.mysql._negate()
        )


@compiles(DialectCase)
def _dialect_case_default(
    element: DialectCase[Any], compiler: SQLCompiler, **kw: Any
) -> str:
    return compiler.process(element.postgresql, **kw)


@_compiles_on_mysql_family(DialectCase)
def _dialect_case_mysql(
    element: DialectCase[Any], compiler: SQLCompiler, **kw: Any
) -> str:
    return compiler.process(element.mysql, **kw)


def nulls_last[T](sort_key: SQLColumnExpression[T], descending: bool) -> DialectCase[T]:
    """An ORDER BY term that sorts NULL values of `sort_key` after every other value."""
    directed = sort_key.desc() if descending else sort_key.asc()
    # MySQL and MariaDB have no NULLS LAST. DESC already puts NULLs last there;
    # ASC needs the `IS NULL` term leading.
    return DialectCase(
        # PostgreSQL's `idx_roms_<column>_desc` indexes are declared with exactly
        # this spelling, so the descending sort reads out of them.
        postgresql=directed.nulls_last(),
        mysql=directed if descending else ClauseList(sort_key.is_(None), directed),
    )


def _jsonb(column: JsonArrayColumn) -> ColumnElement[Any]:
    return sa.type_coerce(column, sa_pg.JSONB)


def _jsonb_contains(column: JsonArrayColumn, value: str | int) -> ColumnElement[bool]:
    return _jsonb(column).contains(
        func.cast(sa.literal(value, sa_pg.JSONB), sa_pg.JSONB)
    )


def _jsonb_text_array(values: JsonArrayValues) -> ColumnElement[Any]:
    return sa.type_coerce(values, sa_pg.ARRAY(sa_pg.TEXT))


def json_array_contains_value(
    column: JsonArrayColumn, value: str | int
) -> ColumnElement[bool]:
    """Check if a JSON array column contains the given value."""
    return DialectCase(
        # `?` only matches strings; `@>` handles every other JSON type.
        postgresql=(
            _jsonb(column).has_key(value)
            if isinstance(value, str)
            else _jsonb_contains(column, value)
        ),
        # JSON_CONTAINS takes JSON text, even for a number.
        mysql=func.json_contains(column, json.dumps(value)),
    )


def json_array_contains_any(
    column: JsonArrayColumn, values: JsonArrayValues
) -> ColumnElement[bool]:
    """Check if a JSON array column contains any of the given values."""
    if not values:
        return sa.false()
    if len(values) == 1:
        return json_array_contains_value(column, values[0])

    return DialectCase(
        postgresql=(
            _jsonb(column).has_any(_jsonb_text_array(values))
            if isinstance(values[0], str)
            else sa.or_(*(_jsonb_contains(column, v) for v in values))
        ),
        mysql=func.json_overlaps(column, json.dumps(values)),
    )


def json_array_contains_all(
    column: JsonArrayColumn, values: JsonArrayValues
) -> ColumnElement[bool]:
    """Check if a JSON array column contains all of the given values."""
    if not values:
        return sa.false()

    return DialectCase(
        postgresql=(
            _jsonb(column).has_all(_jsonb_text_array(values))
            if isinstance(values[0], str)
            else sa.and_(*(_jsonb_contains(column, v) for v in values))
        ),
        mysql=func.json_contains(column, json.dumps(values)),
    )


class Analyze(ExecutableDDLElement):
    """Refresh the planner statistics of `table`."""

    def __init__(self, table: str) -> None:
        self.table = table


@compiles(Analyze)
def _analyze_default(element: Analyze, compiler: DDLCompiler, **kw: Any) -> str:
    return f"ANALYZE {compiler.preparer.quote(element.table)}"


@_compiles_on_mysql_family(Analyze)
def _analyze_mysql(element: Analyze, compiler: DDLCompiler, **kw: Any) -> str:
    return f"ANALYZE TABLE {compiler.preparer.quote(element.table)}"
