import pytest

from models.platform import PLATFORM_MATCH_FIELDS, Platform


def _platform(**fields: object) -> Platform:
    return Platform(slug="test", fs_slug="test", name="Test", **fields)


@pytest.mark.parametrize("field", PLATFORM_MATCH_FIELDS)
def test_any_match_field_identifies_the_platform(field: str):
    value = "match" if field.endswith("_slug") else 1

    platform = _platform(**{field: value})

    assert platform.is_identified is True
    assert platform.is_unidentified is False


def test_platform_without_matches_is_unidentified():
    assert _platform().is_unidentified is True


def test_artwork_only_sgdb_does_not_identify_the_platform():
    assert _platform(sgdb_id=1).is_unidentified is True
