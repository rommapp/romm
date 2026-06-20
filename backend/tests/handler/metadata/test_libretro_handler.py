"""Tests for the libretro thumbnails metadata handler."""

import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.libretro_thumbnails import LibretroThumbnailsService
from adapters.services.libretro_thumbnails_types import LibretroArtType
from config.config_manager import MetadataMediaType
from handler.metadata.libretro_handler import (
    LIBRETRO_PLATFORM_LIST,
    LibretroHandler,
    _strip_paren_tags,
    libretro_id_for,
)

# Sample directory listing for Sony - PlayStation
PSX_LISTING = [
    "Castlevania - Symphony of the Night (USA).png",
    "Castlevania - Symphony of the Night (Europe).png",
    "Castlevania - Symphony of the Night (Japan).png",
    "Final Fantasy VII (USA).png",
    "Final Fantasy VII (Europe).png",
    "Metal Gear Solid (USA).png",
    "Sonic _ Knuckles Collection (USA).png",
]


@pytest.fixture
def handler() -> LibretroHandler:
    return LibretroHandler()


# ---------------------------------------------------------------------------
# Pure utilities
# ---------------------------------------------------------------------------


def test_strip_paren_tags_removes_single_tag():
    assert _strip_paren_tags("Foo (USA)") == "Foo"


def test_strip_paren_tags_removes_multiple_tags():
    assert _strip_paren_tags("Foo (USA) (Rev 1)") == "Foo"


def test_strip_paren_tags_preserves_when_no_tags():
    assert _strip_paren_tags("Foo") == "Foo"


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------


def test_get_platform_supported_platform(handler: LibretroHandler):
    # PSX is explicitly mapped to "Sony - PlayStation"
    assert handler.get_platform("psx")["libretro_slug"] == "Sony - PlayStation"


def test_get_platform_unsupported_platform(handler: LibretroHandler):
    assert handler.get_platform("not-a-real-platform")["libretro_slug"] is None


def test_platform_list_uses_ups_keys():
    """Every entry in LIBRETRO_PLATFORM_LIST should be a UniversalPlatformSlug."""
    from handler.metadata.base_handler import UniversalPlatformSlug

    for key in LIBRETRO_PLATFORM_LIST.keys():
        assert isinstance(key, UniversalPlatformSlug)


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------


def test_find_matching_art_exact_case_insensitive(handler: LibretroHandler):
    # The match should prefer the exact case-insensitive filename (region tag
    # included), so a PAL ROM lands on the (Europe) artwork.
    result = handler._find_matching_art(
        "Castlevania - Symphony of the Night (Europe).iso", PSX_LISTING
    )
    assert result == "Castlevania - Symphony of the Night (Europe).png"


def test_find_matching_art_different_case(handler: LibretroHandler):
    result = handler._find_matching_art(
        "CASTLEVANIA - SYMPHONY OF THE NIGHT (USA).bin", PSX_LISTING
    )
    assert result == "Castlevania - Symphony of the Night (USA).png"


def test_find_matching_art_ampersand_normalized(handler: LibretroHandler):
    # Libretro filenames replace `&` with `_`; ROM filename uses `&`.
    result = handler._find_matching_art(
        "Sonic & Knuckles Collection (USA).iso", PSX_LISTING
    )
    assert result == "Sonic _ Knuckles Collection (USA).png"


def test_find_matching_art_fuzzy_fallback(handler: LibretroHandler):
    # No exact match, since the ROM has an extra `(Rev 1)` tag that libretro doesn't
    # index. Fuzzy fallback strips tags from both sides; the Europe variant
    # is the first tag-stripped candidate and wins.
    result = handler._find_matching_art(
        "Castlevania - Symphony of the Night (Europe) (Rev 1).iso", PSX_LISTING
    )
    assert result is not None
    assert result.startswith("Castlevania - Symphony of the Night")


def test_find_matching_art_no_match(handler: LibretroHandler):
    result = handler._find_matching_art(
        "Completely Made Up Game Title XYZ.iso", PSX_LISTING
    )
    assert result is None


# ---------------------------------------------------------------------------
# get_rom (scan path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_rom_unsupported_platform_returns_empty(handler: LibretroHandler):
    result = await handler.get_rom("whatever.iso", "not-a-real-platform")
    assert result == {"libretro_id": None}


@pytest.mark.asyncio
async def test_get_rom_matched_returns_cover_url(handler: LibretroHandler):
    # Isolate from SCAN_MEDIA defaults so this test only exercises box art.
    with (
        patch.object(
            handler.service,
            "fetch_listing",
            AsyncMock(return_value=PSX_LISTING),
        ) as mock_fetch,
        patch(
            "handler.metadata.libretro_handler.get_preferred_media_types",
            return_value=[],
        ),
    ):
        result = await handler.get_rom(
            "Castlevania - Symphony of the Night (Europe).iso", "psx"
        )

    mock_fetch.assert_awaited_once()
    # libretro_id is the SHA1 hex of the matched libretro filename
    expected_id = libretro_id_for("Castlevania - Symphony of the Night (Europe).png")
    assert result["libretro_id"]
    assert result["libretro_id"] == expected_id
    assert len(result["libretro_id"]) == 40  # SHA1 hex
    assert result.get("url_cover", "").startswith("https://thumbnails.libretro.com/")
    assert "Sony%20-%20PlayStation" in result.get("url_cover", "")
    assert "Named_Boxarts" in result.get("url_cover", "")
    assert "Europe" in result.get("url_cover", "")
    # Scan path intentionally does not populate `name` so it doesn't
    # overwrite a real IGDB name.
    assert "name" not in result
    # No extra art types requested, so url_screenshots is absent.
    assert "url_screenshots" not in result


@pytest.mark.asyncio
async def test_get_rom_fetches_extra_art_when_preferred(handler: LibretroHandler):
    """SCREENSHOT/TITLE_SCREEN/LOGO in SCAN_MEDIA trigger the corresponding
    Named_Snaps/Named_Titles/Named_Logos fetches; matches land in
    url_screenshots so the scan_handler artwork loop can pick them up."""
    with (
        patch.object(
            handler.service,
            "fetch_listing",
            AsyncMock(return_value=PSX_LISTING),
        ) as mock_fetch,
        patch(
            "handler.metadata.libretro_handler.get_preferred_media_types",
            return_value=[
                MetadataMediaType.SCREENSHOT,
                MetadataMediaType.TITLE_SCREEN,
                MetadataMediaType.LOGO,
            ],
        ),
    ):
        result = await handler.get_rom(
            "Castlevania - Symphony of the Night (Europe).iso", "psx"
        )

    # Box art + three extras = four listings fetched in parallel.
    assert mock_fetch.await_count == 4
    screenshots = result.get("url_screenshots", [])
    assert len(screenshots) == 3
    assert any("Named_Snaps" in s for s in screenshots)
    assert any("Named_Titles" in s for s in screenshots)
    assert any("Named_Logos" in s for s in screenshots)
    # url_cover still comes from Named_Boxarts.
    assert "Named_Boxarts" in result.get("url_cover", "")


@pytest.mark.asyncio
async def test_get_rom_skips_extra_art_when_not_preferred(handler: LibretroHandler):
    """Only Named_Boxarts is fetched when no extra media types are in SCAN_MEDIA."""
    with (
        patch.object(
            handler.service,
            "fetch_listing",
            AsyncMock(return_value=PSX_LISTING),
        ) as mock_fetch,
        patch(
            "handler.metadata.libretro_handler.get_preferred_media_types",
            return_value=[MetadataMediaType.BOX2D, MetadataMediaType.MANUAL],
        ),
    ):
        result = await handler.get_rom(
            "Castlevania - Symphony of the Night (Europe).iso", "psx"
        )

    mock_fetch.assert_awaited_once()
    assert "url_screenshots" not in result


def test_libretro_id_for_is_deterministic():
    f = "Castlevania - Symphony of the Night (Europe).png"
    assert libretro_id_for(f) == libretro_id_for(f)
    # Sanity-check the algorithm so the ID is stable across releases.
    assert libretro_id_for(f) == hashlib.sha1(f.encode("utf-8")).hexdigest()


def test_libretro_id_for_distinguishes_regions():
    assert libretro_id_for(
        "Castlevania - Symphony of the Night (USA).png"
    ) != libretro_id_for("Castlevania - Symphony of the Night (Europe).png")


@pytest.mark.asyncio
async def test_get_rom_no_match_returns_empty(handler: LibretroHandler):
    with patch.object(
        handler.service,
        "fetch_listing",
        AsyncMock(return_value=PSX_LISTING),
    ):
        result = await handler.get_rom("Totally Unknown Title.iso", "psx")

    assert result == {"libretro_id": None}


@pytest.mark.asyncio
async def test_get_rom_empty_listing_returns_empty(handler: LibretroHandler):
    with patch.object(
        handler.service,
        "fetch_listing",
        AsyncMock(return_value=[]),
    ):
        result = await handler.get_rom("Whatever.iso", "psx")

    assert result == {"libretro_id": None}


# ---------------------------------------------------------------------------
# LibretroThumbnailsService helpers
# ---------------------------------------------------------------------------


def test_build_art_url_encodes_spaces_and_special_chars():
    url = LibretroThumbnailsService.build_art_url(
        "Sony - PlayStation",
        LibretroArtType.BOX_ART,
        "Castlevania - Symphony of the Night (Europe).png",
    )
    assert url.startswith("https://thumbnails.libretro.com/")
    assert "Sony%20-%20PlayStation" in url
    assert "Named_Boxarts" in url
    # Filename-level encoding is strict (space → %20, paren encoded).
    assert "Castlevania%20-%20Symphony%20of%20the%20Night" in url


def test_art_type_values():
    assert LibretroArtType.BOX_ART.value == "Named_Boxarts"
    assert LibretroArtType.TITLE_SCREEN.value == "Named_Titles"
    assert LibretroArtType.LOGO.value == "Named_Logos"
    assert LibretroArtType.SCREENSHOT.value == "Named_Snaps"


# ---------------------------------------------------------------------------
# Handler basics
# ---------------------------------------------------------------------------


def test_is_enabled_always_true():
    # No API key required; this is a public server.
    assert LibretroHandler.is_enabled() is True
