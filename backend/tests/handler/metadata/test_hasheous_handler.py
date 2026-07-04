"""Tests for the Hasheous ScreenScraper proxy fallback."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.services.screenscraper_types import SSGame
from config.config_manager import Config, MetadataMediaType
from handler.metadata.hasheous_handler import HasheousHandler


@pytest.fixture
def handler() -> HasheousHandler:
    return HasheousHandler()


def _make_config() -> Config:
    return Config(
        EXCLUDED_PLATFORMS=[],
        EXCLUDED_SINGLE_EXT=[],
        EXCLUDED_SINGLE_FILES=[],
        EXCLUDED_MULTI_FILES=[],
        EXCLUDED_MULTI_PARTS_EXT=[],
        EXCLUDED_MULTI_PARTS_FILES=[],
        PLATFORMS_BINDING={},
        PLATFORMS_VERSIONS={},
        ROMS_FOLDER_NAME="roms",
        FIRMWARE_FOLDER_NAME="bios",
        SCAN_REGION_PRIORITY=[],
        SCAN_LANGUAGE_PRIORITY=["en"],
        SCAN_MEDIA=["box2d", "box3d", "screenshot"],
        GAMELIST_MEDIA_THUMBNAIL=MetadataMediaType.BOX2D,
        GAMELIST_MEDIA_IMAGE=MetadataMediaType.SCREENSHOT,
    )


def _make_rom() -> MagicMock:
    rom = MagicMock()
    rom.regions = []
    rom.platform_slug = "snes"
    rom.platform_id = 1
    rom.id = 1
    return rom


def _make_file() -> MagicMock:
    f = MagicMock()
    f.file_size_bytes = 1024
    f.is_top_level = True
    f.file_extension = "sfc"
    f.md5_hash = "abc123md5"
    f.sha1_hash = "abc123sha1"
    f.crc_hash = "deadbeef"
    f.file_name = "Sonic (USA).sfc"
    f.archive_members = None
    return f


def _jeu_response(game_id: str = "12345") -> dict:
    return {
        "response": {
            "jeu": {
                "id": game_id,
                "noms": [{"region": "ss", "text": "Sonic the Hedgehog"}],
                "synopsis": [{"langue": "en", "text": "A speedy platformer."}],
            }
        }
    }


@pytest.mark.asyncio
async def test_get_ss_game_populates_ssrom(handler: HasheousHandler):
    with (
        patch.object(HasheousHandler, "is_enabled", return_value=True),
        patch("handler.metadata.ss_handler.cm.get_config", return_value=_make_config()),
        patch.object(
            handler, "_request", new=AsyncMock(return_value=_jeu_response())
        ) as req,
    ):
        result = await handler.get_ss_game(_make_rom(), 4, [_make_file()])

    assert result["ss_id"] == 12345
    assert result["name"] == "Sonic the Hedgehog"
    assert result["summary"] == "A speedy platformer."
    assert result.get("ss_metadata") is not None

    # jeuInfos is queried with the platform id and the file hashes.
    _, kwargs = req.call_args
    params = kwargs["params"]
    assert params["systemeid"] == 4
    assert params["md5"] == "abc123md5"
    assert params["sha1"] == "abc123sha1"
    assert params["crc"] == "deadbeef"
    assert kwargs["method"] == "GET"


@pytest.mark.asyncio
async def test_get_ss_game_disabled_returns_empty(handler: HasheousHandler):
    with patch.object(HasheousHandler, "is_enabled", return_value=False):
        result = await handler.get_ss_game(_make_rom(), 4, [_make_file()])

    assert result["ss_id"] is None


@pytest.mark.asyncio
async def test_get_ss_game_no_platform_id_returns_empty(handler: HasheousHandler):
    with patch.object(HasheousHandler, "is_enabled", return_value=True):
        result = await handler.get_ss_game(_make_rom(), 0, [_make_file()])

    assert result["ss_id"] is None


@pytest.mark.asyncio
async def test_get_ss_game_notgame_returns_empty(handler: HasheousHandler):
    notgame = _jeu_response()
    notgame["response"]["jeu"]["notgame"] = "true"

    with (
        patch.object(HasheousHandler, "is_enabled", return_value=True),
        patch("handler.metadata.ss_handler.cm.get_config", return_value=_make_config()),
        patch.object(handler, "_request", new=AsyncMock(return_value=notgame)),
    ):
        result = await handler.get_ss_game(_make_rom(), 4, [_make_file()])

    assert result["ss_id"] is None


@pytest.mark.asyncio
async def test_get_ss_game_empty_response_returns_empty(handler: HasheousHandler):
    with (
        patch.object(HasheousHandler, "is_enabled", return_value=True),
        patch.object(handler, "_request", new=AsyncMock(return_value={})),
    ):
        result = await handler.get_ss_game(_make_rom(), 4, [_make_file()])

    assert result["ss_id"] is None


@pytest.mark.asyncio
async def test_get_ss_rom_by_id_queries_gameid(handler: HasheousHandler):
    with (
        patch.object(HasheousHandler, "is_enabled", return_value=True),
        patch("handler.metadata.ss_handler.cm.get_config", return_value=_make_config()),
        patch.object(
            handler, "_request", new=AsyncMock(return_value=_jeu_response("999"))
        ) as req,
    ):
        result = await handler.get_ss_rom_by_id(_make_rom(), 999)

    assert result["ss_id"] == 999
    _, kwargs = req.call_args
    assert kwargs["params"]["gameid"] == 999
    assert kwargs["method"] == "GET"


def test_notgame_helper_reused_from_ss_handler():
    """The proxy path must reuse the native ScreenScraper notgame filter."""
    from handler.metadata.hasheous_handler import _is_notgame

    assert _is_notgame(cast(SSGame, {"notgame": "true"})) is True
    assert _is_notgame(cast(SSGame, {"notgame": "false", "noms": []})) is False
