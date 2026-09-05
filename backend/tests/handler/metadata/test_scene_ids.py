"""scene_id_or_none accepts a bare scene id or a pasted production URL."""

from collections.abc import Callable

import pytest

from handler.metadata import scene_id_or_none
from handler.metadata.csdb_handler import extract_csdb_id_from_filename
from handler.metadata.demozoo_handler import extract_demozoo_id_from_filename
from handler.metadata.pouet_handler import (
    extract_pouet_id_from_filename,
    pouet_id_from_location,
)

KINDS = ["demozoo", "pouet", "csdb"]


@pytest.mark.parametrize("kind", KINDS)
def test_bare_id_is_parsed(kind: str) -> None:
    assert scene_id_or_none("108", kind) == 108


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("value", [None, "", "   ", "not-an-id"])
def test_empty_and_unparseable_are_none(value: str | None, kind: str) -> None:
    assert scene_id_or_none(value, kind) is None


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        ("https://demozoo.org/productions/108/", "demozoo", 108),
        ("https://www.pouet.net/prod.php?which=63", "pouet", 63),
        ("https://csdb.dk/release/?id=75330", "csdb", 75330),
    ],
)
def test_production_url_is_parsed(value: str, kind: str, expected: int) -> None:
    assert scene_id_or_none(value, kind) == expected


@pytest.mark.parametrize("kind", KINDS)
def test_non_ascii_digit_is_none(kind: str) -> None:
    """str.isdigit() accepts a superscript that int() rejects."""
    assert scene_id_or_none("²", kind) is None


@pytest.mark.parametrize("kind", KINDS)
def test_absurdly_long_digit_string_is_none(kind: str) -> None:
    """int() refuses to parse past CPython's 4300-digit limit."""
    assert scene_id_or_none("9" * 4400, kind) is None


@pytest.mark.parametrize(
    ("template", "kind"),
    [
        ("https://demozoo.org/productions/{id}/", "demozoo"),
        ("https://www.pouet.net/prod.php?which={id}", "pouet"),
        ("https://csdb.dk/release/?id={id}", "csdb"),
        ("https://csdb.dk/release/{id}", "csdb"),
    ],
)
def test_absurdly_long_digit_string_in_url_is_none(template: str, kind: str) -> None:
    """The URL branch must guard the digit limit the bare branch already guards."""
    assert scene_id_or_none(template.format(id="9" * 4400), kind) is None


@pytest.mark.parametrize(
    ("extract", "tag"),
    [
        (extract_demozoo_id_from_filename, "demozoo"),
        (extract_pouet_id_from_filename, "pouet"),
        (extract_csdb_id_from_filename, "csdb"),
    ],
)
def test_absurdly_long_filename_tag_is_none(
    extract: Callable[[str], int | None], tag: str
) -> None:
    """A scanned filename is untrusted input and reaches int() unauthenticated."""
    assert extract(f"prod ({tag}-{'9' * 4400}).zip") is None


def test_absurdly_long_pouet_location_is_none() -> None:
    assert pouet_id_from_location(f"/prod.php?which={'9' * 4400}") is None
