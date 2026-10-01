"""Per-engine SQL spellings, chosen when the statement compiles."""

import json
import re
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


_WHITESPACE_RUN = r"\s+"
_JSON_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def collapse_whitespace(expression: ColumnElement[Any]) -> ColumnElement[str]:
    """`expression` with each run of whitespace turned into one space."""
    return DialectCase(
        postgresql=func.regexp_replace(
            expression, _WHITESPACE_RUN, " ", "g", type_=sa.Text
        ),
        mysql=func.regexp_replace(expression, _WHITESPACE_RUN, " ", type_=sa.Text),
    )


class _JsonTableTitlesHold(ColumnElement[bool]):
    """MySQL/MariaDB: whether a JSON object's `key` array holds `title` once decoded."""

    inherit_cache = True
    _traverse_internals = [
        ("column", InternalTraversal.dp_clauseelement),
        ("key", InternalTraversal.dp_string),
        ("title", InternalTraversal.dp_clauseelement),
        ("pattern", InternalTraversal.dp_clauseelement),
    ]
    type = sa.Boolean()

    def __init__(self, column: SQLColumnExpression[Any], key: str, title: str) -> None:
        self.column = sa.type_coerce(column, sa.JSON())
        self.key = key
        self.title = sa.bindparam(None, title, type_=sa.Text)
        self.pattern = sa.bindparam(None, _WHITESPACE_RUN, type_=sa.Text)


@_compiles_on_mysql_family(_JsonTableTitlesHold)
def _json_table_titles_hold_mysql(
    element: _JsonTableTitlesHold, compiler: SQLCompiler, **kw: Any
) -> str:
    column = compiler.process(element.column, **kw)
    title = compiler.process(element.title, **kw)
    pattern = compiler.process(element.pattern, **kw)
    # JSON_TABLE decodes `\uXXXX` escapes, which LOWER on the raw text can't
    # fold. Both sides take one explicit collation, so neither side's default wins.
    folded = f"REGEXP_REPLACE(LOWER(titles.title), {pattern}, ' ')"
    # Every interpolation is a compiled bind or a key checked against _JSON_KEY.
    return (
        f"EXISTS (SELECT 1 FROM JSON_TABLE({column}, '$.{element.key}[*]' "  # nosec B608
        "COLUMNS (title TEXT PATH '$')) AS titles "
        f"WHERE CONVERT({folded} USING utf8mb4) COLLATE utf8mb4_bin "
        f"= CONVERT({title} USING utf8mb4) COLLATE utf8mb4_bin)"
    )


def json_titles_contain_folded(
    column: SQLColumnExpression[Any], key: str, title: str
) -> ColumnElement[bool]:
    """Whether a JSON object's `key` array of titles holds `title`, ignoring case and spacing."""
    # The key lands inside a literal JSON path, so it must be a plain name.
    if not _JSON_KEY.fullmatch(key):
        raise ValueError(f"Not a plain JSON key: {key!r}")
    folded = " ".join(title.split()).lower()
    # jsonb keeps characters decoded, so lowering its text is safe there.
    lowered = sa.cast(
        collapse_whitespace(func.lower(sa.cast(_jsonb(column)[key], sa.Text))),
        sa_pg.JSONB,
    )
    # MariaDB's text keeps `\uXXXX` escapes, whose case LOWER can't fold; an
    # ASCII title can only equal ASCII titles, so only others need JSON_TABLE.
    mysql = (
        func.coalesce(
            func.json_contains(
                collapse_whitespace(func.lower(func.json_extract(column, f"$.{key}"))),
                json.dumps(folded),
            ),
            0,
        )
        if folded.isascii()
        else _JsonTableTitlesHold(column, key, folded)
    )
    return DialectCase(
        postgresql=func.coalesce(_jsonb(lowered).has_key(folded), sa.false()),
        mysql=mysql,
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
