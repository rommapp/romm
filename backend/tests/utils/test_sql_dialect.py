from collections.abc import Callable, Iterator

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mysql, sqlite
from tests.sql_dialects import (
    MARIADB_DIALECT,
    POSTGRESQL_DIALECT,
    compile_sql,
)

from handler.database.base_handler import sync_engine
from utils.database import CustomJSON
from utils.sql_dialect import (
    Analyze,
    DialectCase,
    JsonArrayColumn,
    json_array_contains_all,
    json_array_contains_any,
    json_array_contains_value,
    nulls_last,
)

_T = sa.table("t", sa.column("v", sa.Integer), sa.column("tags", CustomJSON()))


def _where_sql(condition: sa.ColumnElement[bool], dialect: sa.Dialect) -> str:
    return compile_sql(sa.select(_T.c.v).where(condition), dialect).split("WHERE ")[-1]


def _order_by_sql(descending: bool, dialect: sa.Dialect) -> str:
    statement = sa.select(_T.c.v).order_by(nulls_last(_T.c.v, descending))
    return compile_sql(statement, dialect).split("ORDER BY ")[-1]


class TestDialectCase:
    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [
            (MARIADB_DIALECT, "t.v IS NOT NULL"),
            (mysql.dialect(), "t.v IS NOT NULL"),
            (POSTGRESQL_DIALECT, "t.v IS NULL"),
            (sqlite.dialect(), "t.v IS NULL"),
        ],
    )
    def test_picks_the_branch_for_the_engine(self, dialect: sa.Dialect, expected: str):
        case = DialectCase(postgresql=_T.c.v.is_(None), mysql=_T.c.v.is_not(None))

        assert _where_sql(case, dialect) == expected

    def test_an_or_branch_keeps_its_precedence_under_not_and_and(self):
        case = DialectCase(
            postgresql=sa.or_(_T.c.v == 1, _T.c.v == 2), mysql=_T.c.v == 3
        )

        assert _where_sql(sa.and_(~case, _T.c.v != 4), POSTGRESQL_DIALECT) == (
            "NOT (t.v = :v_1::INTEGER OR t.v = :v_2::INTEGER) AND t.v != :v_3::INTEGER"
        )

    def test_both_branches_bind_parameters_follow_the_cache(self):
        """A cached compile must pick up each execution's own values."""
        with sync_engine.connect() as connection:
            for value in (1, 2):
                case = DialectCase(
                    postgresql=sa.literal(value), mysql=sa.literal(value)
                )
                assert connection.scalar(sa.select(case)) == value

    def test_from_inference_sees_the_tables_a_branch_reads(self):
        case = DialectCase(postgresql=_T.c.v.is_(None), mysql=_T.c.v.is_not(None))

        assert "FROM t" in compile_sql(
            sa.select(sa.literal(1)).where(case), MARIADB_DIALECT
        )


class TestNullsLastSpelling:
    @pytest.mark.parametrize(
        ("dialect", "descending", "expected"),
        [
            (MARIADB_DIALECT, False, "t.v IS NULL, t.v ASC"),
            (MARIADB_DIALECT, True, "t.v DESC"),
            (mysql.dialect(), False, "t.v IS NULL, t.v ASC"),
            (mysql.dialect(), True, "t.v DESC"),
            (POSTGRESQL_DIALECT, False, "t.v ASC NULLS LAST"),
            (POSTGRESQL_DIALECT, True, "t.v DESC NULLS LAST"),
            (sqlite.dialect(), True, "t.v DESC NULLS LAST"),
        ],
    )
    def test_each_engine_gets_its_own_spelling(
        self, dialect: sa.Dialect, descending: bool, expected: str
    ):
        assert _order_by_sql(descending, dialect) == expected

    def test_stays_unparenthesised_inside_a_multi_term_branch(self):
        """`(t.v IS NULL, t.v ASC)` would be a row value MariaDB cannot parse."""
        ranked: DialectCase[int] = DialectCase(
            postgresql=_T.c.v.asc(),
            mysql=sa.ClauseList(nulls_last(_T.c.v, False), _T.c.tags.desc()),
        )
        statement = sa.select(_T.c.v).order_by(ranked)

        assert compile_sql(statement, MARIADB_DIALECT).split("ORDER BY ")[-1] == (
            "t.v IS NULL, t.v ASC, t.tags DESC"
        )

    def test_direction_is_part_of_the_cache_key(self):
        """A shared cache key would replay one direction's SQL for the other."""
        ascending = sa.select(_T.c.v).order_by(nulls_last(_T.c.v, False))
        descending = sa.select(_T.c.v).order_by(nulls_last(_T.c.v, True))

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
        statement = sa.select(rows.c.v).order_by(nulls_last(rows.c.v, descending))

        with sync_engine.connect() as connection:
            assert list(connection.scalars(statement)) == expected


class TestJsonArrayContainsSpelling:
    @pytest.mark.parametrize(
        ("condition", "mariadb", "postgres"),
        [
            (
                json_array_contains_value(_T.c.tags, "rpg"),
                "json_contains(t.tags, :json_contains_1)",
                "t.tags ? :param_1::VARCHAR",
            ),
            (
                json_array_contains_any(_T.c.tags, ["rpg", "puzzle"]),
                "json_overlaps(t.tags, :json_overlaps_1)",
                "t.tags ?| :param_1::TEXT[]",
            ),
            (
                json_array_contains_all(_T.c.tags, ["rpg", "puzzle"]),
                "json_contains(t.tags, :json_contains_1)",
                "t.tags ?& :param_1::TEXT[]",
            ),
        ],
    )
    def test_each_engine_gets_its_own_operator(
        self, condition: sa.ColumnElement[bool], mariadb: str, postgres: str
    ):
        assert _where_sql(condition, MARIADB_DIALECT).startswith(mariadb)
        assert _where_sql(condition, POSTGRESQL_DIALECT) == postgres

    def test_no_values_match_nothing(self):
        assert (
            _where_sql(json_array_contains_any(_T.c.tags, []), POSTGRESQL_DIALECT)
            == "false"
        )


class TestJsonArrayContainsOnTheRunningEngine:
    @pytest.fixture
    def tagged(self) -> Iterator[sa.Table]:
        table = sa.Table(
            "sql_dialect_tagged",
            sa.MetaData(),
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tags", CustomJSON()),
        )
        with sync_engine.begin() as connection:
            # An interrupted run can leave the table behind in the shared test DB.
            table.drop(connection, checkfirst=True)
            table.create(connection)
            connection.execute(
                table.insert(),
                [
                    {"id": 1, "tags": ["rpg", "puzzle"]},
                    {"id": 2, "tags": ["rpg"]},
                    {"id": 3, "tags": [7, 9]},
                ],
            )
        yield table
        with sync_engine.begin() as connection:
            table.drop(connection)

    @pytest.mark.parametrize(
        ("build", "expected"),
        [
            (lambda c: json_array_contains_value(c, "puzzle"), [1]),
            (lambda c: json_array_contains_value(c, 9), [3]),
            (lambda c: json_array_contains_any(c, ["puzzle", "rpg"]), [1, 2]),
            (lambda c: json_array_contains_any(c, [8, 9]), [3]),
            (lambda c: json_array_contains_all(c, ["puzzle", "rpg"]), [1]),
            (lambda c: json_array_contains_all(c, [7, 9]), [3]),
            (lambda c: ~json_array_contains_any(c, [8, 9]), [1, 2]),
        ],
    )
    def test_matches_the_expected_rows(
        self,
        tagged: sa.Table,
        build: Callable[[JsonArrayColumn], sa.ColumnElement[bool]],
        expected: list[int],
    ):
        statement = (
            sa.select(tagged.c.id).where(build(tagged.c.tags)).order_by(tagged.c.id)
        )

        with sync_engine.connect() as connection:
            assert list(connection.scalars(statement)) == expected


class TestAnalyze:
    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [
            (MARIADB_DIALECT, "ANALYZE TABLE roms"),
            (mysql.dialect(), "ANALYZE TABLE roms"),
            (POSTGRESQL_DIALECT, "ANALYZE roms"),
        ],
    )
    def test_each_engine_gets_its_own_spelling(
        self, dialect: sa.Dialect, expected: str
    ):
        assert str(Analyze("roms").compile(dialect=dialect)) == expected

    def test_quotes_a_reserved_name(self):
        assert str(Analyze("order").compile(dialect=POSTGRESQL_DIALECT)) == (
            'ANALYZE "order"'
        )

    def test_runs_on_the_running_engine(self):
        with sync_engine.begin() as connection:
            connection.execute(Analyze("roms"))
