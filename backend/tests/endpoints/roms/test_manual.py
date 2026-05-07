from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.roms import manual as manual_endpoint
from handler.database import db_rom_handler
from models.rom import Rom, RomFile, RomFileCategory

PDF_BYTES = b"%PDF-1.4\n%mock pdf\n%%EOF"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manual_fs_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Mock fs_resource_handler so /manuals (resources path) writes to tmp_path."""
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir()

    def validate_path(path: str) -> Path:
        target = resources_dir / Path(path).name
        return target

    monkeypatch.setattr(
        manual_endpoint.fs_resource_handler, "validate_path", validate_path
    )
    monkeypatch.setattr(
        manual_endpoint.fs_resource_handler,
        "make_directory",
        AsyncMock(return_value=None),
    )
    return resources_dir


@pytest.fixture
def manual_fs_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Mock fs_rom_handler so /manuals/files (folder path) writes to tmp_path."""
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

    monkeypatch.setattr(manual_endpoint.fs_rom_handler, "validate_path", validate_path)
    monkeypatch.setattr(
        manual_endpoint.fs_rom_handler,
        "make_directory",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        manual_endpoint.fs_rom_handler,
        "remove_file",
        AsyncMock(side_effect=remove_file),
    )
    return folder_dir


# ---------- POST /api/roms/{id}/manuals (resources) ----------


def test_upload_manual_to_resources_success(
    client: TestClient,
    access_token: str,
    rom: Rom,
    manual_fs_resources: Path,
):
    response = client.post(
        f"/api/roms/{rom.id}/manuals",
        headers={**_auth(access_token), "x-upload-filename": "manual.pdf"},
        files={"manual.pdf": ("manual.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == status.HTTP_200_OK
    written = manual_fs_resources / f"{rom.id}.pdf"
    assert written.exists()
    assert written.read_bytes() == PDF_BYTES
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed.path_manual == f"{rom.fs_resources_path}/manual/{rom.id}.pdf"


def test_upload_manual_to_resources_rom_not_found(
    client: TestClient,
    access_token: str,
    manual_fs_resources: Path,
):
    response = client.post(
        "/api/roms/999999/manuals",
        headers={**_auth(access_token), "x-upload-filename": "manual.pdf"},
        files={"manual.pdf": ("manual.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- POST /api/roms/{id}/manuals/files (folder) ----------


def test_upload_manual_to_folder_success(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/manuals/files",
        headers={**_auth(access_token), "x-upload-filename": "english.pdf"},
        files={"english.pdf": ("english.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == status.HTTP_200_OK
    written = manual_fs_folder / "english.pdf"
    assert written.exists()
    assert written.read_bytes() == PDF_BYTES

    rom_after = db_rom_handler.get_rom(multi_file_rom.id)
    manual_files = [f for f in rom_after.files if f.category == RomFileCategory.MANUAL]
    assert len(manual_files) == 1
    assert manual_files[0].file_name == "english.pdf"
    assert manual_files[0].file_path == f"{multi_file_rom.full_path}/manual"
    assert manual_files[0].file_size_bytes == len(PDF_BYTES)


def test_upload_manual_to_folder_upserts_on_reupload(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    for _ in range(2):
        response = client.post(
            f"/api/roms/{multi_file_rom.id}/manuals/files",
            headers={**_auth(access_token), "x-upload-filename": "english.pdf"},
            files={"english.pdf": ("english.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == status.HTTP_200_OK

    rom_after = db_rom_handler.get_rom(multi_file_rom.id)
    manual_files = [f for f in rom_after.files if f.category == RomFileCategory.MANUAL]
    assert len(manual_files) == 1


def test_upload_manual_to_folder_rejects_single_file_rom(
    client: TestClient,
    access_token: str,
    rom: Rom,
    manual_fs_folder: Path,
):
    # Single non-nested file → has_simple_single_file is True
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=rom.fs_name,
            file_path=rom.fs_path,
            file_size_bytes=1,
            category=RomFileCategory.GAME,
        )
    )

    response = client.post(
        f"/api/roms/{rom.id}/manuals/files",
        headers={**_auth(access_token), "x-upload-filename": "manual.pdf"},
        files={"manual.pdf": ("manual.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "folder-based" in response.json()["detail"]


def test_upload_manual_to_folder_rejects_non_pdf(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/manuals/files",
        headers={**_auth(access_token), "x-upload-filename": "manual.txt"},
        files={"manual.txt": ("manual.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported manual file type" in response.json()["detail"]


# ---------- POST /api/roms/{id}/manuals/redownload ----------


def test_redownload_manual_no_url(
    client: TestClient,
    access_token: str,
    rom: Rom,
):
    response = client.post(
        f"/api/roms/{rom.id}/manuals/redownload",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "No scraped manual URL" in response.json()["detail"]


def test_redownload_manual_success(
    client: TestClient,
    access_token: str,
    rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    db_rom_handler.update_rom(
        rom.id, {"url_manual": "https://screenscraper.fr/api/manual.pdf"}
    )
    fake_path = f"{rom.fs_resources_path}/manual/{rom.id}.pdf"
    monkeypatch.setattr(
        manual_endpoint.fs_resource_handler,
        "get_manual",
        AsyncMock(return_value=fake_path),
    )

    response = client.post(
        f"/api/roms/{rom.id}/manuals/redownload",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed.path_manual == fake_path


# ---------- DELETE /api/roms/{id}/manuals (resources) ----------


def test_delete_manual_no_manual_returns_404(
    client: TestClient,
    access_token: str,
    rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        manual_endpoint.fs_resource_handler,
        "manual_exists",
        lambda _rom: False,
    )

    response = client.delete(
        f"/api/roms/{rom.id}/manuals",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_manual_success(
    client: TestClient,
    access_token: str,
    rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    db_rom_handler.update_rom(
        rom.id,
        {
            "path_manual": f"{rom.fs_resources_path}/manual/{rom.id}.pdf",
            "url_manual": "https://screenscraper.fr/api/manual.pdf",
        },
    )
    monkeypatch.setattr(
        manual_endpoint.fs_resource_handler, "manual_exists", lambda _rom: True
    )
    remove_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        manual_endpoint.fs_resource_handler, "remove_manual", remove_mock
    )

    response = client.delete(
        f"/api/roms/{rom.id}/manuals",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    remove_mock.assert_awaited_once()
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed.path_manual == ""
    assert refreshed.url_manual == ""


# ---------- DELETE /api/roms/{id}/manuals/files/{file_id} ----------


def test_delete_manual_file_success(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    file_path = f"{multi_file_rom.full_path}/manual"
    (manual_fs_folder / "english.pdf").write_bytes(PDF_BYTES)
    manual_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="english.pdf",
            file_path=file_path,
            file_size_bytes=len(PDF_BYTES),
            category=RomFileCategory.MANUAL,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/manuals/files/{manual_file.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(manual_file.id) is None
    assert not (manual_fs_folder / "english.pdf").exists()


def test_delete_manual_file_wrong_rom_returns_404(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    rom: Rom,
    manual_fs_folder: Path,
):
    manual_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="english.pdf",
            file_path=f"{multi_file_rom.full_path}/manual",
            file_size_bytes=len(PDF_BYTES),
            category=RomFileCategory.MANUAL,
        )
    )

    response = client.delete(
        f"/api/roms/{rom.id}/manuals/files/{manual_file.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_manual_file_wrong_category_returns_404(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    not_manual = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="savegame.dat",
            file_path=f"{multi_file_rom.full_path}/saves",
            file_size_bytes=10,
            category=RomFileCategory.GAME,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/manuals/files/{not_manual.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- permissions ----------


def test_upload_manual_to_resources_forbidden_viewer(
    client: TestClient,
    viewer_access_token: str,
    rom: Rom,
    manual_fs_resources: Path,
):
    response = client.post(
        f"/api/roms/{rom.id}/manuals",
        headers={
            **_auth(viewer_access_token),
            "x-upload-filename": "manual.pdf",
        },
        files={"manual.pdf": ("manual.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_upload_manual_to_folder_forbidden_viewer(
    client: TestClient,
    viewer_access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/manuals/files",
        headers={
            **_auth(viewer_access_token),
            "x-upload-filename": "english.pdf",
        },
        files={"english.pdf": ("english.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_redownload_manual_forbidden_viewer(
    client: TestClient,
    viewer_access_token: str,
    rom: Rom,
):
    response = client.post(
        f"/api/roms/{rom.id}/manuals/redownload",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_delete_manual_file_forbidden_viewer(
    client: TestClient,
    viewer_access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    manual_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="english.pdf",
            file_path=f"{multi_file_rom.full_path}/manual",
            file_size_bytes=len(PDF_BYTES),
            category=RomFileCategory.MANUAL,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/manuals/files/{manual_file.id}",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------- path traversal ----------


def test_upload_manual_file_rejects_dotdot_filename(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/manuals/files",
        headers={**_auth(access_token), "x-upload-filename": ".."},
        files={"..": ("..", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_upload_manual_file_rejects_path_components(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    """Path components in the upload filename must be rejected with 400."""
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/manuals/files",
        headers={
            **_auth(access_token),
            "x-upload-filename": "../../evil.pdf",
        },
        files={"../../evil.pdf": ("evil.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not (manual_fs_folder.parent / "evil.pdf").exists()
    assert not (manual_fs_folder / "evil.pdf").exists()


def test_delete_manual_file_tolerates_missing_disk_file(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    manual_fs_folder: Path,
):
    # Don't create the file on disk — DELETE should still drop the row.
    manual_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="missing.pdf",
            file_path=f"{multi_file_rom.full_path}/manual",
            file_size_bytes=len(PDF_BYTES),
            category=RomFileCategory.MANUAL,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/manuals/files/{manual_file.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(manual_file.id) is None
