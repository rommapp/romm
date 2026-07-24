import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from models.rom import Rom, RomFile, RomFileCategory


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
