"""Per-engine SQL spellings, chosen when the statement compiles."""

import json
from collections.abc import Callable, Collection, Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy import SQLColumnExpression
from sqlalchemy.dialects import mysql as sa_mysql
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import ClauseElement, ColumnElement, func
from sqlalchemy.sql.compiler import DDLCompiler, SQLCompiler
from sqlalchemy.sql.ddl import ExecutableDDLElement
from sqlalchemy.sql.elements import ClauseList
from sqlalchemy.sql.operators import OperatorType, comma_op
from sqlalchemy.sql.selectable import FromClause, Select
from sqlalchemy.sql.visitors import InternalTraversal

# A JSON column holding an array: `Mapped[list[str] | None]`, `Mapped[set[int]]`...
type JsonArrayColumn = SQLColumnExpression[Collection[Any] | None]
type JsonArrayValues = Sequence[str] | Sequence[int]

_MYSQL_FAMILY = ("mysql", "mariadb")


def _compiles_on_mysql_family[F: Callable[..., str]](
    construct: type[ClauseElement],
) -> Callable[[F], F]:
    """Register a compiler for MySQL and MariaDB; `"mysql"` alone misses MariaDB."""

    def decorate(fn: F) -> F:
        for dialect_name in _MYSQL_FAMILY:
            fn = compiles(construct, dialect_name)(fn)
        return fn

    return decorate


class DialectCase[T](ColumnElement[T]):
    """`mysql` on MySQL and MariaDB, `postgresql` elsewhere, typed as `postgresql`."""

    inherit_cache = True
    # Both branches are traversed, so their binds are part of the cache key.
    _traverse_internals = [
        ("postgresql", InternalTraversal.dp_clauseelement),
        ("mysql", InternalTraversal.dp_clauseelement),
    ]

    def __init__(self, *, postgresql: ColumnElement[T], mysql: ClauseElement) -> None:
        self.postgresql = postgresql
        self.mysql = mysql
        self.type = postgresql.type

    # FROM inference and correlation see the tables either branch reads.
    @property
    def _from_objects(self) -> list[FromClause]:
        return [*self.postgresql._from_objects, *self.mysql._from_objects]

    # Group and negate each branch on its own, so `NOT (a OR b)` keeps its parens;
    # a comma list stays flat, since a grouped ORDER BY list is a row value.
    def self_group(self, against: OperatorType | None = None) -> ColumnElement[T]:
        if against is comma_op:
            return self
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


def force_index_on_mysql[S: Select[Any]](
    statement: S, table: FromClause | type[Any], index_name: str
) -> S:
    """Make MySQL and MariaDB read `table` through `index_name`; PostgreSQL plans freely."""
    hint = f"FORCE INDEX ({index_name})"
    for dialect_name in _MYSQL_FAMILY:
        statement = statement.with_hint(table, hint, dialect_name)
    return statement


def fulltext_match(*columns: ColumnElement[Any], boolean_query: str) -> sa_mysql.match:
    """A boolean-mode match over one FULLTEXT index's columns, for a `mysql` branch."""
    return sa_mysql.match(*columns, against=boolean_query).in_boolean_mode()


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
