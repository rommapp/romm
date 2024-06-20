from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_get_rom(access_token, rom):
    response = client.get(
        f"/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == rom.id


def test_get_all_roms(access_token, rom, platform):
    response = client.get(
        "/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"platform_id": platform.id},
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == rom.id


@patch("endpoints.rom.fs_rom_handler.rename_file")
@patch("endpoints.rom.meta_igdb_handler.get_rom_by_id")
def test_update_rom(rename_file_mock, get_rom_by_id_mock, access_token, rom):
    response = client.put(
        f"/roms/{rom.id}",
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


def test_delete_roms(access_token, rom):
    response = client.post(
        "/roms/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"roms": [rom.id], "delete_from_fs": []},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "1 roms deleted successfully!"
