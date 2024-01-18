import json
from fastapi.testclient import TestClient
from unittest.mock import patch

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
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == rom.id


@patch("endpoints.rom.fs_rom_handler.rename_file")
def test_update_rom(update_rom, access_token, rom):
    response = client.put(
        f"/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rename_as_igdb": True},
        data={
            "igdb_id": "236663",
            "name": "Metroid Prime Remastered",
            "slug": "metroid-prime-remastered",
            "file_name": "Metroid Prime Remastered.zip",
            "summary": "summary test",
            "url_cover": "https://images.igdb.com/igdb/image/upload/t_cover_big/co2l7z.jpg",
            "url_screenshots": json.dumps(
                [
                    "https://images.igdb.com/igdb/image/upload/t_original/qhiqlmwvvuaqxxn4cxlr.jpg",
                    "https://images.igdb.com/igdb/image/upload/t_original/kqkixazzsokqgoxmuish.jpg",
                ]
            ),
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["file_name"] == "Metroid Prime Remastered.zip"

    assert update_rom.called


def test_delete_roms(access_token, rom):
    response = client.post(
        "/roms/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"roms": [rom.id], "delete_from_fs": False},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "1 roms deleted successfully!"
