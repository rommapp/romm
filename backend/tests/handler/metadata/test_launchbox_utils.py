"""Property-based tests for the LaunchBox metadata parsing helpers."""

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from hypothesis import assume, given
from hypothesis import strategies as st

from handler.metadata.launchbox_handler.utils import (
    dedupe_words,
    parse_list,
    parse_release_date,
    sanitize_filename,
)

LB_INVALID_CHARS = set("\\/|<>\"?*:'")


@contextmanager
def local_timezone(name: str) -> Iterator[None]:
    """Pin the process timezone that a naive datetime.timestamp() reads."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


class TestParseList:
    @given(st.text() | st.none())
    def test_elements_are_stripped_and_non_empty(self, value):
        result = parse_list(value)
        assert isinstance(result, list)
        for item in result:
            assert item == item.strip()
            assert item != ""

    @given(st.lists(st.text(alphabet=st.characters(blacklist_characters=";,"))))
    def test_roundtrip_via_semicolon_join(self, items):
        cleaned = [i.strip() for i in items if i.strip()]
        assert parse_list(";".join(cleaned)) == cleaned


class TestDedupeWords:
    @given(st.lists(st.text() | st.none()))
    def test_no_duplicate_lowercased_keys(self, values):
        result = dedupe_words(values)
        keys = [v.lower() for v in result]
        assert len(keys) == len(set(keys))

    @given(st.lists(st.text() | st.none()))
    def test_result_is_subset_of_stripped_inputs(self, values):
        stripped = {v.strip() for v in values if v is not None and v.strip()}
        result = dedupe_words(values)
        for item in result:
            assert item in stripped


class TestParseReleaseDate:
    @given(st.text() | st.none())
    def test_returns_none_or_int(self, value):
        result = parse_release_date(value)
        assert result is None or isinstance(result, int)

    # datetime.isoformat() omits fold, so both occurrences of an ambiguous
    # local time reach the parser as the same string. Only the first occurrence
    # is a satisfiable expectation, which is also what fromisoformat returns.
    @given(
        st.datetimes(
            min_value=datetime(1971, 1, 1),
            max_value=datetime(2100, 1, 1),
        ).map(lambda dt: dt.replace(fold=0))
    )
    def test_valid_iso_dates_parse_to_timestamp(self, dt):
        result = parse_release_date(dt.isoformat())
        assert result == int(dt.timestamp())

    def test_ambiguous_local_time_uses_first_occurrence(self):
        # No local time is ambiguous under the UTC that CI runs in, so the
        # timezone has to be pinned to one that observes DST.
        with local_timezone("America/New_York"):
            first = datetime(1981, 10, 25, 1, 0)
            second = first.replace(fold=1)
            # Fails loudly if the zone above ever stops being ambiguous here,
            # rather than leaving the assertions below trivially true.
            assert int(second.timestamp()) - int(first.timestamp()) == 3600
            assert first.isoformat() == second.isoformat()
            assert parse_release_date(second.isoformat()) == int(first.timestamp())

    @given(st.dates(min_value=datetime(1971, 1, 1).date()))
    def test_date_only_format_parses(self, d):
        result = parse_release_date(d.isoformat())
        expected = int(
            datetime(d.year, d.month, d.day).timestamp(),
        )
        assert result == expected


class TestSanitizeFilename:
    @given(st.text())
    def test_output_contains_no_invalid_characters(self, stem):
        result = sanitize_filename(stem)
        assert not (set(result) & LB_INVALID_CHARS)

    @given(st.text())
    def test_is_idempotent(self, stem):
        once = sanitize_filename(stem)
        assert sanitize_filename(once) == once

    @given(st.text())
    def test_no_leading_or_trailing_space_or_dot(self, stem):
        result = sanitize_filename(stem)
        assume(result != "")
        assert result == result.strip(" .")
