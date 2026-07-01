"""Tests for the RetroAchievements metadata handler platform mapping."""

import pytest

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.metadata.ra_handler import RA_PLATFORM_LIST, RAHandler

# RetroAchievements groups MSX and MSX2 under a single console, "MSX"
# (console ID 29). See GitHub issue #3644.
RA_MSX_CONSOLE_ID = 29

# RomM models MSX and MSX2 as separate platforms; RA lumps both into console 29.
MSX_SLUGS_ON_CONSOLE_29 = ["msx", "msx2"]


@pytest.fixture
def handler() -> RAHandler:
    return RAHandler()


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", MSX_SLUGS_ON_CONSOLE_29)
def test_get_platform_msx_slugs_map_to_msx_console(handler: RAHandler, slug: str):
    """MSX and MSX2 both resolve to RA's single MSX console (ID 29), so their
    ROMs get an RA hash and can match (issue #3644)."""
    platform = handler.get_platform(slug)
    assert platform["ra_id"] == RA_MSX_CONSOLE_ID
    assert platform["slug"] == slug


def test_msx2_shares_the_msx_console_id(handler: RAHandler):
    """msx2 must resolve to the same RA id as msx."""
    msx_id = handler.get_platform("msx")["ra_id"]
    assert msx_id == RA_MSX_CONSOLE_ID
    assert handler.get_platform("msx2")["ra_id"] == msx_id


def test_get_platform_unsupported_returns_none(handler: RAHandler):
    platform = handler.get_platform("not-a-real-platform")
    assert platform["ra_id"] is None
    assert platform["slug"] == "not-a-real-platform"


def test_platform_list_uses_ups_keys():
    """Every entry in RA_PLATFORM_LIST should be a UniversalPlatformSlug."""
    for key in RA_PLATFORM_LIST.keys():
        assert isinstance(key, UPS)
