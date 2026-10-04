from datetime import datetime, timedelta, timezone

import pytest
from tests.timezones import local_timezone

from utils.datetime import format_utc, parse_utc_timestamp, to_utc

# 2005-03-14T00:00:00Z
PI_DAY_2005 = 1110758400


class TestParseUtcTimestamp:
    @pytest.mark.parametrize("value", [None, ""])
    def test_nothing_is_none(self, value: str | None):
        assert parse_utc_timestamp(value, ("%Y-%m-%d",), iso=True) is None

    @pytest.mark.parametrize("zone", ["America/Los_Angeles", "Asia/Tokyo", "UTC"])
    def test_a_date_alone_is_midnight_utc_in_any_server_zone(self, zone: str):
        with local_timezone(zone):
            assert parse_utc_timestamp("2005-03-14", ("%Y-%m-%d",)) == PI_DAY_2005

    def test_tries_each_format_in_turn(self):
        formats = ("%d %b, %Y", "%b %d, %Y")

        assert parse_utc_timestamp("Mar 14, 2005", formats) == PI_DAY_2005

    def test_an_offset_parsed_by_the_format_is_kept(self):
        with local_timezone("Asia/Tokyo"):
            result = parse_utc_timestamp(
                "2005-03-14T09:00:00+0900", ("%Y-%m-%dT%H:%M:%S%z",)
            )

        assert result == PI_DAY_2005

    @pytest.mark.parametrize(
        "value",
        ["2005-03-14", "2005-03-14T00:00:00", "2005-03-14T00:00:00Z"],
    )
    def test_iso_without_an_offset_is_utc(self, value: str):
        with local_timezone("America/Los_Angeles"):
            assert parse_utc_timestamp(value, iso=True) == PI_DAY_2005

    def test_iso_keeps_an_offset(self):
        with local_timezone("America/Los_Angeles"):
            assert (
                parse_utc_timestamp("2005-03-13T19:00:00-05:00", iso=True)
                == PI_DAY_2005
            )

    def test_iso_is_tried_only_when_asked(self):
        # fromisoformat also reads the basic "20050314", which a provider
        # that sends "YYYY-MM-DD" would never mean.
        assert parse_utc_timestamp("20050314", ("%Y-%m-%d",)) is None
        assert parse_utc_timestamp("20050314", iso=True) == PI_DAY_2005

    def test_iso_falls_back_to_the_formats(self):
        assert parse_utc_timestamp("2005", ("%Y",), iso=True) == int(
            datetime(2005, 1, 1, tzinfo=timezone.utc).timestamp()
        )

    @pytest.mark.parametrize("value", ["Coming soon", "Q1 2025", "2005-13-01"])
    def test_an_unreadable_date_is_none(self, value: str):
        assert parse_utc_timestamp(value, ("%Y-%m-%d", "%d %b, %Y"), iso=True) is None

    def test_a_value_that_is_not_text_is_none(self):
        assert parse_utc_timestamp(20050314, ("%Y",), iso=True) is None  # type: ignore[arg-type]


class TestFormatUtc:
    def test_formats_the_utc_date_in_any_server_zone(self):
        with local_timezone("America/Los_Angeles"):
            assert format_utc(PI_DAY_2005 * 1000, "%m-%d-%Y") == "03-14-2005"

    def test_round_trips_a_parsed_date(self):
        timestamp = parse_utc_timestamp("2005-03-14", ("%Y-%m-%d",))
        assert timestamp is not None

        assert format_utc(timestamp * 1000, "%Y-%m-%d") == "2005-03-14"


class TestToUtc:
    def test_a_naive_datetime_is_read_as_utc(self):
        assert to_utc(datetime(2005, 3, 14)) == datetime(
            2005, 3, 14, tzinfo=timezone.utc
        )

    def test_an_aware_datetime_is_converted(self):
        eastern = timezone(timedelta(hours=-5))

        assert to_utc(datetime(2005, 3, 13, 19, tzinfo=eastern)) == datetime(
            2005, 3, 14, tzinfo=timezone.utc
        )
