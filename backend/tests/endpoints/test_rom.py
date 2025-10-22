import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from handler.filesystem.roms_handler import FSRomsHandler
from handler.metadata.flashpoint_handler import FlashpointHandler, FlashpointRom
from handler.metadata.igdb_handler import IGDBHandler, IGDBRom
from handler.metadata.launchbox_handler import LaunchboxHandler, LaunchboxRom
from handler.metadata.moby_handler import MobyGamesHandler, MobyGamesRom
from handler.metadata.ra_handler import RAGameRom, RAHandler
from handler.metadata.ss_handler import SSHandler, SSRom
from models.platform import Platform
from models.rom import Rom


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


MOCK_IGDB_ID = 11111
MOCK_MOBY_ID = 22222
MOCK_SS_ID = 33333
MOCK_RA_ID = 44444
MOCK_LAUNCHBOX_ID = 55555
MOCK_FLASHPOINT_ID = 66666
MOCK_HLTB_ID = 77777
MOCK_SGDB_ID = 88888
MOCK_HASHEOUS_ID = 99999


def test_get_rom(client: TestClient, access_token: str, rom: Rom):
    response = client.get(
        f"/api/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["id"] == rom.id


def test_get_all_roms(
    client: TestClient, access_token: str, rom: Rom, platform: Platform
):
    response = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"platform_id": platform.id},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()

    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0

    items = body["items"]
    assert len(items) == 1
    assert items[0]["id"] == rom.id


@patch.object(FSRomsHandler, "rename_fs_rom")
@patch.object(IGDBHandler, "get_rom_by_id", return_value=IGDBRom(igdb_id=None))
def test_update_rom(
    rename_fs_rom_mock: AsyncMock,
    get_rom_by_id_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    rom: Rom,
):
    response = client.put(
        f"/api/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        data={
            "igdb_id": str(MOCK_IGDB_ID),
            "name": "Metroid Prime Remastered",
            "slug": "metroid-prime-remastered",
            "fs_name": "Metroid Prime Remastered.zip",
            "summary": "summary test",
            "url_cover": "https://images.igdb.com/igdb/image/upload/t_cover_big/co2l7z.jpg",
            "genres": '[{"id": 5, "name": "Shooter"}, {"id": 8, "name": "Platform"}, {"id": 31, "name": "Adventure"}]',
            "franchises": '[{"id": 756, "name": "Metroid"}]',
            "collections": '[{"id": 243, "name": "Metroid"}, {"id": 6240, "name": "Metroid Prime"}]',
            "expansions": "[]",
            "dlcs": "[]",
            "companies": '[{"id": 203227, "company": {"id": 70, "name": "Nintendo"}}, {"id": 203307, "company": {"id": 766, "name": "Retro Studios"}}]',
            "first_release_date": "1675814400",
            "youtube_video_id": "dQw4w9WgXcQ",
            "remasters": "[]",
            "remakes": "[]",
            "expanded_games": "[]",
            "ports": "[]",
            "similar_games": "[]",
            "age_ratings": "[1, 2]",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["fs_name"] == "Metroid Prime Remastered.zip"

    assert rename_fs_rom_mock.called
    assert get_rom_by_id_mock.called


def test_delete_roms(client: TestClient, access_token: str, rom: Rom):
    response = client.post(
        "/api/roms/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"roms": [rom.id], "delete_from_fs": []},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["successful_items"] == 1


class TestUpdateMetadataIDs:
    @patch.object(
        IGDBHandler, "get_rom_by_id", return_value=IGDBRom(igdb_id=MOCK_IGDB_ID)
    )
    def test_update_rom_igdb_id(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating IGDB ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"igdb_id": str(MOCK_IGDB_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["igdb_id"] == MOCK_IGDB_ID
        assert get_rom_by_id_mock.called

    @patch.object(
        MobyGamesHandler,
        "get_rom_by_id",
        return_value=MobyGamesRom(moby_id=MOCK_MOBY_ID),
    )
    def test_update_rom_moby_id(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating MobyGames ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"moby_id": str(MOCK_MOBY_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["moby_id"] == MOCK_MOBY_ID
        assert get_rom_by_id_mock.called

    @patch.object(SSHandler, "get_rom_by_id", return_value=SSRom(ss_id=MOCK_SS_ID))
    def test_update_rom_ss_id(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating ScreenScraper ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"ss_id": str(MOCK_SS_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["ss_id"] == MOCK_SS_ID
        assert get_rom_by_id_mock.called

    @patch.object(RAHandler, "get_rom_by_id", return_value=RAGameRom(ra_id=MOCK_RA_ID))
    def test_update_rom_ra_id(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating RetroAchievements ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"ra_id": str(MOCK_RA_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["ra_id"] == MOCK_RA_ID
        assert get_rom_by_id_mock.called

    @patch.object(
        LaunchboxHandler,
        "get_rom_by_id",
        return_value=LaunchboxRom(launchbox_id=MOCK_LAUNCHBOX_ID),
    )
    def test_update_rom_launchbox_id(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating LaunchBox ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"launchbox_id": str(MOCK_LAUNCHBOX_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["launchbox_id"] == MOCK_LAUNCHBOX_ID
        assert get_rom_by_id_mock.called

    @patch.object(
        FlashpointHandler,
        "get_rom_by_id",
        return_value=FlashpointRom(flashpoint_id=str(MOCK_FLASHPOINT_ID)),
    )
    def test_update_rom_flashpoint_id(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating Flashpoint ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"flashpoint_id": str(MOCK_FLASHPOINT_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["flashpoint_id"] == str(MOCK_FLASHPOINT_ID)
        assert get_rom_by_id_mock.called

    # These metadata sources are not called when updating roms
    def test_update_rom_sgdb_id(self, client: TestClient, access_token: str, rom: Rom):
        """Test updating SteamGridDB ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"sgdb_id": str(MOCK_SGDB_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["sgdb_id"] == MOCK_SGDB_ID

    def test_update_rom_hasheous_id(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        """Test updating Hasheous ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"hasheous_id": str(MOCK_HASHEOUS_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["hasheous_id"] == MOCK_HASHEOUS_ID

    def test_update_rom_hltb_id(self, client: TestClient, access_token: str, rom: Rom):
        """Test updating HowLongToBeat ID."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"hltb_id": str(MOCK_HLTB_ID)},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["hltb_id"] == MOCK_HLTB_ID


class TestUpdateRawMetadata:
    @patch.object(
        IGDBHandler,
        "get_rom_by_id",
        return_value=IGDBRom(igdb_id=MOCK_IGDB_ID),
    )
    def test_update_raw_igdb_metadata(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating raw IGDB metadata."""
        raw_metadata = {
            "genres": ["Action"],
            "franchises": ["Metroid"],
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "igdb_id": str(MOCK_IGDB_ID),
                "raw_igdb_metadata": json.dumps(raw_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["igdb_metadata"] is not None
        assert body["igdb_metadata"]["genres"] == ["Action"]
        assert body["igdb_metadata"]["franchises"] == ["Metroid"]

    @patch.object(
        MobyGamesHandler,
        "get_rom_by_id",
        return_value=MobyGamesRom(moby_id=MOCK_MOBY_ID),
    )
    def test_update_raw_moby_metadata(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating raw MobyGames metadata."""
        raw_metadata = {
            "genres": ["Action", "Adventure"],
            "moby_score": "90",
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "moby_id": str(MOCK_MOBY_ID),
                "raw_moby_metadata": json.dumps(raw_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["moby_metadata"] is not None
        assert body["moby_metadata"]["moby_score"] == "90"
        assert body["moby_metadata"]["genres"] == ["Action", "Adventure"]

    @patch.object(
        SSHandler,
        "get_rom_by_id",
        return_value=SSRom(ss_id=MOCK_SS_ID),
    )
    def test_update_raw_ss_metadata(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating raw ScreenScraper metadata."""
        raw_metadata = {
            "ss_score": "85",
            "alternative_names": ["Test SS Game"],
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "ss_id": str(MOCK_SS_ID),
                "raw_ss_metadata": json.dumps(raw_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["ss_metadata"] is not None
        assert body["ss_metadata"]["ss_score"] == "85"
        assert body["ss_metadata"]["alternative_names"] == ["Test SS Game"]

    @patch.object(
        LaunchboxHandler,
        "get_rom_by_id",
        return_value=LaunchboxRom(launchbox_id=MOCK_LAUNCHBOX_ID),
    )
    def test_update_raw_launchbox_metadata(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating raw LaunchBox metadata."""
        raw_metadata = {
            "first_release_date": "1675814400",
            "max_players": 4,
            "release_type": "Single",
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "launchbox_id": str(MOCK_LAUNCHBOX_ID),
                "raw_launchbox_metadata": json.dumps(raw_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["launchbox_metadata"] is not None
        assert body["launchbox_metadata"]["first_release_date"] == 1675814400
        assert body["launchbox_metadata"]["max_players"] == 4
        assert body["launchbox_metadata"]["release_type"] == "Single"

    def test_update_raw_hasheous_metadata(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        """Test updating raw Hasheous metadata."""
        raw_metadata = {
            "tosec_match": True,
            "mame_arcade_match": False,
            "mame_mess_match": True,
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "hasheous_id": str(MOCK_HASHEOUS_ID),
                "raw_hasheous_metadata": json.dumps(raw_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["hasheous_metadata"] is not None
        assert body["hasheous_metadata"]["tosec_match"] is True
        assert body["hasheous_metadata"]["mame_arcade_match"] is False
        assert body["hasheous_metadata"]["mame_mess_match"] is True

    @patch.object(
        FlashpointHandler,
        "get_rom_by_id",
        return_value=FlashpointRom(flashpoint_id=str(MOCK_FLASHPOINT_ID)),
    )
    def test_update_raw_flashpoint_metadata(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating raw Flashpoint metadata."""
        raw_metadata = {
            "franchises": ["Metroid"],
            "companies": ["Nintendo"],
            "source": "Flashpoint",
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "flashpoint_id": str(MOCK_FLASHPOINT_ID),
                "raw_flashpoint_metadata": json.dumps(raw_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["flashpoint_metadata"] is not None
        assert body["flashpoint_metadata"]["franchises"] == ["Metroid"]
        assert body["flashpoint_metadata"]["companies"] == ["Nintendo"]
        assert body["flashpoint_metadata"]["source"] == "Flashpoint"

    def test_update_raw_hltb_metadata(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating raw HowLongToBeat metadata."""
        raw_metadata = {
            "main_story": 10000,
            "main_story_count": 1,
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "hltb_id": str(MOCK_HLTB_ID),
                "raw_hltb_metadata": json.dumps(raw_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["hltb_metadata"] is not None
        assert body["hltb_metadata"]["main_story"] == 10000
        assert body["hltb_metadata"]["main_story_count"] == 1

    # Tests for combined updates
    @patch.object(
        IGDBHandler, "get_rom_by_id", return_value=IGDBRom(igdb_id=MOCK_IGDB_ID)
    )
    def test_update_rom_metadata_id_and_raw_metadata(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating both metadata ID and raw metadata in the same request."""
        raw_igdb_metadata = {
            "genres": ["Action"],
            "franchises": ["Metroid"],
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "igdb_id": str(MOCK_IGDB_ID),
                "raw_igdb_metadata": json.dumps(raw_igdb_metadata),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert get_rom_by_id_mock.called

        body = response.json()
        assert body["igdb_id"] == MOCK_IGDB_ID
        assert body["igdb_metadata"] is not None
        assert body["igdb_metadata"]["genres"] == ["Action"]
        assert body["igdb_metadata"]["franchises"] == ["Metroid"]

    @patch.object(
        IGDBHandler, "get_rom_by_id", return_value=IGDBRom(igdb_id=MOCK_IGDB_ID)
    )
    @patch.object(
        MobyGamesHandler,
        "get_rom_by_id",
        return_value=MobyGamesRom(moby_id=MOCK_MOBY_ID),
    )
    @patch.object(SSHandler, "get_rom_by_id", return_value=SSRom(ss_id=MOCK_SS_ID))
    def test_update_rom_multiple_metadata_ids(
        self,
        igdb_get_rom_by_id_mock: AsyncMock,
        moby_get_rom_by_id_mock: AsyncMock,
        ss_get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating multiple metadata IDs in the same request."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "igdb_id": str(MOCK_IGDB_ID),
                "moby_id": str(MOCK_MOBY_ID),
                "ss_id": str(MOCK_SS_ID),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert igdb_get_rom_by_id_mock.called
        assert moby_get_rom_by_id_mock.called
        assert ss_get_rom_by_id_mock.called

        body = response.json()
        assert body["igdb_id"] == MOCK_IGDB_ID
        assert body["moby_id"] == MOCK_MOBY_ID
        assert body["ss_id"] == MOCK_SS_ID

    @patch.object(
        IGDBHandler, "get_rom_by_id", return_value=IGDBRom(igdb_id=MOCK_IGDB_ID)
    )
    @patch.object(
        MobyGamesHandler,
        "get_rom_by_id",
        return_value=MobyGamesRom(moby_id=MOCK_MOBY_ID),
    )
    @patch.object(SSHandler, "get_rom_by_id", return_value=SSRom(ss_id=MOCK_SS_ID))
    def test_update_rom_multiple_raw_metadata(
        self,
        igdb_get_rom_by_id_mock: AsyncMock,
        moby_get_rom_by_id_mock: AsyncMock,
        ss_get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test updating multiple raw metadata fields in the same request."""
        raw_igdb = {
            "genres": ["Action"],
            "franchises": ["Metroid"],
        }
        raw_moby = {
            "genres": ["Action", "Adventure"],
            "moby_score": "90",
        }
        raw_ss = {
            "ss_score": "85",
            "alternative_names": ["Test SS Game"],
        }

        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "igdb_id": str(MOCK_IGDB_ID),
                "moby_id": str(MOCK_MOBY_ID),
                "ss_id": str(MOCK_SS_ID),
                "raw_igdb_metadata": json.dumps(raw_igdb),
                "raw_moby_metadata": json.dumps(raw_moby),
                "raw_ss_metadata": json.dumps(raw_ss),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert igdb_get_rom_by_id_mock.called
        assert moby_get_rom_by_id_mock.called
        assert ss_get_rom_by_id_mock.called

        body = response.json()
        assert body["igdb_metadata"] is not None
        assert body["igdb_metadata"]["genres"] == ["Action"]
        assert body["igdb_metadata"]["franchises"] == ["Metroid"]

        assert body["moby_metadata"] is not None
        assert body["moby_metadata"]["genres"] == ["Action", "Adventure"]
        assert body["moby_metadata"]["moby_score"] == "90"

        assert body["ss_metadata"] is not None
        assert body["ss_metadata"]["ss_score"] == "85"
        assert body["ss_metadata"]["alternative_names"] == ["Test SS Game"]

    # Tests for invalid JSON handling
    def test_update_rom_invalid_json_raw_metadata(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test that invalid JSON in raw metadata is handled gracefully."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"raw_igdb_metadata": "invalid json {["},
        )
        # Should still succeed, but raw metadata should not be updated
        assert response.status_code == status.HTTP_200_OK
        # The invalid JSON should be ignored, so igdb_metadata should remain unchanged
        body = response.json()
        assert body["igdb_metadata"] == {}

    def test_update_rom_empty_raw_metadata(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        """Test that empty raw metadata is handled correctly."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"raw_igdb_metadata": ""},
        )
        assert response.status_code == status.HTTP_200_OK
        # Empty string should be ignored, so igdb_metadata should remain unchanged
        body = response.json()
        assert body["igdb_metadata"] == {}


class TestUnmatchMetadata:
    @patch.object(
        IGDBHandler, "get_rom_by_id", return_value=IGDBRom(igdb_id=MOCK_IGDB_ID)
    )
    def test_update_rom_unmatch_metadata(
        self,
        get_rom_by_id_mock: AsyncMock,
        client: TestClient,
        access_token: str,
        rom: Rom,
    ):
        """Test the unmatch_metadata functionality that clears all metadata."""
        # Verify the ROM has existing metadata
        initial_response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"igdb_id": str(MOCK_IGDB_ID)},
        )
        assert initial_response.status_code == status.HTTP_200_OK
        assert get_rom_by_id_mock.called

        initial_body = initial_response.json()
        assert initial_body["igdb_id"] == MOCK_IGDB_ID
        assert initial_body["igdb_metadata"] is not None

        # Now unmatch all metadata
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"unmatch_metadata": True},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()

        assert body["igdb_id"] is None
        assert body["moby_id"] is None
        assert body["ss_id"] is None
        assert body["ra_id"] is None
        assert body["launchbox_id"] is None
        assert body["hasheous_id"] is None
        assert body["tgdb_id"] is None
        assert body["flashpoint_id"] is None
        assert body["hltb_id"] is None

        assert body["name"] == rom.fs_name
        assert body["summary"] == ""
        assert body["url_cover"] == ""
        assert body["slug"] == ""

        assert body["igdb_metadata"] == {}
        assert body["moby_metadata"] == {}
        assert body["ss_metadata"] == {}
        assert body["merged_ra_metadata"] == {}  # Special case
        assert body["launchbox_metadata"] == {}
        assert body["hasheous_metadata"] == {}
        assert body["flashpoint_metadata"] == {}
        assert body["hltb_metadata"] == {}

    def test_update_rom_unmatch_metadata_with_other_data(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        """Test that unmatch_metadata works even when other data is provided."""
        response = client.put(
            f"/api/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"unmatch_metadata": True},
            data={
                "igdb_id": str(MOCK_IGDB_ID),  # This should be ignored
                "name": "Should be ignored",  # This should be ignored
                "summary": "Should be ignored",  # This should be ignored
            },
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()

        # All metadata should still be cleared despite other data being provided
        assert body["igdb_id"] is None
        assert body["name"] == rom.fs_name
        assert body["summary"] == ""
