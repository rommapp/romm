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


def test_get_all_roms(access_token, rom):
    response = client.get(
        f"/platforms/{rom.platform_slug}/roms",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == rom.id


@patch("endpoints.rom.rename_rom")
def test_update_rom(rename_rom, access_token, rom):
    response = client.patch(
        f"/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rename_as_igdb": True},
        data={
            "igdb_id": "236663",
            "name": "Metroid Prime Remastered",
            "slug": "metroid-prime-remastered",
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

    assert rename_rom.called


def test_delete_roms(access_token, rom):
    response = client.delete(
        f"/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == f"{rom.file_name} deleted successfully!"
