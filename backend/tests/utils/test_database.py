"""Tests for `utils.database`.

The day-of-year predicate behind the `released_days` filter (issue #3440):
`generated_first_release_date` is epoch milliseconds, so "8 September in any year" is a
union of one-day ranges rather than a `MONTH()/DAY()` call. Ranges are sargable, which is
the whole point: they let the column's index serve a range scan instead of a scan of every
row. These tests pin the range arithmetic; the endpoint tests pin what it selects.

The trigger-DDL guard (issue #3932): error 1419 hits every trigger statement, `DROP
TRIGGER IF EXISTS` included, so `alembic/env.py` probes for it before a revision can
half-apply itself.
"""

import inspect
from datetime import datetime, timezone
from unittest.mock import patch

import alembic.command
import pytest
import sqlalchemy as sa

from handler.database.base_handler import sync_engine
from utils.database import (
    BINLOG_TRIGGER_DDL_ERRNO,
    EARLIEST_RELEASE_YEAR,
    LATEST_RELEASE_YEAR,
    MS_PER_DAY,
    alembic_runs_revisions,
    day_of_year_ranges,
    is_binlog_trigger_privilege_error,
    is_mariadb,
    is_mysql,
    release_day_ranges,
    trigger_ddl_is_blocked,
)


def _ms(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


def test_covers_every_year_below_the_bound():
    ranges = day_of_year_ranges(9, 8, before_year=2026)

    assert len(ranges) == 2026 - EARLIEST_RELEASE_YEAR
    assert (_ms(1958, 9, 8), _ms(1958, 9, 9)) in ranges
    assert (_ms(2025, 9, 8), _ms(2025, 9, 9)) in ranges


def test_each_range_spans_exactly_one_day():
    assert all(
        end - start == MS_PER_DAY
        for start, end in day_of_year_ranges(9, 8, before_year=2026)
    )


def test_ranges_are_sorted_ascending():
    """Emitted in key order so the index range scan needs no sort on top of it."""
    ranges = day_of_year_ranges(2, 28, before_year=2026)

    assert ranges == sorted(ranges)


def test_the_bound_year_is_excluded():
    """An anniversary is at least a year old, so the current year is never in the union."""
    ranges = day_of_year_ranges(9, 8, before_year=2026)

    assert (_ms(2026, 9, 8), _ms(2026, 9, 9)) not in ranges
    assert max(end for _, end in ranges) == _ms(2025, 9, 9)


def test_releases_before_the_epoch_get_negative_ranges():
    """Video games predate 1970, and providers report those releases as negative epochs."""
    start, end = day_of_year_ranges(9, 8, before_year=2026)[0]

    assert start < 0
    assert end < 0


def test_the_year_boundary_does_not_bleed():
    """31 December's ranges must stop before 1 January, and vice versa."""
    dec = dict(day_of_year_ranges(12, 31, before_year=2026))
    jan = dict(day_of_year_ranges(1, 1, before_year=2026))

    assert dec[_ms(1999, 12, 31)] == _ms(2000, 1, 1)
    assert _ms(2000, 1, 1) in jan
    assert not set(dec) & set(jan)


def test_29_february_only_matches_leap_years():
    starts = {start for start, _ in day_of_year_ranges(2, 29, before_year=2026)}

    assert _ms(2024, 2, 29) in starts
    assert _ms(2023, 2, 28) not in starts
    assert len(starts) == len(range(1960, 2025, 4))


@pytest.mark.parametrize(("month", "day"), [(2, 30), (4, 31), (6, 31)])
def test_a_day_no_year_has_yields_no_ranges(month: int, day: int):
    assert day_of_year_ranges(month, day, before_year=2026) == []


class TestReleaseDayRanges:
    """The union the filter hands to the index, over one or more days."""

    def test_covers_the_union_of_the_days(self):
        ranges = release_day_ranges([(2, 29), (2, 28)], before_year=2026)

        assert set(ranges) == set(day_of_year_ranges(2, 28, before_year=2026)) | set(
            day_of_year_ranges(2, 29, before_year=2026)
        )

    def test_a_single_day_matches_the_underlying_ranges(self):
        assert release_day_ranges([(9, 8)], before_year=2026) == day_of_year_ranges(
            9, 8, before_year=2026
        )

    def test_no_days_yields_no_ranges(self):
        assert release_day_ranges([], before_year=2026) == []

    def test_an_unbounded_caller_still_gets_a_finite_union(self):
        """`epoch_ms_in_ranges` cannot express "any year", so the bound is capped."""
        ranges = release_day_ranges([(9, 8)])

        assert len(ranges) == LATEST_RELEASE_YEAR - EARLIEST_RELEASE_YEAR
        assert max(end for _, end in ranges) == _ms(LATEST_RELEASE_YEAR - 1, 9, 9)


class _DriverError(Exception):
    """A driver exception carrying the code as an attribute, as both drivers do."""

    def __init__(self, errno: int):
        # Only the message in `args`, the shape mariadbconnector raises, so the
        # attribute is the only thing an assertion here can be reading.
        super().__init__("denied")
        self.errno = errno


def _denial(orig: Exception) -> sa.exc.DatabaseError:
    return sa.exc.DatabaseError("DROP TRIGGER IF EXISTS t", None, orig)


class TestBinlogTriggerGuard:
    def test_reads_the_code_through_the_sqlalchemy_wrapper(self):
        assert is_binlog_trigger_privilege_error(
            _denial(_DriverError(BINLOG_TRIGGER_DDL_ERRNO))
        )

    def test_falls_back_to_the_first_exception_argument(self):
        """mysqlconnector spells the code in `args` instead."""
        assert is_binlog_trigger_privilege_error(
            _denial(Exception(BINLOG_TRIGGER_DDL_ERRNO, "denied"))
        )

    def test_leaves_every_other_database_error_alone(self):
        assert not is_binlog_trigger_privilege_error(_denial(_DriverError(1045)))

    def test_an_exception_without_a_code_is_not_a_denial(self):
        assert not is_binlog_trigger_privilege_error(RuntimeError("boom"))

    def test_a_server_that_allows_triggers_is_not_blocked(self):
        with sync_engine.connect() as conn:
            if not (is_mysql(conn) or is_mariadb(conn)):
                pytest.skip("only MariaDB and MySQL deny trigger DDL")

            assert not trigger_ddl_is_blocked(conn)

    def test_a_denied_probe_leaves_the_connection_usable(self):
        """The probe runs before the migrations, so it must not poison the session."""
        with sync_engine.connect() as conn:
            if not (is_mysql(conn) or is_mariadb(conn)):
                pytest.skip("only MariaDB and MySQL deny trigger DDL")

            denial = _denial(_DriverError(BINLOG_TRIGGER_DDL_ERRNO))
            with patch.object(type(conn), "exec_driver_sql", side_effect=denial):
                assert trigger_ddl_is_blocked(conn)

            assert conn.scalar(sa.text("SELECT 1")) == 1


class TestRevisionCommandGate:
    """`command` is alembic's per-command `fn` name, not the CLI subcommand."""

    @pytest.mark.parametrize("command", ["do_stamp", "display_version"])
    def test_a_command_that_emits_no_ddl_skips_the_probe(self, command: str):
        """Blocking `stamp` would take away the operator's own way out."""
        assert not alembic_runs_revisions(command, pending=True)

    def test_an_upgrade_with_nothing_left_to_apply_skips_the_probe(self):
        assert not alembic_runs_revisions("upgrade", pending=False)

    def test_an_upgrade_with_pending_revisions_probes(self):
        assert alembic_runs_revisions("upgrade", pending=True)

    def test_a_downgrade_probes_even_at_head(self):
        """`pending` is False at head, yet a downgrade still runs DROP TRIGGER."""
        assert alembic_runs_revisions("downgrade", pending=False)

    def test_alembic_still_names_the_closure_this_gate_matches(self):
        """A rename upstream would turn the pre-flight off without a word."""
        assert "def upgrade(rev, context)" in inspect.getsource(alembic.command.upgrade)
