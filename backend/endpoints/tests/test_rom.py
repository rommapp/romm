import json
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

client = TestClient(app)


def test_get_rom(access_token, rom):
    response = client.get(
        f"/platforms/{rom.p_slug}/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == rom.id


def test_get_all_roms(access_token, rom):
    response = client.get(
        f"/platforms/{rom.p_slug}/roms",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == rom.id


@patch("utils.fs.rename_rom")
def test_update_rom(rename_rom, access_token, rom):
    response = client.patch(
        f"/platforms/{rom.p_slug}/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        data={
            "r_igdb_id": "236663",
            "r_name": "Metroid Prime Remastered",
            "r_slug": "metroid-prime-remastered",
            "file_name": "Metroid Prime Remastered.xci",
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
    assert body["rom"]["file_name"] == "Metroid Prime Remastered.xci"

    assert rename_rom.called


def test_delete_roms(access_token, rom):
    response = client.delete(
        f"/platforms/{rom.p_slug}/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == f"{rom.file_name} deleted successfully!"
