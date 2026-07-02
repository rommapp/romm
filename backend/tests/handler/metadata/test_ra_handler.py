"""Tests for the RetroAchievements metadata handler platform mapping."""

import pytest

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.metadata.ra_handler import (
    RA_PLATFORM_LIST,
    RAHandler,
)


@pytest.fixture
def handler() -> RAHandler:
    return RAHandler()


def test_get_platform_unsupported_returns_none(handler: RAHandler):
    platform = handler.get_platform("not-a-real-platform")
    assert platform["ra_id"] is None
    assert platform["slug"] == "not-a-real-platform"


def test_platform_list_uses_ups_keys():
    """Every entry in RA_PLATFORM_LIST should be a UniversalPlatformSlug."""
    for key in RA_PLATFORM_LIST.keys():
        assert isinstance(key, UPS)
