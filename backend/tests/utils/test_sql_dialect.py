import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mysql, postgresql, sqlite
from tests.handler.database.conftest import MARIADB_DIALECT

from handler.database.base_handler import sync_engine
from utils.sql_dialect import Analyze, NullsLast

_T = sa.table("t", sa.column("v", sa.Integer))


def _order_by_sql(descending: bool, dialect: sa.Dialect) -> str:
    statement = sa.select(_T.c.v).order_by(NullsLast(_T.c.v, descending))
    return str(statement.compile(dialect=dialect)).split("ORDER BY ")[-1]


class TestNullsLastSpelling:
    @pytest.mark.parametrize(
        ("dialect", "descending", "expected"),
        [
            (MARIADB_DIALECT, False, "t.v IS NULL, t.v ASC"),
            (MARIADB_DIALECT, True, "t.v DESC"),
            (mysql.dialect(), False, "t.v IS NULL, t.v ASC"),
            (mysql.dialect(), True, "t.v DESC"),
            (postgresql.dialect(), False, "t.v ASC NULLS LAST"),
            (postgresql.dialect(), True, "t.v DESC NULLS LAST"),
            (sqlite.dialect(), True, "t.v DESC NULLS LAST"),
        ],
    )
    def test_each_engine_gets_its_own_spelling(
        self, dialect: sa.Dialect, descending: bool, expected: str
    ):
        assert _order_by_sql(descending, dialect) == expected

    def test_direction_is_part_of_the_cache_key(self):
        """A shared cache key would replay one direction's SQL for the other."""
        ascending = sa.select(_T.c.v).order_by(NullsLast(_T.c.v, False))
        descending = sa.select(_T.c.v).order_by(NullsLast(_T.c.v, True))

        assert ascending._generate_cache_key() != descending._generate_cache_key()


class TestNullsLastOnTheRunningEngine:
    @pytest.mark.parametrize(
        ("descending", "expected"), [(False, [1, 2, None]), (True, [2, 1, None])]
    )
    def test_nulls_sort_last_in_both_directions(
        self, descending: bool, expected: list[int | None]
    ):
        rows = sa.union_all(
            sa.select(sa.literal(2, sa.Integer).label("v")),
            sa.select(sa.cast(sa.null(), sa.Integer).label("v")),
            sa.select(sa.literal(1, sa.Integer).label("v")),
        ).subquery()
        statement = sa.select(rows.c.v).order_by(NullsLast(rows.c.v, descending))

        with sync_engine.connect() as connection:
            assert list(connection.scalars(statement)) == expected


class TestAnalyze:
    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [
            (MARIADB_DIALECT, "ANALYZE TABLE roms"),
            (mysql.dialect(), "ANALYZE TABLE roms"),
            (postgresql.dialect(), "ANALYZE roms"),
        ],
    )
    def test_each_engine_gets_its_own_spelling(
        self, dialect: sa.Dialect, expected: str
    ):
        assert str(Analyze("roms").compile(dialect=dialect)) == expected

    def test_quotes_a_reserved_name(self):
        assert str(Analyze("order").compile(dialect=postgresql.dialect())) == (
            'ANALYZE "order"'
        )

    def test_runs_on_the_running_engine(self):
        with sync_engine.begin() as connection:
            connection.execute(Analyze("roms"))
