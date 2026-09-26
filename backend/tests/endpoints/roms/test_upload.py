import hashlib
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from config import ROM_UPLOAD_TMP_BASE
from endpoints.roms import upload as upload_endpoint
from handler import rom_upload
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from models.platform import Platform
from models.rom import DocSource, Rom, RomFile, RomFileCategory
from models.user import User


@pytest.fixture
def upload_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    uploads_tmp = tmp_path / "uploads"
    final_dir = tmp_path / "library"

    async def make_directory(_path: str) -> None:
        final_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(upload_endpoint, "ROM_UPLOAD_TMP_BASE", uploads_tmp)
    monkeypatch.setattr(fs_rom_handler, "get_roms_fs_structure", lambda _slug: "roms")
    monkeypatch.setattr(
        fs_rom_handler,
        "validate_path",
        lambda path: final_dir / Path(path).name,
    )
    monkeypatch.setattr(fs_rom_handler, "file_exists", AsyncMock(return_value=False))
    monkeypatch.setattr(
        fs_rom_handler,
        "make_directory",
        AsyncMock(side_effect=make_directory),
    )

    return {"uploads_tmp": uploads_tmp, "final_dir": final_dir}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _start_upload(
    client: TestClient,
    token: str,
    platform_id: int,
    *,
    filename: str = "game.zip",
    total_size: int = 11,
    total_chunks: int = 2,
):
    return client.post(
        "/api/roms/upload/start",
        headers={
            **_auth_headers(token),
            "x-upload-platform": str(platform_id),
            "x-upload-filename": filename,
            "x-upload-total-size": str(total_size),
            "x-upload-total-chunks": str(total_chunks),
        },
    )


def test_start_chunked_upload_success(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
):
    response = _start_upload(client, access_token, platform.id)

    assert response.status_code == status.HTTP_201_CREATED
    upload_id = response.json()["upload_id"]
    assert UUID(upload_id)


def test_start_chunked_upload_platform_not_found(
    client: TestClient,
    access_token: str,
    upload_fs: dict[str, Any],
):
    response = _start_upload(client, access_token, platform_id=999999)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Platform not found"


def test_upload_chunk_complete_success(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
):
    start_response = _start_upload(
        client,
        access_token,
        platform.id,
        filename="metroid.zip",
        total_size=11,
        total_chunks=2,
    )
    upload_id = start_response.json()["upload_id"]

    first = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )
    second = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "1"},
        content=b"GHIJK",
    )
    complete = client.post(
        f"/api/roms/upload/{upload_id}/complete",
        headers=_auth_headers(access_token),
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert complete.status_code == status.HTTP_201_CREATED

    final_file = upload_fs["final_dir"] / "metroid.zip"
    assert final_file.exists()
    assert final_file.read_bytes() == b"ABCDEFGHIJK"


def test_upload_empty_file_without_chunks(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
):
    start_response = _start_upload(
        client,
        access_token,
        platform.id,
        filename="empty.nsp",
        total_size=0,
        total_chunks=0,
    )
    assert start_response.status_code == status.HTTP_201_CREATED
    upload_id = start_response.json()["upload_id"]

    complete = client.post(
        f"/api/roms/upload/{upload_id}/complete",
        headers=_auth_headers(access_token),
    )

    assert complete.status_code == status.HTTP_201_CREATED
    final_file = upload_fs["final_dir"] / "empty.nsp"
    assert final_file.exists()
    assert final_file.read_bytes() == b""


@pytest.mark.parametrize(("total_size", "total_chunks"), [(11, 0), (0, 2)])
def test_start_with_chunks_that_do_not_match_the_size_returns_400(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
    total_size: int,
    total_chunks: int,
):
    response = _start_upload(
        client,
        access_token,
        platform.id,
        total_size=total_size,
        total_chunks=total_chunks,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Chunk count does not match the file size"


def test_upload_chunk_invalid_upload_id(client: TestClient, access_token: str):
    response = client.put(
        "/api/roms/upload/not-a-uuid",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"chunk",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid upload ID"


def test_upload_chunk_forbidden_user(
    client: TestClient,
    access_token: str,
    editor_access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(editor_access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Forbidden"


def test_upload_chunk_oversized_returns_413(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(upload_endpoint, "ROM_UPLOAD_MAX_CHUNK_SIZE", 6)

    start_response = _start_upload(
        client,
        access_token,
        platform.id,
        total_size=12,
        total_chunks=2,
    )
    upload_id = start_response.json()["upload_id"]

    response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"1234567",
    )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json()["detail"] == "Chunk exceeds maximum allowed size"


def test_complete_missing_chunks_returns_400(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    upload_response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )
    complete_response = client.post(
        f"/api/roms/upload/{upload_id}/complete",
        headers=_auth_headers(access_token),
    )

    assert upload_response.status_code == status.HTTP_200_OK
    assert complete_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Missing chunks" in complete_response.json()["detail"]


def test_complete_invalid_upload_id(client: TestClient, access_token: str):
    response = client.post(
        "/api/roms/upload/not-a-uuid/complete",
        headers=_auth_headers(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid upload ID"


def test_cancel_upload_cleans_temp_files(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    upload_response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )
    chunk_path = upload_fs["uploads_tmp"] / upload_id / "00000"
    assert chunk_path.exists()

    cancel_response = client.post(
        f"/api/roms/upload/{upload_id}/cancel",
        headers=_auth_headers(access_token),
    )

    assert upload_response.status_code == status.HTTP_200_OK
    assert cancel_response.status_code == status.HTTP_204_NO_CONTENT
    assert not chunk_path.exists()


def test_complete_after_cancel_returns_404(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict[str, Any],
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    cancel_response = client.post(
        f"/api/roms/upload/{upload_id}/cancel",
        headers=_auth_headers(access_token),
    )
    complete_response = client.post(
        f"/api/roms/upload/{upload_id}/complete",
        headers=_auth_headers(access_token),
    )

    assert cancel_response.status_code == status.HTTP_204_NO_CONTENT
    assert complete_response.status_code == status.HTTP_404_NOT_FOUND


# ---------- uploads into an existing ROM's folder ----------

ROM_FOLDER = "Multi"


@pytest.fixture
def rom_upload_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real temp library, so a completed upload lands where the scanner looks."""
    lib = tmp_path / "library"
    lib.mkdir()
    monkeypatch.setattr(upload_endpoint, "ROM_UPLOAD_TMP_BASE", tmp_path / "uploads")
    monkeypatch.setattr(fs_rom_handler, "base_path", lib.resolve())
    return lib


def _write(lib: Path, rel: str, data: bytes) -> os.stat_result:
    path = lib / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path.stat()


def _add_row(rom: Rom, lib: Path, rel: str, data: bytes) -> None:
    st = _write(lib, f"{rom.fs_path}/{rel}", data)
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=Path(rel).name,
            file_path=str(Path(rom.fs_path, rel).parent),
            file_size_bytes=st.st_size,
            last_modified=st.st_mtime,
            crc_hash="row-crc",
            md5_hash="row-md5",
            sha1_hash="row-sha1",
        )
    )


def _folder_rom(
    platform: Platform, admin_user: User, lib: Path, files: dict[str, bytes]
) -> Rom:
    """A folder ROM whose rows describe the files on disk, with stored hashes."""
    rom = Rom(
        platform_id=platform.id,
        name=ROM_FOLDER,
        slug=f"{ROM_FOLDER}_slug",
        fs_name=ROM_FOLDER,
        fs_name_no_tags=ROM_FOLDER,
        fs_name_no_ext=ROM_FOLDER,
        fs_extension="",
        fs_path=f"{platform.fs_slug}/roms",
        fs_size_bytes=sum(len(data) for data in files.values()),
        crc_hash="stored-crc",
        md5_hash="stored-md5",
        sha1_hash="stored-sha1",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    for rel, data in files.items():
        _add_row(rom, lib, f"{ROM_FOLDER}/{rel}", data)
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    return refreshed


def _single_file_rom(platform: Platform, admin_user: User, lib: Path) -> Rom:
    rom = Rom(
        platform_id=platform.id,
        name="solo",
        slug="solo_slug",
        fs_name="solo.zip",
        fs_name_no_tags="solo",
        fs_name_no_ext="solo",
        fs_extension="zip",
        fs_path=f"{platform.fs_slug}/roms",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    _add_row(rom, lib, "solo.zip", b"romdata")
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    return refreshed


def _start_into_rom(
    client: TestClient,
    token: str,
    rom: Rom,
    *,
    filename: str,
    folder: str | None,
    total_size: int,
    platform_id: int | None = None,
    overwrite: bool = False,
):
    target: dict[str, int | str | bool] = {"rom_id": rom.id}
    if folder is not None:
        target["folder"] = folder
    if overwrite:
        target["overwrite"] = True
    return client.post(
        "/api/roms/upload/start",
        headers={
            **_auth_headers(token),
            "x-upload-platform": str(platform_id or rom.platform_id),
            "x-upload-filename": filename,
            "x-upload-total-size": str(total_size),
            "x-upload-total-chunks": "1",
        },
        json=target,
    )


def _upload_into_rom(
    client: TestClient,
    token: str,
    rom: Rom,
    *,
    filename: str,
    folder: str | None,
    data: bytes,
    overwrite: bool = False,
):
    start = _start_into_rom(
        client,
        token,
        rom,
        filename=filename,
        folder=folder,
        total_size=len(data),
        overwrite=overwrite,
    )
    assert start.status_code == status.HTTP_201_CREATED, start.json()
    upload_id = start.json()["upload_id"]
    put = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(token), "x-chunk-index": "0"},
        content=data,
    )
    assert put.status_code == status.HTTP_200_OK
    return client.post(
        f"/api/roms/upload/{upload_id}/complete", headers=_auth_headers(token)
    )


@pytest.mark.parametrize("folder", ["../x", "/abs", "a/../b", ".", "a//b", "a\\b"])
def test_start_into_rom_rejects_unsafe_folders(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
    folder: str,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = _start_into_rom(
        client, access_token, rom, filename="fix.ips", folder=folder, total_size=3
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_start_into_rom_rejects_path_in_filename(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = _start_into_rom(
        client, access_token, rom, filename="sub/fix.ips", folder=None, total_size=3
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize("filename", ["notes.tmp", ".DS_Store"])
def test_start_into_rom_rejects_names_the_scanner_ignores(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
    filename: str,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = _start_into_rom(
        client, access_token, rom, filename=filename, folder=None, total_size=3
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ignored by the scanner" in response.json()["detail"]


def test_start_into_rom_rejects_platform_mismatch(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})
    other = db_platform_handler.add_platform(
        Platform(name="other", slug="other_slug", fs_slug="other_slug")
    )

    response = _start_into_rom(
        client,
        access_token,
        rom,
        filename="fix.ips",
        folder=None,
        total_size=3,
        platform_id=other.id,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_start_into_unknown_rom_returns_404(
    client: TestClient,
    access_token: str,
    platform: Platform,
    rom_upload_fs: Path,
):
    response = client.post(
        "/api/roms/upload/start",
        headers={
            **_auth_headers(access_token),
            "x-upload-platform": str(platform.id),
            "x-upload-filename": "fix.ips",
            "x-upload-total-size": "3",
            "x-upload-total-chunks": "1",
        },
        json={"rom_id": 999999},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_start_into_rom_rejects_existing_destination(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(
        platform, admin_user, rom_upload_fs, {"game.bin": b"game", "hack/x.ips": b"x"}
    )

    response = _start_into_rom(
        client, access_token, rom, filename="x.ips", folder="hack", total_size=1
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_overwrite_replaces_an_existing_file(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(
        platform, admin_user, rom_upload_fs, {"game.bin": b"game", "hack/x.ips": b"old"}
    )

    refused = _start_into_rom(
        client, access_token, rom, filename="x.ips", folder="hack", total_size=3
    )
    assert refused.status_code == status.HTTP_409_CONFLICT

    response = _upload_into_rom(
        client,
        access_token,
        rom,
        filename="x.ips",
        folder="hack",
        data=b"new",
        overwrite=True,
    )

    assert response.status_code == status.HTTP_201_CREATED, response.json()
    on_disk = rom_upload_fs / rom.fs_path / ROM_FOLDER / "hack" / "x.ips"
    assert on_disk.read_bytes() == b"new"
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    rows = [f for f in refreshed.files if f.file_name == "x.ips"]
    assert len(rows) == 1
    assert rows[0].file_size_bytes == 3


def test_complete_registers_nested_file(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(
        platform,
        admin_user,
        rom_upload_fs,
        {"game.bin": b"game", "readme.txt": b"readme"},
    )

    response = _upload_into_rom(
        client,
        access_token,
        rom,
        filename="fix.ips",
        folder="patches/v2",
        data=b"patch bytes",
    )

    assert response.status_code == status.HTTP_201_CREATED
    on_disk = rom_upload_fs / rom.fs_path / ROM_FOLDER / "patches/v2/fix.ips"
    assert on_disk.read_bytes() == b"patch bytes"
    after = db_rom_handler.get_rom(rom.id)
    assert after is not None
    new = next(f for f in after.files if f.file_name == "fix.ips")
    assert new.file_path == f"{rom.fs_path}/{ROM_FOLDER}/patches/v2"
    assert new.category == RomFileCategory.PATCH
    assert (
        new.md5_hash == hashlib.md5(b"patch bytes", usedforsecurity=False).hexdigest()
    )
    assert after.fs_size_bytes == len(b"game") + len(b"readme") + len(b"patch bytes")
    assert after.md5_hash == "stored-md5"


def test_complete_top_level_file_updates_rom_hashes(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = _upload_into_rom(
        client, access_token, rom, filename="extra.bin", folder=None, data=b"extra"
    )

    assert response.status_code == status.HTTP_201_CREATED
    after = db_rom_handler.get_rom(rom.id)
    assert after is not None
    assert {f.file_name for f in after.files} == {"game.bin", "extra.bin"}
    assert after.md5_hash != "stored-md5"
    expected = hashlib.md5(usedforsecurity=False)
    for rom_file in after.files:
        expected.update(
            (rom_upload_fs / rom_file.file_path / rom_file.file_name).read_bytes()
        )
    assert after.md5_hash in {
        expected.hexdigest(),
        hashlib.md5(b"extragame", usedforsecurity=False).hexdigest(),
    }


def test_complete_into_single_file_rom_promotes_it_to_a_folder(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _single_file_rom(platform, admin_user, rom_upload_fs)
    assert rom.has_simple_single_file

    response = _upload_into_rom(
        client, access_token, rom, filename="notes.txt", folder=None, data=b"notes"
    )

    assert response.status_code == status.HTTP_201_CREATED
    after = db_rom_handler.get_rom(rom.id)
    assert after is not None
    assert after.fs_name == "solo"
    folder = f"{rom.fs_path}/solo"
    assert {(f.file_path, f.file_name) for f in after.files} == {
        (folder, "solo.zip"),
        (folder, "notes.txt"),
    }
    assert (rom_upload_fs / folder / "solo.zip").read_bytes() == b"romdata"
    assert (rom_upload_fs / folder / "notes.txt").read_bytes() == b"notes"


def test_complete_after_destination_appeared_returns_409(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})
    start = _start_into_rom(
        client, access_token, rom, filename="late.bin", folder=None, total_size=4
    )
    upload_id = start.json()["upload_id"]
    client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"late",
    )
    _write(rom_upload_fs, f"{rom.fs_path}/{ROM_FOLDER}/late.bin", b"raced")

    response = client.post(
        f"/api/roms/upload/{upload_id}/complete", headers=_auth_headers(access_token)
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert not (ROM_UPLOAD_TMP_BASE / upload_id).exists()
    assert (
        rom_upload_fs / rom.fs_path / ROM_FOLDER / "late.bin"
    ).read_bytes() == b"raced"


def test_start_into_single_file_rom_rejects_its_own_name(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _single_file_rom(platform, admin_user, rom_upload_fs)

    response = _start_into_rom(
        client, access_token, rom, filename="solo.zip", folder=None, total_size=3
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    assert refreshed.fs_name == "solo.zip"


def test_complete_collision_does_not_promote_a_single_file_rom(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _single_file_rom(platform, admin_user, rom_upload_fs)
    start = _start_into_rom(
        client, access_token, rom, filename="notes.txt", folder=None, total_size=5
    )
    upload_id = start.json()["upload_id"]
    client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"notes",
    )
    _write(rom_upload_fs, f"{rom.fs_path}/solo/notes.txt", b"raced")

    response = client.post(
        f"/api/roms/upload/{upload_id}/complete", headers=_auth_headers(access_token)
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    after = db_rom_handler.get_rom(rom.id)
    assert after is not None
    assert after.fs_name == "solo.zip"
    assert (rom_upload_fs / rom.fs_path / "solo.zip").read_bytes() == b"romdata"


def test_start_takes_the_filename_from_the_body_over_the_header(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    """A browser cannot put a name outside Latin-1 in a header, so the body
    names the file and the header only has to be present."""
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})
    name = "Relax \uff5c 432Hz.mp3"

    start = client.post(
        "/api/roms/upload/start",
        headers={
            **_auth_headers(access_token),
            "x-upload-platform": str(rom.platform_id),
            "x-upload-filename": "Relax%20%EF%BD%9C%20432Hz.mp3",
            "x-upload-total-size": "5",
            "x-upload-total-chunks": "1",
        },
        json={"rom_id": rom.id, "folder": "soundtrack", "filename": name},
    )
    assert start.status_code == status.HTTP_201_CREATED, start.json()
    upload_id = start.json()["upload_id"]
    client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"audio",
    )
    complete = client.post(
        f"/api/roms/upload/{upload_id}/complete", headers=_auth_headers(access_token)
    )

    assert complete.status_code == status.HTTP_201_CREATED, complete.json()
    on_disk = rom_upload_fs / rom.fs_path / ROM_FOLDER / "soundtrack" / name
    assert on_disk.read_bytes() == b"audio"
    track = db_rom_handler.get_rom_files_by_category(rom.id, RomFileCategory.SOUNDTRACK)
    assert [f.file_name for f in track] == [name]


def test_start_refuses_a_file_the_folder_category_cannot_hold(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = _start_into_rom(
        client,
        access_token,
        rom,
        filename="notes.txt",
        folder="screenshots",
        total_size=3,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported image file type" in response.json()["detail"]


def test_start_rejects_an_empty_body_filename(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = client.post(
        "/api/roms/upload/start",
        headers={
            **_auth_headers(access_token),
            "x-upload-platform": str(rom.platform_id),
            "x-upload-filename": "fallback.bin",
            "x-upload-total-size": "3",
            "x-upload-total-chunks": "1",
        },
        json={"rom_id": rom.id, "filename": ""},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "filename" in response.json()["detail"].lower()


def test_complete_into_the_walkthrough_folder_records_the_upload_source(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = _upload_into_rom(
        client,
        access_token,
        rom,
        filename="guide.txt",
        folder="walkthrough",
        data=b"Step 1: leave home.",
    )

    assert response.status_code == status.HTTP_201_CREATED, response.json()
    guides = db_rom_handler.get_rom_files_by_category(
        rom.id, RomFileCategory.WALKTHROUGH
    )
    assert [f.file_name for f in guides] == ["guide.txt"]
    assert guides[0].doc_meta is not None
    assert guides[0].doc_meta.source == DocSource.UPLOAD


def test_complete_into_a_category_folder_registers_the_category(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    rom_upload_fs: Path,
):
    rom = _folder_rom(platform, admin_user, rom_upload_fs, {"game.bin": b"game"})

    response = _upload_into_rom(
        client,
        access_token,
        rom,
        filename="shot.png",
        folder="screenshots",
        data=b"\x89PNG",
    )

    assert response.status_code == status.HTTP_201_CREATED, response.json()
    shots = db_rom_handler.get_rom_files_by_category(rom.id, RomFileCategory.SCREENSHOT)
    assert [f.file_name for f in shots] == ["shot.png"]


def test_claim_destination_refuses_an_existing_file(tmp_path: Path):
    target = tmp_path / "game.bin"

    rom_upload.claim_destination(target)
    assert target.exists()

    with pytest.raises(rom_upload.UploadConflictException):
        rom_upload.claim_destination(target)
