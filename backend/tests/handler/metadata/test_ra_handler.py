"""Tests for the RetroAchievements metadata handler platform mapping."""

import pytest

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.metadata.ra_handler import (
    RA_PLATFORM_LIST,
    RAHandler,
)

# RetroAchievements groups the PC Engine, TurboGrafx-16 and SuperGrafx under a
# single console (console ID 8). RomM already maps tg16 to that console; the
# supergrafx slug must resolve to the same one so its ROMs get an RA hash and
# can match. See GitHub issue #3651.
RA_PC_ENGINE_CONSOLE_ID = 8


@pytest.fixture
def handler() -> RAHandler:
    return RAHandler()


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------


def test_get_platform_supergrafx_maps_to_console_8(handler: RAHandler):
    """supergrafx resolves to RA's PC Engine/TurboGrafx-16 console (ID 8), so
    its ROMs get an RA hash and can match (issue #3651)."""
    platform = handler.get_platform("supergrafx")
    assert platform["ra_id"] == RA_PC_ENGINE_CONSOLE_ID
    assert platform["slug"] == "supergrafx"


def test_supergrafx_shares_console_with_tg16(handler: RAHandler):
    """RA has no separate SuperGrafx console; supergrafx must reuse the same
    console ID as tg16 rather than being left unmapped (issue #3651)."""
    assert (
        handler.get_platform("supergrafx")["ra_id"]
        == handler.get_platform("tg16")["ra_id"]
    )


def test_get_platform_unsupported_returns_none(handler: RAHandler):
    platform = handler.get_platform("not-a-real-platform")
    assert platform["ra_id"] is None
    assert platform["slug"] == "not-a-real-platform"


def test_platform_list_uses_ups_keys():
    """Every entry in RA_PLATFORM_LIST should be a UniversalPlatformSlug."""
    for key in RA_PLATFORM_LIST.keys():
        assert isinstance(key, UPS)
