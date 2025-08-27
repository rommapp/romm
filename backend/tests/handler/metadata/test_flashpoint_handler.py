from unittest.mock import AsyncMock, patch

import pytest
from handler.metadata.flashpoint_handler import (
    FLASHPOINT_PLATFORM_LIST,
    FlashpointGame,
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

        assert platform["slug"] == "browser"
        assert platform.get("name") is not None

    def test_get_platform_unsupported(self):
        """Test get_platform with unsupported platform"""
        handler = FlashpointHandler()
        platform = handler.get_platform("nintendo-64")

        assert platform["slug"] == "nintendo-64"
        assert platform.get("name") is None

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
            print(games)

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
            FlashpointGame(
                {
                    "id": "test-id",
                    "title": "Test Game",
                    "developer": "Test Dev",
                    "publisher": "Test Pub",
                    "platform": "Flash",
                    "library": "arcade",
                    "series": "Test Series",
                    "source": "Test Source",
                    "play_mode": "Test Play Mode",
                    "status": "Test Status",
                    "version": "Test Version",
                    "release_date": "2024-01-01",
                    "language": "Test Language",
                    "notes": "Test Notes",
                    "tags": ["Action"],
                    "original_description": "A test game description",
                    "date_added": "2024-01-01T00:00:00Z",
                    "date_modified": "2024-01-01T00:00:00Z",
                }
            ),
        ]

        with patch.object(
            handler, "search_games", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_games

            rom = await handler.get_rom("test_game.swf", "browser")

            assert rom["flashpoint_id"] == "test-id"
            assert rom.get("name") == "Test Game"

            flashpoint_metadata = rom.get("flashpoint_metadata")
            assert flashpoint_metadata is not None
            assert flashpoint_metadata["companies"] == ["Test Dev", "Test Pub"]
            assert flashpoint_metadata["franchises"] == ["Test Series"]
            assert flashpoint_metadata["genres"] == ["Action"]
            assert flashpoint_metadata["game_modes"] == ["Test Play Mode"]
            assert flashpoint_metadata["first_release_date"] == "1704060000"
            assert flashpoint_metadata["status"] == "Test Status"
            assert flashpoint_metadata["version"] == "Test Version"
            assert flashpoint_metadata["language"] == "Test Language"
            assert flashpoint_metadata["notes"] == "Test Notes"

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
                "releaseDate": "2024-01-01",
                "dateAdded": "2024-01-01T00:00:00Z",
                "dateModified": "2024-01-01T00:00:00Z",
                "series": "Test Series",
                "playMode": "Test Play Mode",
                "status": "Test Status",
                "version": "Test Version",
                "language": "Test Language",
                "notes": "Test Notes",
                "source": "Test Source",
            }
        ]

        with patch.object(handler, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            rom = await handler.get_rom_by_id("test-id")

            assert rom["flashpoint_id"] == "test-id"
            assert rom.get("name") == "Test Game"

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
