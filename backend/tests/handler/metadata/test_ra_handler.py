"""Tests for the RetroAchievements metadata handler platform mapping."""

import pytest

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.metadata.ra_handler import (
    RA_ID_TO_SLUG,
    RA_PLATFORM_LIST,
    RAHandler,
)

# RetroAchievements lists the Famicom Disk System as its own console
# (console ID 81), separate from the NES/Famicom console (ID 7). See GitHub
# issue #3646.
RA_FDS_CONSOLE_ID = 81
RA_NES_CONSOLE_ID = 7


@pytest.fixture
def handler() -> RAHandler:
    return RAHandler()


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------


def test_get_platform_fds_maps_to_console_81(handler: RAHandler):
    """fds resolves to RA's dedicated Famicom Disk System console (ID 81), so
    its ROMs get an RA hash and can match (issue #3646)."""
    platform = handler.get_platform("fds")
    assert platform["ra_id"] == RA_FDS_CONSOLE_ID
    assert platform["slug"] == "fds"


def test_fds_console_is_distinct_from_nes(handler: RAHandler):
    """fds must not reuse the NES/Famicom console ID; RA models it separately."""
    assert handler.get_platform("nes")["ra_id"] == RA_NES_CONSOLE_ID
    assert handler.get_platform("fds")["ra_id"] != RA_NES_CONSOLE_ID


def test_fds_reverse_lookup_resolves_to_fds_slug():
    """The FDS console ID is unique, so the reverse map points back to fds."""
    assert RA_ID_TO_SLUG[RA_FDS_CONSOLE_ID] == UPS.FDS


def test_get_platform_unsupported_returns_none(handler: RAHandler):
    platform = handler.get_platform("not-a-real-platform")
    assert platform["ra_id"] is None
    assert platform["slug"] == "not-a-real-platform"


def test_platform_list_uses_ups_keys():
    """Every entry in RA_PLATFORM_LIST should be a UniversalPlatformSlug."""
    for key in RA_PLATFORM_LIST.keys():
        assert isinstance(key, UPS)
