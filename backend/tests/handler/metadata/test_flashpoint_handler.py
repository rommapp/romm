"""Tests for the Flashpoint handler's lookup failure reporting."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from handler.metadata.flashpoint_handler import FlashpointHandler


@pytest.mark.asyncio
async def test_search_games_propagates_an_unreachable_flashpoint():
    """A failed search has to stay distinguishable from a term with no hits."""
    handler = FlashpointHandler()

    with (
        patch.object(FlashpointHandler, "is_enabled", return_value=True),
        patch.object(
            FlashpointHandler,
            "_request",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="down"),
        ),
        pytest.raises(HTTPException),
    ):
        await handler.search_games("Interactive Buddy")


@pytest.mark.asyncio
async def test_get_rom_by_id_propagates_an_unreachable_flashpoint():
    handler = FlashpointHandler()

    with (
        patch("handler.metadata.flashpoint_handler.FLASHPOINT_API_ENABLED", True),
        patch.object(
            FlashpointHandler,
            "_request",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="down"),
        ),
        pytest.raises(HTTPException),
    ):
        await handler.get_rom_by_id("dc1f7d99-9a3d-4f3f-8f2a-000000000000")
