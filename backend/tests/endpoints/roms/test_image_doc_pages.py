import zipfile
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from tests.auth_helpers import bearer, hide, user_headers

from handler.database import db_rom_handler
from handler.filesystem import fs_resource_handler
from models.permission import PermEntity
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User
from utils import image_docs

PAGES = {"02.png": b"\x89PNG second", "01.jpg": b"\xff\xd8 first"}


def _write_cbz(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in PAGES.items():
            archive.writestr(name, data)
        archive.writestr("ComicInfo.xml", b"<ComicInfo/>")


def _add_document(
    rom: Rom, folder: str, name: str, category: RomFileCategory
) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=name,
            file_path=f"{rom.full_path}/{folder}",
            file_size_bytes=10,
            category=category,
        )
    )


@pytest.fixture
def walkthrough_image_doc(game_folder_rom: Rom, game_folder_on_disk: Path) -> RomFile:
    _write_cbz(game_folder_on_disk / "walkthrough" / "guide.cbz")
    return _add_document(
        game_folder_rom, "walkthrough", "guide.cbz", RomFileCategory.WALKTHROUGH
    )


@pytest.fixture
def resources_image_doc_manual(rom: Rom, tmp_path: Path, mocker: MockerFixture) -> Path:
    path = tmp_path / "resources" / f"{rom.id}.cbz"
    _write_cbz(path)
    mocker.patch.object(fs_resource_handler, "validate_path", lambda _p: path)
    db_rom_handler.update_rom(
        rom.id, {"path_manual": f"{rom.fs_resources_path}/manual/{rom.id}.cbz"}
    )
    return path


# ---------- /api/roms/{rom_id}/files/{file_id}/pages ----------


def test_file_pages_counts_only_images(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_image_doc: RomFile,
):
    response = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_image_doc.id}/pages",
        headers=bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"count": 2}


def test_file_page_serves_image_in_reading_order(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_image_doc: RomFile,
):
    base = f"/api/roms/{game_folder_rom.id}/files/{walkthrough_image_doc.id}/pages"

    first = client.get(f"{base}/1", headers=bearer(access_token))
    second = client.get(f"{base}/2", headers=bearer(access_token))

    assert first.status_code == status.HTTP_200_OK
    assert first.content == PAGES["01.jpg"]
    assert first.headers["content-type"] == "image/jpeg"
    assert first.headers["x-content-type-options"] == "nosniff"
    assert second.content == PAGES["02.png"]
    assert second.headers["content-type"] == "image/png"


def test_file_page_past_the_end_returns_404(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_image_doc: RomFile,
):
    response = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_image_doc.id}/pages/3",
        headers=bearer(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_file_pages_reject_a_non_image_doc_document(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    game_folder_on_disk: Path,
):
    pdf = _add_document(game_folder_rom, "manual", "manual.pdf", RomFileCategory.MANUAL)

    response = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{pdf.id}/pages",
        headers=bearer(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_file_pages_reject_a_game_file(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    game_folder_on_disk: Path,
):
    game = _add_document(game_folder_rom, "", "extra.cbz", RomFileCategory.GAME)

    response = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{game.id}/pages/1",
        headers=bearer(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_file_pages_of_a_non_archive_count_none(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    game_folder_on_disk: Path,
):
    broken = game_folder_on_disk / "walkthrough" / "broken.cbr"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_bytes(b"not an archive")
    rom_file = _add_document(
        game_folder_rom, "walkthrough", "broken.cbr", RomFileCategory.WALKTHROUGH
    )

    response = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{rom_file.id}/pages",
        headers=bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"count": 0}


def test_file_page_past_the_size_cap_returns_422(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    walkthrough_image_doc: RomFile,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(image_docs, "MAX_IMAGE_DOC_PAGE_BYTES", 4)

    response = client.get(
        f"/api/roms/{game_folder_rom.id}/files/{walkthrough_image_doc.id}/pages/1",
        headers=bearer(access_token),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_file_pages_404_on_a_hidden_rom(
    client: TestClient,
    editor_user: User,
    game_folder_rom: Rom,
    walkthrough_image_doc: RomFile,
):
    hide(PermEntity.ROMS, game_folder_rom.id, user_id=editor_user.id)
    base = f"/api/roms/{game_folder_rom.id}/files/{walkthrough_image_doc.id}/pages"

    count = client.get(base, headers=user_headers(editor_user))
    page = client.get(f"{base}/1", headers=user_headers(editor_user))

    assert count.status_code == status.HTTP_404_NOT_FOUND
    assert page.status_code == status.HTTP_404_NOT_FOUND


# ---------- /api/roms/{id}/manuals/pages ----------


def test_manual_pages_read_the_resources_manual(
    client: TestClient,
    access_token: str,
    rom: Rom,
    resources_image_doc_manual: Path,
):
    count = client.get(
        f"/api/roms/{rom.id}/manuals/pages", headers=bearer(access_token)
    )
    page = client.get(
        f"/api/roms/{rom.id}/manuals/pages/2", headers=bearer(access_token)
    )

    assert count.json() == {"count": 2}
    assert page.status_code == status.HTTP_200_OK
    assert page.content == PAGES["02.png"]


def test_manual_pages_404_when_the_manual_is_not_an_image_doc(
    client: TestClient,
    access_token: str,
    rom: Rom,
):
    db_rom_handler.update_rom(
        rom.id, {"path_manual": f"{rom.fs_resources_path}/manual/{rom.id}.pdf"}
    )

    response = client.get(
        f"/api/roms/{rom.id}/manuals/pages", headers=bearer(access_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_manual_pages_404_on_a_hidden_rom(
    client: TestClient,
    editor_user: User,
    rom: Rom,
    resources_image_doc_manual: Path,
):
    hide(PermEntity.ROMS, rom.id, user_id=editor_user.id)

    response = client.get(
        f"/api/roms/{rom.id}/manuals/pages/1", headers=user_headers(editor_user)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- uploads accept image docs ----------


@pytest.mark.parametrize("name", ["issue.cbz", "issue.cbr"])
def test_walkthrough_upload_accepts_image_docs(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    game_folder_on_disk: Path,
    name: str,
):
    (game_folder_on_disk / "walkthrough").mkdir()

    response = client.post(
        f"/api/roms/{game_folder_rom.id}/walkthroughs/files",
        headers={**bearer(access_token), "x-upload-filename": name},
        files={name: (name, b"PK\x03\x04", "application/octet-stream")},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert (game_folder_on_disk / "walkthrough" / name).exists()


@pytest.mark.parametrize("name", ["issue.cbz", "issue.cbr"])
def test_manual_folder_upload_accepts_image_docs(
    client: TestClient,
    access_token: str,
    game_folder_rom: Rom,
    game_folder_on_disk: Path,
    name: str,
):
    (game_folder_on_disk / "manual").mkdir()

    response = client.post(
        f"/api/roms/{game_folder_rom.id}/manuals/files",
        headers={**bearer(access_token), "x-upload-filename": name},
        files={name: (name, b"PK\x03\x04", "application/octet-stream")},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert (game_folder_on_disk / "manual" / name).exists()
