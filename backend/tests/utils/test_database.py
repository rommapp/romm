"""Tests for the day-of-year predicate behind `GET /api/roms/anniversaries` (issue #3440).

`generated_first_release_date` is epoch milliseconds, so "8 September in any year" is a
union of one-day ranges rather than a `MONTH()/DAY()` call. Ranges are sargable, which is
the whole point: they let the column's index serve a range scan instead of a scan of every
row. These tests pin the range arithmetic; the endpoint tests pin what it selects.
"""

from datetime import datetime, timezone

import pytest

from utils.database import EARLIEST_RELEASE_YEAR, MS_PER_DAY, day_of_year_ranges


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
