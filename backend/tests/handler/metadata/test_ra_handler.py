"""Tests for the RetroAchievements metadata handler."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from handler.metadata import ra_handler
from handler.metadata.ra_handler import RA_PLATFORM_LIST, RAHandler
from utils.platform_slugs import UniversalPlatformSlug as UPS


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


class TestSearchRom:
    """The hash index must only map hashes of games that actually have a set."""

    @pytest.fixture(autouse=True)
    def _pin_cache_ttl(self, monkeypatch: pytest.MonkeyPatch):
        """A local .env may set this to 0, which would force a refresh every time."""
        monkeypatch.setattr(ra_handler, "REFRESH_RETROACHIEVEMENTS_CACHE_DAYS", 30)

    def _make_rom(self) -> MagicMock:
        rom = MagicMock()
        rom.platform.id = 1
        rom.platform.ra_id = 2
        return rom

    async def test_skips_games_without_achievements(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch
    ):
        get_game_list = AsyncMock(
            return_value=[{"ID": 10210, "Hashes": ["ABCDEF", "123456"]}]
        )
        write_file = AsyncMock()
        monkeypatch.setattr(handler.ra_service, "get_game_list", get_game_list)
        monkeypatch.setattr(
            ra_handler.fs_resource_handler, "file_exists", AsyncMock(return_value=False)
        )
        monkeypatch.setattr(
            ra_handler.fs_resource_handler,
            "get_platform_resources_path",
            lambda _platform_id: "roms/1",
        )
        monkeypatch.setattr(ra_handler.fs_resource_handler, "write_file", write_file)

        ra_id = await handler._search_rom(self._make_rom(), "abcdef")

        get_game_list.assert_awaited_once_with(
            system_id=2,
            only_games_with_achievements=True,
            include_hashes=True,
        )
        assert ra_id == 10210

        written = json.loads(write_file.await_args_list[0].args[0].decode("utf-8"))
        assert written == {"abcdef": 10210, "123456": 10210}

    async def test_reads_the_cached_index_without_refetching(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        cache_file = tmp_path / handler.HASHES_FILE_NAME
        cache_file.write_bytes(json.dumps({"abcdef": 10210}).encode("utf-8"))

        get_game_list = AsyncMock()
        monkeypatch.setattr(handler.ra_service, "get_game_list", get_game_list)
        monkeypatch.setattr(
            ra_handler.fs_resource_handler, "file_exists", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            ra_handler.fs_resource_handler, "validate_path", lambda _path: cache_file
        )
        monkeypatch.setattr(
            ra_handler.fs_resource_handler,
            "read_file",
            AsyncMock(return_value=cache_file.read_bytes()),
        )

        ra_id = await handler._search_rom(self._make_rom(), "ABCDEF")

        assert ra_id == 10210
        get_game_list.assert_not_awaited()

    async def test_returns_none_without_a_platform_ra_id(self, handler: RAHandler):
        rom = self._make_rom()
        rom.platform.ra_id = None

        assert await handler._search_rom(rom, "abcdef") is None
