"""Tests for the RetroAchievements metadata handler platform mapping."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.metadata.ra_handler import RA_PLATFORM_LIST, RAHandler


@pytest.fixture
def handler() -> RAHandler:
    return RAHandler()


def _rom(platform_ra_id: int | None = 7, platform_id: int = 1):
    return SimpleNamespace(
        platform=SimpleNamespace(ra_id=platform_ra_id, id=platform_id)
    )


class TestHashIsKnown:
    """`hash_is_known` answers from RA's own hash list, not another provider.

    Every sibling of a game shares its `ra_id`, so this per-file answer is
    the only thing that says whether achievements will unlock.
    """

    async def test_recognises_a_hash_in_ras_list(self, handler: RAHandler):
        handler._get_hash_index = AsyncMock(return_value={"abc123": 42})  # type: ignore[method-assign]

        assert await handler.hash_is_known(_rom(), "ABC123") is True

    async def test_rejects_a_hash_ra_has_never_seen(self, handler: RAHandler):
        handler._get_hash_index = AsyncMock(return_value={"abc123": 42})  # type: ignore[method-assign]

        assert await handler.hash_is_known(_rom(), "deadbeef") is False

    @pytest.mark.parametrize(
        ("platform_ra_id", "ra_hash"),
        [(None, "abc123"), (7, "")],
        ids=["platform-not-on-ra", "no-hash-computed"],
    )
    async def test_stays_unknown_with_nothing_to_check(
        self, handler: RAHandler, platform_ra_id: int | None, ra_hash: str
    ):
        handler._get_hash_index = AsyncMock(return_value={"abc123": 42})  # type: ignore[method-assign]

        assert await handler.hash_is_known(_rom(platform_ra_id), ra_hash) is None

    async def test_stays_unknown_when_the_list_cant_be_read(self, handler: RAHandler):
        """A missing or unreadable index must not read as "unsupported"."""
        handler._get_hash_index = AsyncMock(side_effect=OSError("boom"))  # type: ignore[method-assign]

        assert await handler.hash_is_known(_rom(), "abc123") is None


async def test_hash_index_is_parsed_once_per_platform(handler: RAHandler):
    """A scan asks per ROM; the multi-MB parse happens once."""
    handler._exists_cache_file = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._days_since_last_cache_file_update = AsyncMock(return_value=0)  # type: ignore[method-assign]
    read_file = AsyncMock(return_value=b'{"abc123": 42}')

    from handler.metadata import ra_handler as ra_handler_module

    original = ra_handler_module.fs_resource_handler.read_file
    ra_handler_module.fs_resource_handler.read_file = read_file  # type: ignore[method-assign]
    try:
        rom = _rom()
        assert await handler.hash_is_known(rom, "abc123") is True
        assert await handler.hash_is_known(rom, "abc123") is True
    finally:
        ra_handler_module.fs_resource_handler.read_file = original  # type: ignore[method-assign]

    assert read_file.await_count == 1


def test_get_platform_unsupported_returns_none(handler: RAHandler):
    platform = handler.get_platform("not-a-real-platform")
    assert platform["ra_id"] is None
    assert platform["slug"] == "not-a-real-platform"


def test_platform_list_uses_ups_keys():
    """Every entry in RA_PLATFORM_LIST should be a UniversalPlatformSlug."""
    for key in RA_PLATFORM_LIST.keys():
        assert isinstance(key, UPS)
