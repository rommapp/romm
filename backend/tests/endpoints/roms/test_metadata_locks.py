from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from models.rom import Rom


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_update_metadata_locks_snapshots_and_exposes_only_names(
    client: TestClient, access_token: str, rom: Rom
):
    db_rom_handler.update_rom(rom.id, {"igdb_metadata": {"genres": ["Action"]}})
    response = client.put(
        f"/api/roms/{rom.id}/metadata-locks",
        headers=_auth(access_token),
        json={"fields": ["genres"], "locked": True},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"locked_fields": ["genres"]}
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    assert refreshed.metadata_locks == {"genres": ["Action"]}

    db_rom_handler.update_rom(rom.id, {"igdb_metadata": {"genres": ["Puzzle"]}})
    response = client.get(f"/api/roms/{rom.id}", headers=_auth(access_token))
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["metadata_locked_fields"] == ["genres"]
    assert "metadata_locks" not in payload
    assert payload["metadatum"]["genres"] == ["Action"]


def test_metadata_locks_require_roms_write(
    client: TestClient, viewer_access_token: str, rom: Rom
):
    response = client.put(
        f"/api/roms/{rom.id}/metadata-locks",
        headers=_auth(viewer_access_token),
        json={"fields": ["name"], "locked": True},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_metadata_locks_reject_unknown_fields(
    client: TestClient, access_token: str, rom: Rom
):
    response = client.put(
        f"/api/roms/{rom.id}/metadata-locks",
        headers=_auth(access_token),
        json={"fields": ["igdb_id"], "locked": True},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_bulk_metadata_locks_can_target_platform_or_library(
    client: TestClient, access_token: str, rom: Rom
):
    for payload in (
        {"fields": ["summary"], "locked": True, "platform_id": rom.platform_id},
        {"fields": ["summary"], "locked": False, "all": True},
    ):
        response = client.put(
            "/api/roms/metadata-locks",
            headers=_auth(access_token),
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"updated": 1, "failed": 0}
