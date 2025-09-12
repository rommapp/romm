from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from handler.filesystem.roms_handler import FSRomsHandler
from handler.metadata.igdb_handler import IGDBHandler, IGDBRom


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_get_rom(client, access_token, rom):
    response = client.get(
        f"/api/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["id"] == rom.id


def test_get_all_roms(client, access_token, rom, platform):
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
def test_update_rom(rename_fs_rom_mock, get_rom_by_id_mock, client, access_token, rom):
    response = client.put(
        f"/api/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        data={
            "igdb_id": "236663",
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
            "first_release_date": 1675814400,
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


def test_delete_roms(client, access_token, rom):
    response = client.post(
        "/api/roms/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"roms": [rom.id], "delete_from_fs": []},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["successful_items"] == 1
