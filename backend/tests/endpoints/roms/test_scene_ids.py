"""Edit ROM accepts a bare scene id or a pasted production URL."""

import pytest

from endpoints.roms import scene_id_or_none


@pytest.mark.parametrize("kind", ["demozoo", "pouet", "csdb"])
def test_bare_id_is_parsed(kind: str) -> None:
    assert scene_id_or_none("108", kind) == 108


@pytest.mark.parametrize("kind", ["demozoo", "pouet", "csdb"])
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


@pytest.mark.parametrize("kind", ["demozoo", "pouet", "csdb"])
@pytest.mark.parametrize("value", ["²", "١٢٣" + "9" * 4400])
def test_non_ascii_digits_do_not_raise(value: str, kind: str) -> None:
    """str.isdigit() accepts digits int() rejects; the endpoint must not 500."""
    assert scene_id_or_none(value, kind) is None
