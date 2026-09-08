"""Which roms count as an anniversary for a given day (issue #3440).

`today` is a parameter rather than a clock read so leap-year behaviour is
pinned to explicit dates instead of drifting with the calendar. The endpoint
tests cover the route; these cover what it selects.
"""

from datetime import date, datetime, timezone

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom


def _dated_rom(platform: Platform, name: str, released: date | None) -> Rom:
    """Seed a rom whose `generated_first_release_date` lands on `released`.

    The generated column is derived from the provider blobs, and IGDB reports
    seconds, so that is what goes in (0098 multiplies it up to milliseconds).
    """
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name,
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    if released is None:
        return rom

    seconds = int(
        datetime(
            released.year, released.month, released.day, tzinfo=timezone.utc
        ).timestamp()
    )
    return db_rom_handler.update_rom(
        rom.id, {"igdb_metadata": {"first_release_date": str(seconds)}}
    )


def _anniversary_names(today: date, month: int | None = None, day: int | None = None):
    query, _ = db_rom_handler.get_roms_query()
    ids = db_rom_handler.get_anniversary_rom_ids(
        query=query, today=today, month=month, day=day, limit=24
    )
    by_id = {rom.id: rom.name for rom in db_rom_handler.get_roms_simple_by_ids(ids)}
    return [by_id[rom_id] for rom_id in ids]


class TestJanuaryFirst:
    """Year-only metadata collapses onto 1 January, so the date means nothing there."""

    def test_january_first_matches_nothing(self, platform: Platform):
        _dated_rom(platform, "year_only", date(1983, 1, 1))

        assert _anniversary_names(date(2026, 1, 1)) == []

    def test_a_january_first_rom_surfaces_on_no_day_at_all(self, platform: Platform):
        _dated_rom(platform, "year_only", date(1983, 1, 1))

        for month, day in ((1, 1), (1, 2), (12, 31), (6, 15)):
            assert _anniversary_names(date(2026, 6, 1), month, day) == []


class TestMatching:
    def test_matches_the_same_day_across_years(self, platform: Platform):
        _dated_rom(platform, "same_day_1995", date(1995, 9, 8))
        _dated_rom(platform, "same_day_2004", date(2004, 9, 8))
        _dated_rom(platform, "other_day", date(1995, 9, 9))

        assert _anniversary_names(date(2026, 9, 8)) == [
            "same_day_1995",
            "same_day_2004",
        ]

    def test_orders_oldest_release_first(self, platform: Platform):
        _dated_rom(platform, "newest", date(2010, 9, 8))
        _dated_rom(platform, "oldest", date(1985, 9, 8))
        _dated_rom(platform, "middle", date(1999, 9, 8))

        assert _anniversary_names(date(2026, 9, 8)) == ["oldest", "middle", "newest"]

    def test_defaults_to_todays_month_and_day(self, platform: Platform):
        _dated_rom(platform, "match", date(1990, 3, 14))

        assert _anniversary_names(date(2026, 3, 14)) == ["match"]
        assert _anniversary_names(date(2026, 3, 15)) == []

    def test_undated_roms_never_match(self, platform: Platform):
        _dated_rom(platform, "undated", None)

        assert _anniversary_names(date(2026, 9, 8)) == []

    def test_the_current_year_is_not_an_anniversary(self, platform: Platform):
        """A game released earlier today is not "N years ago today"."""
        _dated_rom(platform, "released_today", date(2026, 9, 8))
        _dated_rom(platform, "released_before", date(2025, 9, 8))

        assert _anniversary_names(date(2026, 9, 8)) == ["released_before"]

    def test_respects_the_limit(self, platform: Platform):
        for year in range(1990, 2000):
            _dated_rom(platform, f"rom_{year}", date(year, 9, 8))

        query, _ = db_rom_handler.get_roms_query()
        ids = db_rom_handler.get_anniversary_rom_ids(
            query=query, today=date(2026, 9, 8), limit=3
        )

        assert len(ids) == 3


class TestYearBoundary:
    def test_new_years_eve_does_not_bleed_into_new_years_day(self, platform: Platform):
        _dated_rom(platform, "new_years_eve", date(1999, 12, 31))

        assert _anniversary_names(date(2026, 12, 31)) == ["new_years_eve"]
        assert _anniversary_names(date(2026, 1, 1)) == []

    def test_a_client_behind_utc_still_excludes_its_own_year(self, platform: Platform):
        """31 December asked for on 1 January UTC belongs to the year just ended."""
        _dated_rom(platform, "released_today", date(2026, 12, 31))
        _dated_rom(platform, "new_years_eve", date(1999, 12, 31))

        assert _anniversary_names(date(2027, 1, 1), 12, 31) == ["new_years_eve"]


class TestLeapDay:
    def test_leap_day_matches_itself_in_a_leap_year(self, platform: Platform):
        _dated_rom(platform, "leap_baby", date(2004, 2, 29))

        assert _anniversary_names(date(2028, 2, 29)) == ["leap_baby"]

    def test_leap_day_does_not_roll_over_in_a_leap_year(self, platform: Platform):
        _dated_rom(platform, "leap_baby", date(2004, 2, 29))

        assert _anniversary_names(date(2028, 2, 28)) == []
        assert _anniversary_names(date(2028, 3, 1)) == []

    def test_leap_day_rolls_onto_february_28_in_a_non_leap_year(
        self, platform: Platform
    ):
        _dated_rom(platform, "leap_baby", date(2004, 2, 29))

        assert _anniversary_names(date(2027, 2, 28)) == ["leap_baby"]

    def test_the_rollover_fires_exactly_once(self, platform: Platform):
        """On 1 March too and it would show twice in the same week."""
        _dated_rom(platform, "leap_baby", date(2004, 2, 29))

        assert _anniversary_names(date(2027, 3, 1)) == []

    def test_the_rollover_keeps_february_28_releases(self, platform: Platform):
        _dated_rom(platform, "leap_baby", date(2004, 2, 29))
        _dated_rom(platform, "end_of_february", date(1998, 2, 28))

        assert _anniversary_names(date(2027, 2, 28)) == [
            "end_of_february",
            "leap_baby",
        ]
