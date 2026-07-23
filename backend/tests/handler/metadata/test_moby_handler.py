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
