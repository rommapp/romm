import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity
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


def test_metadata_locks_survive_editing_rom(
    client: TestClient, access_token: str, rom: Rom
):
    fields = ["name", "summary", "genres"]
    locked = client.put(
        f"/api/roms/{rom.id}/metadata-locks",
        headers=_auth(access_token),
        json={"fields": fields, "locked": True},
    )
    assert locked.status_code == status.HTTP_200_OK

    response = client.put(
        f"/api/roms/{rom.id}",
        headers=_auth(access_token),
        data={"summary": "hello world", "raw_manual_metadata": "{}"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(response.json()["metadata_locked_fields"]) == set(fields)
    stored = db_rom_handler.get_rom(rom.id)
    assert stored is not None
    assert stored.metadata_locks["summary"] == "hello world"


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


@pytest.mark.parametrize("target", ["platform", "all"])
def test_bulk_metadata_locks_skip_roms_hidden_from_editor(
    client: TestClient,
    editor_access_token: str,
    editor_user,
    rom: Rom,
    second_rom: Rom,
    target: str,
):
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=PermEntity.ROMS,
                entity_id=rom.id,
                user_id=editor_user.id,
            )
        )

    target_body = (
        {"platform_id": rom.platform_id} if target == "platform" else {"all": True}
    )
    response = client.put(
        "/api/roms/metadata-locks",
        headers=_auth(editor_access_token),
        json={"fields": ["summary"], "locked": True, **target_body},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"updated": 1, "failed": 0}
    hidden_rom = db_rom_handler.get_rom(rom.id)
    visible_rom = db_rom_handler.get_rom(second_rom.id)
    assert hidden_rom is not None
    assert visible_rom is not None
    assert "summary" not in (hidden_rom.metadata_locks or {})
    assert "summary" in (visible_rom.metadata_locks or {})


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
