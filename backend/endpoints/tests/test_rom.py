from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from handler.filesystem.roms_handler import FSRomsHandler
from handler.metadata.igdb_handler import IGDBBaseHandler, IGDBRom
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_get_rom(client, access_token, rom):
    response = client.get(
        f"/api/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == rom.id


def test_get_all_roms(client, access_token, rom, platform):
    response = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"platform_id": platform.id},
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == rom.id


@patch.object(FSRomsHandler, "rename_file")
@patch.object(IGDBBaseHandler, "get_rom_by_id", return_value=IGDBRom(igdb_id=None))
def test_update_rom(rename_file_mock, get_rom_by_id_mock, client, access_token, rom):
    response = client.put(
        f"/api/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rename_as_source": True},
        data={
            "igdb_id": "236663",
            "name": "Metroid Prime Remastered",
            "slug": "metroid-prime-remastered",
            "file_name": "Metroid Prime Remastered.zip",
            "summary": "summary test",
            "url_cover": "https://images.igdb.com/igdb/image/upload/t_cover_big/co2l7z.jpg",
            "genres": '[{"id": 5, "name": "Shooter"}, {"id": 8, "name": "Platform"}, {"id": 31, "name": "Adventure"}]',
            "franchises": '[{"id": 756, "name": "Metroid"}]',
            "collections": '[{"id": 243, "name": "Metroid"}, {"id": 6240, "name": "Metroid Prime"}]',
            "expansions": "[]",
            "dlcs": "[]",
            "companies": '[{"id": 203227, "company": {"id": 70, "name": "Nintendo"}}, {"id": 203307, "company": {"id": 766, "name": "Retro Studios"}}]',
            "first_release_date": 1675814400,
            "remasters": "[]",
            "remakes": "[]",
            "expanded_games": "[]",
            "ports": "[]",
            "similar_games": "[]",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["file_name"] == "Metroid Prime Remastered.zip"

    assert rename_file_mock.called
    assert get_rom_by_id_mock.called


def test_delete_roms(client, access_token, rom):
    response = client.post(
        "/api/roms/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"roms": [rom.id], "delete_from_fs": []},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "1 roms deleted successfully!"
