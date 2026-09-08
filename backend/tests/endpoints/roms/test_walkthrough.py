from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.roms import walkthrough as walkthrough_endpoint
from handler.database import db_rom_handler
from models.rom import DocSource, Rom, RomFile, RomFileCategory

TXT_BYTES = b"Chrono Trigger walkthrough\n\nStep 1: leave home.\n"
GAMEFAQS_URL = "https://gamefaqs.gamespot.com/snes/563538-chrono-trigger/faqs/1"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def walkthrough_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Mock fs_rom_handler so walkthrough writes land in tmp_path."""
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

    async def write_file(file, path: str, filename: str) -> None:
        (folder_dir / filename).write_bytes(file)

    monkeypatch.setattr(
        walkthrough_endpoint.fs_rom_handler, "validate_path", validate_path
    )
    monkeypatch.setattr(
        walkthrough_endpoint.fs_rom_handler,
        "make_directory",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        walkthrough_endpoint.fs_rom_handler,
        "remove_file",
        AsyncMock(side_effect=remove_file),
    )
    monkeypatch.setattr(
        walkthrough_endpoint.fs_rom_handler,
        "write_file",
        AsyncMock(side_effect=write_file),
    )
    return folder_dir


# ---------- POST /api/roms/{id}/walkthroughs/files ----------


def test_upload_walkthrough_file_success(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_fs: Path,
):
    response = client.post(
        f"/api/roms/{game_folder_rom.id}/walkthroughs/files",
        headers={
            **_auth(access_token),
            "x-upload-filename": "guide.txt",
            "x-doc-author": "John%20Doe",
            "x-doc-title": "Full%20Walkthrough",
        },
        files={"guide.txt": ("guide.txt", TXT_BYTES, "text/plain")},
    )

    assert response.status_code == status.HTTP_201_CREATED

    files = db_rom_handler.get_rom_files_by_category(
        game_folder_rom.id, RomFileCategory.WALKTHROUGH
    )
    assert len(files) == 1
    created = files[0]
    assert created.file_name == "guide.txt"
    assert created.doc_meta is not None
    assert created.doc_meta.source == DocSource.UPLOAD
    assert created.doc_meta.author == "John Doe"
    assert created.doc_meta.title == "Full Walkthrough"


def test_upload_walkthrough_rejects_unsupported_extension(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_fs: Path,
):
    response = client.post(
        f"/api/roms/{game_folder_rom.id}/walkthroughs/files",
        headers={**_auth(access_token), "x-upload-filename": "guide.exe"},
        files={"guide.exe": ("guide.exe", b"nope", "application/octet-stream")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported walkthrough file type" in response.json()["detail"]


def test_upload_walkthrough_rom_not_found(
    client: TestClient,
    access_token: str,
    walkthrough_fs: Path,
):
    response = client.post(
        "/api/roms/999999/walkthroughs/files",
        headers={**_auth(access_token), "x-upload-filename": "guide.txt"},
        files={"guide.txt": ("guide.txt", TXT_BYTES, "text/plain")},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- DELETE /api/roms/{id}/walkthroughs/files/{file_id} ----------


def test_delete_walkthrough_file(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_fs: Path,
):
    (walkthrough_fs / "guide.txt").write_bytes(TXT_BYTES)
    rom_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=game_folder_rom.id,
            file_name="guide.txt",
            file_path=f"{game_folder_rom.full_path}/walkthrough",
            file_size_bytes=len(TXT_BYTES),
            category=RomFileCategory.WALKTHROUGH,
        )
    )

    response = client.delete(
        f"/api/roms/{game_folder_rom.id}/walkthroughs/files/{rom_file.id}",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(rom_file.id) is None


def test_delete_walkthrough_rejects_non_walkthrough_file(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_fs: Path,
):
    game_file = db_rom_handler.get_rom_files_by_category(
        game_folder_rom.id, RomFileCategory.GAME
    )[0]

    response = client.delete(
        f"/api/roms/{game_folder_rom.id}/walkthroughs/files/{game_file.id}",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- POST /api/roms/{id}/walkthroughs/gamefaqs ----------


def test_add_gamefaqs_walkthrough_success(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_fs: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        walkthrough_endpoint,
        "fetch_gamefaqs_guide",
        AsyncMock(
            return_value={
                "title": "Chrono Trigger FAQ",
                "author": "Jane Roe",
                "text": "This is the guide body.",
            }
        ),
    )

    response = client.post(
        f"/api/roms/{game_folder_rom.id}/walkthroughs/gamefaqs",
        headers=_auth(access_token),
        json={"url": GAMEFAQS_URL},
    )

    assert response.status_code == status.HTTP_201_CREATED

    files = db_rom_handler.get_rom_files_by_category(
        game_folder_rom.id, RomFileCategory.WALKTHROUGH
    )
    assert len(files) == 1
    created = files[0]
    assert created.file_name == "chrono-trigger-faq.txt"
    assert created.doc_meta.source == DocSource.GAMEFAQS
    assert created.doc_meta.source_url == GAMEFAQS_URL
    assert created.doc_meta.author == "Jane Roe"
    assert (walkthrough_fs / "chrono-trigger-faq.txt").read_bytes() == (
        b"This is the guide body."
    )


def test_add_gamefaqs_walkthrough_rejects_bad_host(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_fs: Path,
):
    response = client.post(
        f"/api/roms/{game_folder_rom.id}/walkthroughs/gamefaqs",
        headers=_auth(access_token),
        json={"url": "https://evil.example.com/guide"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
