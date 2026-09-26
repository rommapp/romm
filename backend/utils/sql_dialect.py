"""SQL constructs that each engine renders in its own spelling.

Query code builds these like any other expression and never branches on the
driver; the per-dialect SQL lives in the `@compiles` functions below.
"""

from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import ColumnElement, coercions, roles
from sqlalchemy.sql.compiler import DDLCompiler, SQLCompiler
from sqlalchemy.sql.ddl import ExecutableDDLElement
from sqlalchemy.sql.visitors import InternalTraversal


def _compiles_on_mysql_family(construct: type) -> Callable[[Callable], Callable]:
    """Register a compiler for both MySQL and MariaDB.

    `@compiles(..., "mysql")` alone misses MariaDB, whose dialect is named
    `mariadb` even though it inherits MySQL's compiler.
    """

    def decorate(fn: Callable) -> Callable:
        return compiles(construct, "mariadb")(compiles(construct, "mysql")(fn))

    return decorate


class NullsLast(ColumnElement[Any]):
    """An ORDER BY term that sorts NULL values of `sort_key` after every other value."""

    inherit_cache = True
    _traverse_internals = [
        ("sort_key", InternalTraversal.dp_clauseelement),
        ("descending", InternalTraversal.dp_boolean),
    ]

    def __init__(self, sort_key: Any, descending: bool) -> None:
        self.sort_key = coercions.expect(roles.ExpressionElementRole, sort_key)
        self.descending = descending

    def _directed(self) -> sa.UnaryExpression[Any]:
        return self.sort_key.desc() if self.descending else self.sort_key.asc()


@compiles(NullsLast)
def _nulls_last_default(element: NullsLast, compiler: SQLCompiler, **kw: Any) -> str:
    # PostgreSQL's `idx_roms_<column>_desc` indexes are declared with exactly
    # this spelling, so the descending sort reads out of them.
    return compiler.process(element._directed().nulls_last(), **kw)


@_compiles_on_mysql_family(NullsLast)
def _nulls_last_mysql(element: NullsLast, compiler: SQLCompiler, **kw: Any) -> str:
    # No NULLS LAST syntax. DESC already puts NULLs last; ASC needs the
    # `IS NULL` term leading.
    if element.descending:
        return compiler.process(element._directed(), **kw)
    return (
        f"{compiler.process(element.sort_key.is_(None), **kw)}, "
        f"{compiler.process(element._directed(), **kw)}"
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
