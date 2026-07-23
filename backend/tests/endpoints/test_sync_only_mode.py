import pytest
from fastapi import status
from fastapi.testclient import TestClient

from models.platform import Platform
from models.rom import Rom


@pytest.fixture
def sync_only_mode(monkeypatch):
    # The route dependency and inline guards read the flag off the config
    # module at request time; the heartbeat endpoint binds it at import.
    monkeypatch.setattr("config.SYNC_ONLY_MODE", True)
    monkeypatch.setattr("endpoints.heartbeat.SYNC_ONLY_MODE", True)


def test_heartbeat_exposes_sync_only_mode(client: TestClient, sync_only_mode):
    response = client.get("/api/heartbeat")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["SYSTEM"]["SYNC_ONLY_MODE"] is True
    assert body["EMULATION"]["DISABLE_EMULATOR_JS"] is True
    assert body["EMULATION"]["DISABLE_RUFFLE_RS"] is True


def test_heartbeat_defaults_to_sync_only_mode_off(client: TestClient):
    response = client.get("/api/heartbeat")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["SYSTEM"]["SYNC_ONLY_MODE"] is False


def test_fs_centric_routers_are_hidden(
    client: TestClient, access_token: str, sync_only_mode
):
    headers = {"Authorization": f"Bearer {access_token}"}

    assert (
        client.get("/api/feeds/webrcade", headers=headers).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.get("/api/firmware", headers=headers).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_rom_content_download_is_hidden(
    client: TestClient, access_token: str, rom: Rom, sync_only_mode
):
    response = client.get(
        f"/api/roms/{rom.id}/content/{rom.fs_name}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Not available in sync-only mode"


def test_rom_listing_and_resolve_stay_available(
    client: TestClient, access_token: str, platform: Platform, rom: Rom, sync_only_mode
):
    headers = {"Authorization": f"Bearer {access_token}"}

    listing = client.get(f"/api/roms/{rom.id}", headers=headers)
    assert listing.status_code == status.HTTP_200_OK

    resolved = client.post(
        "/api/roms/resolve",
        json={"platform_slug": platform.fs_slug, "fs_name": "some_game.gba"},
        headers=headers,
    )
    assert resolved.status_code == status.HTTP_200_OK
    assert resolved.json()["is_virtual"] is True
