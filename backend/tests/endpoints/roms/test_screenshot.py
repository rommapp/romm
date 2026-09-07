from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.roms import screenshot as screenshot_endpoint
from handler.database import db_rom_handler
from models.rom import Rom, RomFile, RomFileCategory

PNG_BYTES = b"\x89PNG\r\n\x1a\n fake png payload"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def screenshot_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    folder_dir = tmp_path / "library"
    folder_dir.mkdir()

    def validate_path(path: str) -> Path:
        return folder_dir / Path(path).name

    async def remove_file(path: str) -> None:
        target = folder_dir / Path(path).name
        if target.exists():
            target.unlink()
        else:
            raise FileNotFoundError(path)

    monkeypatch.setattr(
        screenshot_endpoint.fs_rom_handler, "validate_path", validate_path
    )
    monkeypatch.setattr(
        screenshot_endpoint.fs_rom_handler,
        "make_directory",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        screenshot_endpoint.fs_rom_handler,
        "remove_file",
        AsyncMock(side_effect=remove_file),
    )
    return folder_dir


# ---------- POST /api/roms/{id}/screenshots ----------


def test_upload_screenshot_success(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    screenshot_fs: Path,
):
    response = client.post(
        f"/api/roms/{game_folder_rom.id}/screenshots",
        headers={**_auth(access_token), "x-upload-filename": "shot1.png"},
        files={"shot1.png": ("shot1.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == status.HTTP_201_CREATED
    written = screenshot_fs / "shot1.png"
    assert written.exists()
    assert written.read_bytes() == PNG_BYTES

    rom_after = db_rom_handler.get_rom(game_folder_rom.id)
    screenshots = [
        f for f in rom_after.files if f.category == RomFileCategory.SCREENSHOT
    ]
    assert len(screenshots) == 1
    assert screenshots[0].file_name == "shot1.png"
    assert screenshots[0].file_path == f"{game_folder_rom.full_path}/screenshots"
    assert screenshots[0].file_size_bytes == len(PNG_BYTES)


def test_upload_screenshot_upserts_on_reupload(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    screenshot_fs: Path,
):
    for _ in range(2):
        response = client.post(
            f"/api/roms/{game_folder_rom.id}/screenshots",
            headers={**_auth(access_token), "x-upload-filename": "shot1.png"},
            files={"shot1.png": ("shot1.png", PNG_BYTES, "image/png")},
        )
        assert response.status_code == status.HTTP_201_CREATED

    rom_after = db_rom_handler.get_rom(game_folder_rom.id)
    screenshots = [
        f for f in rom_after.files if f.category == RomFileCategory.SCREENSHOT
    ]
    assert len(screenshots) == 1


# Single-file auto-convert on upload is covered in test_convert_to_folder.py.


def test_upload_screenshot_rejects_invalid_extension(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    screenshot_fs: Path,
):
    response = client.post(
        f"/api/roms/{game_folder_rom.id}/screenshots",
        headers={**_auth(access_token), "x-upload-filename": "notes.txt"},
        files={"notes.txt": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported image file type" in response.json()["detail"]


# ---------- DELETE /api/roms/{id}/screenshots/{file_id} ----------


def test_delete_screenshot_success(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    screenshot_fs: Path,
):
    (screenshot_fs / "shot1.png").write_bytes(PNG_BYTES)
    shot = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=game_folder_rom.id,
            file_name="shot1.png",
            file_path=f"{game_folder_rom.full_path}/screenshots",
            file_size_bytes=len(PNG_BYTES),
            category=RomFileCategory.SCREENSHOT,
        )
    )

    response = client.delete(
        f"/api/roms/{game_folder_rom.id}/screenshots/{shot.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(shot.id) is None
    assert not (screenshot_fs / "shot1.png").exists()


def test_delete_screenshot_wrong_rom_returns_404(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    rom: Rom,
    screenshot_fs: Path,
):
    shot = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=game_folder_rom.id,
            file_name="shot1.png",
            file_path=f"{game_folder_rom.full_path}/screenshots",
            file_size_bytes=len(PNG_BYTES),
            category=RomFileCategory.SCREENSHOT,
        )
    )

    response = client.delete(
        f"/api/roms/{rom.id}/screenshots/{shot.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_screenshot_wrong_category_returns_404(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    screenshot_fs: Path,
):
    not_screenshot = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=game_folder_rom.id,
            file_name="english.pdf",
            file_path=f"{game_folder_rom.full_path}/manual",
            file_size_bytes=10,
            category=RomFileCategory.MANUAL,
        )
    )

    response = client.delete(
        f"/api/roms/{game_folder_rom.id}/screenshots/{not_screenshot.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
