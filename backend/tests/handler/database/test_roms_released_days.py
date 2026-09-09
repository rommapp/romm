"""What the `released_days` filter selects (issue #3440).

The filter means exactly what it says: the days asked for, in every year up to
`released_before_year`. The calendar policy that the Home anniversary widget
layers on top (skipping 1 January, excluding the current year, rolling 29
February onto 28 February) lives in the client, so nothing here reads a clock.
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


def _names(days, before_year: int | None = None) -> list[str]:
    roms = db_rom_handler.get_roms_scalar(
        released_days=days,
        released_before_year=before_year,
        order_by="first_release_date",
    )
    return [rom.name for rom in roms]


class TestMatching:
    def test_matches_the_same_day_across_years(self, platform: Platform):
        _dated_rom(platform, "same_day_1995", date(1995, 9, 8))
        _dated_rom(platform, "same_day_2004", date(2004, 9, 8))
        _dated_rom(platform, "other_day", date(1995, 9, 9))

        assert _names([(9, 8)]) == ["same_day_1995", "same_day_2004"]

    def test_orders_oldest_release_first(self, platform: Platform):
        _dated_rom(platform, "newest", date(2010, 9, 8))
        _dated_rom(platform, "oldest", date(1985, 9, 8))
        _dated_rom(platform, "middle", date(1999, 9, 8))

        assert _names([(9, 8)]) == ["oldest", "middle", "newest"]

    def test_undated_roms_never_match(self, platform: Platform):
        _dated_rom(platform, "undated", None)

        assert _names([(9, 8)]) == []

    def test_no_days_leaves_the_query_alone(self, platform: Platform):
        """An absent filter must not narrow anything, the way every other one behaves."""
        _dated_rom(platform, "dated", date(1995, 9, 8))
        _dated_rom(platform, "undated", None)

        assert sorted(_names([])) == ["dated", "undated"]

    def test_january_first_is_an_ordinary_day_here(self, platform: Platform):
        """The widget skips it, the filter does not: it is not the filter's business."""
        _dated_rom(platform, "year_only", date(1983, 1, 1))

        assert _names([(1, 1)]) == ["year_only"]

    def test_a_day_no_year_has_matches_nothing(self, platform: Platform):
        _dated_rom(platform, "end_of_february", date(1994, 2, 28))

        assert _names([(2, 30)]) == []


class TestMultipleDays:
    def test_matches_the_union_of_the_days(self, platform: Platform):
        """The widget asks for 28 and 29 February together in a non-leap year."""
        _dated_rom(platform, "leap_baby", date(2004, 2, 29))
        _dated_rom(platform, "end_of_february", date(1998, 2, 28))
        _dated_rom(platform, "march", date(1998, 3, 1))

        assert _names([(2, 28), (2, 29)]) == ["end_of_february", "leap_baby"]

    def test_29_february_alone_only_matches_leap_years(self, platform: Platform):
        _dated_rom(platform, "leap_baby", date(2004, 2, 29))
        _dated_rom(platform, "end_of_february", date(1998, 2, 28))

        assert _names([(2, 29)]) == ["leap_baby"]


class TestYearBound:
    def test_the_bound_year_is_excluded(self, platform: Platform):
        """The widget passes its own year, so "today" is never its own anniversary."""
        _dated_rom(platform, "released_this_year", date(2026, 9, 8))
        _dated_rom(platform, "released_before", date(2025, 9, 8))

        assert _names([(9, 8)], before_year=2026) == ["released_before"]

    def test_without_a_bound_every_year_matches(self, platform: Platform):
        _dated_rom(platform, "released_this_year", date(2026, 9, 8))
        _dated_rom(platform, "released_before", date(2025, 9, 8))

        assert _names([(9, 8)]) == ["released_before", "released_this_year"]

    def test_the_year_boundary_does_not_bleed(self, platform: Platform):
        _dated_rom(platform, "new_years_eve", date(1999, 12, 31))
        _dated_rom(platform, "new_years_day", date(2000, 1, 1))

        assert _names([(12, 31)]) == ["new_years_eve"]
        assert _names([(1, 1)]) == ["new_years_day"]
