from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.roms import files as files_endpoint
from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _add_file(rom: Rom, name: str, category: RomFileCategory | None) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=name,
            file_path=f"{rom.fs_path}/{rom.fs_name}",
            file_size_bytes=10,
            category=category,
        )
    )


def _make_rom(admin_user: User, platform: Platform) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="media_rom",
            slug="media_rom_slug",
            fs_name="media_rom",
            fs_name_no_tags="media_rom",
            fs_name_no_ext="media_rom",
            fs_extension="",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    return rom


def test_image_file_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "trailer_thumb.png", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/trailer_thumb.png",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("image/png")
    assert r.headers["content-disposition"].startswith("inline")


def test_video_file_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "trailer.mp4", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/trailer.mp4",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("video/mp4")
    assert r.headers["content-disposition"].startswith("inline")


def test_pdf_manual_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "manual.pdf", RomFileCategory.MANUAL)

    r = client.get(
        f"/api/roms/{file.id}/files/content/manual.pdf",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_markdown_manual_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "manual.md", RomFileCategory.MANUAL)

    r = client.get(
        f"/api/roms/{file.id}/files/content/manual.md",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.headers["content-disposition"].startswith("inline")
    # nosniff keeps the browser from sniffing the Markdown into HTML.
    assert r.headers["x-content-type-options"] == "nosniff"


def test_non_manual_document_served_as_attachment(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    # A game/extra file that happens to end in .pdf must still download; only
    # manual-category documents are served inline.
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "readme.pdf", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/readme.pdf",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert r.headers["content-disposition"].startswith("attachment")


def test_rom_file_served_as_attachment(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "game.bin", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/game.bin",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert r.headers["content-disposition"].startswith("attachment")


def test_content_type_derived_from_db_not_path_param(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    # A caller must not be able to force an inline image content-type on a
    # non-media file by tacking a fake extension onto the URL path param.
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "game.bin", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/game.bin.png",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert r.headers["content-disposition"].startswith("attachment")


# ---------- DELETE /api/roms/{rom_id}/files/{file_id} ----------


@pytest.fixture
def files_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock fs_rom_handler so file operations hit a temporary directory."""
    library_dir = tmp_path / "library"
    library_dir.mkdir()

    def validate_path(path: str) -> Path:
        return library_dir / Path(path).name

    async def remove_file(path: str) -> None:
        target = library_dir / Path(path).name
        if target.exists():
            target.unlink()
        else:
            raise FileNotFoundError(path)

    monkeypatch.setattr(files_endpoint.fs_rom_handler, "validate_path", validate_path)
    monkeypatch.setattr(
        files_endpoint.fs_rom_handler,
        "remove_file",
        AsyncMock(side_effect=remove_file),
    )
    return library_dir


def test_delete_rom_file_success(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    files_fs: Path,
):
    rom = _make_rom(admin_user, platform)
    (files_fs / "game.bin").write_bytes(b"\x00" * 16)
    rom_file = _add_file(rom, "game.bin", RomFileCategory.GAME)

    response = client.delete(
        f"/api/roms/{rom.id}/files/{rom_file.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(rom_file.id) is None
    assert not (files_fs / "game.bin").exists()


def test_delete_rom_file_wrong_rom_returns_404(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    files_fs: Path,
):
    rom_a = _make_rom(admin_user, platform)
    # Use the game_folder_rom fixture name to avoid a duplicate fs_name constraint;
    # create a second ROM directly with a distinct slug and fs_name.
    rom_b = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="other_rom",
            slug="other_rom_slug",
            fs_name="other_rom",
            fs_name_no_tags="other_rom",
            fs_name_no_ext="other_rom",
            fs_extension="",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom_b.id, user_id=admin_user.id)
    rom_file = _add_file(rom_a, "game.bin", RomFileCategory.GAME)

    response = client.delete(
        f"/api/roms/{rom_b.id}/files/{rom_file.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    # File must NOT have been deleted from the database.
    assert db_rom_handler.get_rom_file_by_id(rom_file.id) is not None


def test_delete_rom_file_unknown_file_returns_404(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    files_fs: Path,
):
    rom = _make_rom(admin_user, platform)

    response = client.delete(
        f"/api/roms/{rom.id}/files/999999",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_rom_file_tolerates_missing_disk_file(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    files_fs: Path,
):
    """DB row must be dropped even when the on-disk file is already gone."""
    rom = _make_rom(admin_user, platform)
    rom_file = _add_file(rom, "missing.bin", RomFileCategory.GAME)

    response = client.delete(
        f"/api/roms/{rom.id}/files/{rom_file.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(rom_file.id) is None


def test_delete_rom_file_forbidden_viewer(
    client: TestClient,
    viewer_access_token: str,
    admin_user: User,
    platform: Platform,
    files_fs: Path,
):
    rom = _make_rom(admin_user, platform)
    rom_file = _add_file(rom, "game.bin", RomFileCategory.GAME)

    response = client.delete(
        f"/api/roms/{rom.id}/files/{rom_file.id}",
        headers=_auth(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    # File must NOT have been deleted.
    assert db_rom_handler.get_rom_file_by_id(rom_file.id) is not None
