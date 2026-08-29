from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def walkthrough_file(game_folder_rom: Rom) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=game_folder_rom.id,
            file_name="guide.txt",
            file_path=f"{game_folder_rom.full_path}/walkthrough",
            file_size_bytes=10,
            category=RomFileCategory.WALKTHROUGH,
        )
    )


def test_get_progress_defaults_to_zero(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_file: RomFile,
):
    response = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_file.id}/progress",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["progress"] == 0.0
    assert body["finished"] is False


def test_put_then_get_progress_roundtrip(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_file: RomFile,
):
    put = client.put(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_file.id}/progress",
        headers=_auth(access_token),
        json={"progress": 0.42, "last_page": 3, "finished": False},
    )
    assert put.status_code == status.HTTP_200_OK
    assert put.json()["progress"] == pytest.approx(0.42)
    assert put.json()["last_page"] == 3

    got = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_file.id}/progress",
        headers=_auth(access_token),
    )
    assert got.json()["progress"] == pytest.approx(0.42)
    assert got.json()["last_page"] == 3


def test_put_progress_clamps_out_of_range(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_file: RomFile,
):
    put = client.put(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_file.id}/progress",
        headers=_auth(access_token),
        json={"progress": 5.0},
    )
    assert put.status_code == status.HTTP_200_OK
    assert put.json()["progress"] == 1.0


def test_put_progress_rejects_oversized_last_page(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_file: RomFile,
):
    """Out of range must be a 400, not an integer-column overflow at insert."""
    put = client.put(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_file.id}/progress",
        headers=_auth(access_token),
        json={"last_page": 2**40},
    )
    assert put.status_code == status.HTTP_400_BAD_REQUEST


def test_put_progress_requires_the_self_service_write_scope(
    client: TestClient,
    admin_user: User,
    game_folder_rom: Rom,
    walkthrough_file: RomFile,
):
    """Writing progress needs ROMS_USER_WRITE, which a read-only token lacks.

    Every signed-in user holds it (it is self-service, like notes), but the
    kiosk guest is capped to the read scopes and so must not be able to write.
    """
    read_only = oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": str(Scope.ROMS_READ),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )

    put = client.put(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_file.id}/progress",
        headers=_auth(read_only),
        json={"progress": 0.5},
    )
    assert put.status_code == status.HTTP_403_FORBIDDEN

    # The read scope is still enough to read progress back.
    got = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_file.id}/progress",
        headers=_auth(read_only),
    )
    assert got.status_code == status.HTTP_200_OK


def test_progress_rejects_non_document_file(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
):
    game_file = db_rom_handler.get_rom_files_by_category(
        game_folder_rom.id, RomFileCategory.GAME
    )[0]
    response = client.put(
        f"/api/roms/{game_folder_rom.id}/files/{game_file.id}/progress",
        headers=_auth(access_token),
        json={"progress": 0.5},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
