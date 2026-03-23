"""Tests for IGDB handler search cache semantics."""

from unittest.mock import AsyncMock, patch

import pytest

from handler.metadata.igdb_handler import IGDBHandler


class TestIGDBSearchCache:
    """Tests for the per-scan IGDB search cache."""

    @pytest.fixture
    def handler(self):
        with patch.object(IGDBHandler, "is_enabled", return_value=True):
            h = IGDBHandler()
            return h

    def test_cache_starts_empty(self, handler: IGDBHandler):
        assert len(handler._search_cache) == 0

    def test_clear_search_cache(self, handler: IGDBHandler):
        handler._search_cache[("test", 33)] = {"id": 1, "name": "Test"}
        handler.clear_search_cache()
        assert len(handler._search_cache) == 0

    async def test_positive_match_is_cached(self, handler: IGDBHandler):
        """A successful search result should be cached for dedup."""
        fake_game = {"id": 123, "name": "Tetris", "game_type": 0}

        mock_search = AsyncMock(return_value=fake_game)
        with patch.object(handler, "_search_games", mock_search):
            result1 = await handler._search_rom("tetris", 33)
            assert result1 == fake_game
            assert ("tetris", 33) in handler._search_cache

            # Second call should use cache, not call _search_games again
            mock_search.reset_mock()
            result2 = await handler._search_rom("tetris", 33)
            assert result2 == fake_game
            mock_search.assert_not_called()

    async def test_negative_result_not_cached(self, handler: IGDBHandler):
        """A failed search (no match) should NOT be cached to avoid
        memoizing transient API failures as permanent misses."""
        with (
            patch.object(
                handler, "_search_games", new_callable=AsyncMock, return_value=None
            ),
            patch.object(
                handler, "_expanded_search", new_callable=AsyncMock, return_value=None
            ),
        ):
            result = await handler._search_rom("unknown_game", 33)
            assert result is None
            assert ("unknown_game", 33) not in handler._search_cache

    async def test_no_platform_id_returns_none(self, handler: IGDBHandler):
        result = await handler._search_rom("test", 0)
        assert result is None
