"""Tests for the MobyGames metadata handler."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from handler.metadata.base_handler import PS1_SERIAL_INDEX_KEY
from handler.metadata.moby_handler import PS1_MOBY_ID, MobyGamesHandler
from handler.redis_handler import async_cache


class TestSonySerialFilenames:
    """Tests for Sony serial resolution in get_rom."""

    @pytest.mark.asyncio
    async def test_serial_at_filename_start_resolves_title(self):
        """A serial in the first two characters of the filename must still hit
        the serial index. Regression: re.IGNORECASE was passed as the ``pos``
        argument of ``Pattern.search()``, skipping the first two characters,
        so files named by their serial (e.g. ``SCUS-94163.bin``) were never
        resolved."""
        handler = MobyGamesHandler()

        with (
            patch(
                "handler.metadata.moby_handler.MobyGamesHandler.is_enabled",
                return_value=True,
            ),
            patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget,
            patch.object(
                MobyGamesHandler,
                "_search_rom",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_hget.return_value = json.dumps({"title": "Gran Turismo"})
            result = await handler.get_rom("SCUS-94163.bin", PS1_MOBY_ID)

        mock_hget.assert_awaited_once_with(PS1_SERIAL_INDEX_KEY, "SCUS-94163")
        assert result.get("name") == "Gran Turismo"
        assert result["moby_id"] is None


class TestSearchTermEncoding:
    """Tests that search terms are passed to the service layer unencoded."""

    @pytest.mark.asyncio
    async def test_search_rom_does_not_pre_encode_special_characters(self):
        """The service layer URL-encodes the title exactly once via
        ``with_query``. Regression: the handler pre-quoted the term, so titles
        containing "&", "+" or "'" were double-encoded ("&" -> "%2526") and
        never matched (e.g. "Sonic & Knuckles",
        "Super Mario 3D World + Bowser's Fury")."""
        handler = MobyGamesHandler()

        with patch.object(
            handler.moby_service,
            "list_games",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list_games:
            await handler._search_rom("Sonic & Knuckles", platform_moby_id=16)

        mock_list_games.assert_awaited_once()
        await_args = mock_list_games.await_args
        assert await_args is not None
        title = await_args.kwargs["title"]
        assert title == "Sonic & Knuckles"
        assert "%" not in title

    @pytest.mark.asyncio
    async def test_get_matched_roms_by_name_does_not_pre_encode(self):
        """Same double-encoding regression for the manual-search path."""
        handler = MobyGamesHandler()

        with (
            patch(
                "handler.metadata.moby_handler.MobyGamesHandler.is_enabled",
                return_value=True,
            ),
            patch.object(
                handler.moby_service,
                "list_games",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_list_games,
        ):
            await handler.get_matched_roms_by_name(
                "Super Mario 3D World + Bowser's Fury", platform_moby_id=203
            )

        mock_list_games.assert_awaited_once()
        await_args = mock_list_games.await_args
        assert await_args is not None
        title = await_args.kwargs["title"]
        assert title == "Super Mario 3D World + Bowser's Fury"
        assert "%" not in title
