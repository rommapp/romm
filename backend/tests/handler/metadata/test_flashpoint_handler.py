from unittest.mock import AsyncMock, patch

import pytest
from handler.metadata.flashpoint_handler import (
    FLASHPOINT_PLATFORM_LIST,
    FlashpointHandler,
)


class TestFlashpointHandler:
    def test_init(self):
        """Test FlashpointHandler initialization"""
        handler = FlashpointHandler()
        assert handler.base_url == "https://db-api.unstable.life"
        assert handler.search_url == "https://db-api.unstable.life/search"
        assert handler.min_similarity_score == 0.75

    def test_get_platform_browser(self):
        """Test get_platform with browser platform"""
        handler = FlashpointHandler()
        platform = handler.get_platform("browser")

        assert platform["flashpoint_id"] == "browser"
        assert platform["slug"] == "browser"
        assert platform["name"] == "Browser (Flash/HTML5)"

    def test_get_platform_unsupported(self):
        """Test get_platform with unsupported platform"""
        handler = FlashpointHandler()
        platform = handler.get_platform("nintendo-64")

        assert platform["flashpoint_id"] is None
        assert platform["slug"] == "nintendo-64"
        assert platform["name"] == ""

    @pytest.mark.asyncio
    async def test_search_games_success(self):
        """Test successful game search"""
        handler = FlashpointHandler()

        mock_response = [
            {
                "id": "test-id",
                "title": "Test Game",
                "developer": "Test Dev",
                "publisher": "Test Pub",
                "platform": "Flash",
                "library": "arcade",
                "tags": ["Action"],
                "originalDescription": "A test game",
                "dateAdded": "2024-01-01T00:00:00Z",
                "dateModified": "2024-01-01T00:00:00Z",
            }
        ]

        with patch.object(handler, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            games = await handler.search_games("test")

            assert len(games) == 1
            assert games[0]["id"] == "test-id"
            assert games[0]["title"] == "Test Game"

    @pytest.mark.asyncio
    async def test_search_games_empty_response(self):
        """Test game search with empty response"""
        handler = FlashpointHandler()

        with patch.object(handler, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = []

            games = await handler.search_games("nonexistent")

            assert len(games) == 0

    @pytest.mark.asyncio
    async def test_get_rom_browser_platform(self):
        """Test get_rom with browser platform"""
        handler = FlashpointHandler()

        mock_games = [
            {
                "id": "test-id",
                "title": "Test Game",
                "developer": "Test Dev",
                "publisher": "Test Pub",
                "platform": "Flash",
                "library": "arcade",
                "tags": ["Action"],
                "originalDescription": "A test game description",
                "dateAdded": "2024-01-01T00:00:00Z",
                "dateModified": "2024-01-01T00:00:00Z",
            }
        ]

        with patch.object(
            handler, "search_games", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_games

            rom = await handler.get_rom("test_game.swf", "browser")

            assert rom["flashpoint_id"] == "test-id"
            assert rom["name"] == "Test Game"
            assert rom["developer"] == "Test Dev"
            assert rom["publisher"] == "Test Pub"

    @pytest.mark.asyncio
    async def test_get_rom_unsupported_platform(self):
        """Test get_rom with unsupported platform"""
        handler = FlashpointHandler()

        rom = await handler.get_rom("test_game.swf", "nintendo-64")

        assert rom["flashpoint_id"] is None

    @pytest.mark.asyncio
    async def test_get_rom_by_id_success(self):
        """Test successful ROM retrieval by ID"""
        handler = FlashpointHandler()

        mock_response = [
            {
                "id": "test-id",
                "title": "Test Game",
                "developer": "Test Dev",
                "publisher": "Test Pub",
                "platform": "Flash",
                "library": "arcade",
                "tags": ["Action"],
                "originalDescription": "A test game description",
                "dateAdded": "2024-01-01T00:00:00Z",
                "dateModified": "2024-01-01T00:00:00Z",
            }
        ]

        with patch.object(handler, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            rom = await handler.get_rom_by_id("test-id")

            assert rom["flashpoint_id"] == "test-id"
            assert rom["name"] == "Test Game"

    @pytest.mark.asyncio
    async def test_get_rom_by_id_not_found(self):
        """Test ROM retrieval by ID when not found"""
        handler = FlashpointHandler()

        with patch.object(handler, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = []

            rom = await handler.get_rom_by_id("nonexistent-id")

            assert rom["flashpoint_id"] is None

    def test_platform_list(self):
        """Test FLASHPOINT_PLATFORM_LIST contains only browser"""
        assert "browser" in FLASHPOINT_PLATFORM_LIST
        assert len(FLASHPOINT_PLATFORM_LIST) == 1
