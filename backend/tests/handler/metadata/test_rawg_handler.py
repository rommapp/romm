from unittest.mock import patch

import pytest

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.metadata.rawg_handler import (
    SLUG_TO_RAWG_SLUG,
    RAWGHandler,
    extract_metadata_from_rawg_rom,
)


@pytest.fixture
def rawg_handler() -> RAWGHandler:
    return RAWGHandler()


def test_is_disabled_without_a_key(rawg_handler):
    with patch("handler.metadata.rawg_handler.RAWG_API_KEY", None):
        assert rawg_handler.is_enabled() is False

    with patch("handler.metadata.rawg_handler.RAWG_API_KEY", "some-key"):
        assert rawg_handler.is_enabled() is True


@pytest.mark.asyncio
async def test_get_rom_returns_a_fallback_when_disabled(rawg_handler):
    with patch("handler.metadata.rawg_handler.RAWG_API_KEY", None):
        rom = await rawg_handler.get_rom("Chrono Trigger (USA).sfc", "snes")

    assert rom["rawg_id"] is None


@pytest.mark.asyncio
async def test_get_rom_returns_a_fallback_without_a_platform(rawg_handler):
    """An unmapped platform must not widen into a search across every platform."""
    with patch("handler.metadata.rawg_handler.RAWG_API_KEY", "some-key"):
        rom = await rawg_handler.get_rom("Chrono Trigger (USA).sfc", "")

    assert rom["rawg_id"] is None


@pytest.mark.parametrize(
    ("slug", "expected"),
    [("snes", "snes"), ("psx", "playstation1"), ("SNES", "snes")],
)
def test_get_platform_maps_known_slugs(rawg_handler, slug: str, expected: str):
    assert rawg_handler.get_platform(slug)["rawg_slug"] == expected


def test_get_platform_returns_none_for_an_unmapped_slug(rawg_handler):
    """RAWG is thin on retro, so returning None beats guessing a near neighbour."""
    platform = rawg_handler.get_platform("neo-geo-pocket-color")

    assert platform["rawg_slug"] is None
    assert platform["slug"] == "neo-geo-pocket-color"


def test_every_mapped_platform_is_a_real_universal_slug():
    """A typo here maps a platform nobody can reach, and it fails silently."""
    for slug in SLUG_TO_RAWG_SLUG:
        assert isinstance(slug, UPS)


@pytest.mark.parametrize(
    ("fs_name", "expected"),
    [
        ("Game (rawg-12345).sfc", 12345),
        ("Game (RAWG-99).sfc", 99),
        ("Game (USA).sfc", None),
    ],
)
def test_extract_rawg_id_from_filename(
    rawg_handler, fs_name: str, expected: int | None
):
    assert rawg_handler.extract_rawg_id_from_filename(fs_name) == expected


def test_extract_metadata_handles_a_sparse_response():
    """RAWG omits fields freely: `esrb_rating` is null for most retro titles."""
    metadata = extract_metadata_from_rawg_rom(
        {"rating": 4.5, "genres": [{"name": "RPG"}], "esrb_rating": None}
    )

    assert metadata["rawg_score"] == "4.5"
    assert metadata["genres"] == ["RPG"]
    assert metadata["esrb_rating"] == ""
    assert metadata["developers"] == []
    assert metadata["publishers"] == []


def test_extract_metadata_of_an_empty_response():
    metadata = extract_metadata_from_rawg_rom({})

    assert metadata["genres"] == []
    assert metadata["first_release_date"] is None
