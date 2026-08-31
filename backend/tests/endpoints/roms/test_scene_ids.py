"""Edit ROM accepts a bare scene id or a pasted production URL."""

import pytest

from endpoints.roms import scene_id_or_none

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
