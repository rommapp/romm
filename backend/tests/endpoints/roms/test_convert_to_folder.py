import asyncio
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler import rom_conversion
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.rom_conversion import promote_single_file_to_folder
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User

MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x21fake mp3 payload"
PDF_BYTES = b"%PDF-1.4 fake pdf payload"
PNG_BYTES = b"\x89PNG\r\n\x1a\n fake png payload"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def real_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point fs_rom_handler at a real temp library so FS moves actually happen."""
    lib = tmp_path / "library"
    lib.mkdir()
    monkeypatch.setattr(fs_rom_handler, "base_path", lib.resolve())
    return lib


def _single_file_rom(
    platform: Platform,
    admin_user: User,
    lib: Path,
    *,
    fs_name: str,
    fs_name_no_ext: str,
    fs_extension: str,
) -> Rom:
    """A simple single-file ROM with its lone file present on disk."""
    rom = Rom(
        platform_id=platform.id,
        name=fs_name_no_ext,
        slug=f"{fs_name}_slug",
        fs_name=fs_name,
        fs_name_no_tags=fs_name_no_ext,
        fs_name_no_ext=fs_name_no_ext,
        fs_extension=fs_extension,
        fs_path=f"{platform.slug}/roms",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=fs_name,
            file_path=rom.fs_path,
            file_size_bytes=10,
            last_modified=1700000000.0,
            category=RomFileCategory.GAME,
        )
    )
    disk = lib / rom.fs_path / fs_name
    disk.parent.mkdir(parents=True, exist_ok=True)
    disk.write_bytes(b"romdata")
    return db_rom_handler.get_rom(rom.id)


# ---------- POST /api/roms/{id}/convert-to-folder ----------


def test_convert_single_file_promotes_in_place(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom.zip",
        fs_name_no_ext="test_rom",
        fs_extension="zip",
    )
    assert rom.has_simple_single_file
    rom_id = rom.id

    response = client.post(
        f"/api/roms/{rom_id}/convert-to-folder", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK

    after = db_rom_handler.get_rom(rom_id)
    assert after.id == rom_id  # same id, no dead reference
    assert after.fs_name == "test_rom"
    game_file = after.files[0]
    assert game_file.file_name == "test_rom.zip"
    assert game_file.file_path == f"{platform.slug}/roms/test_rom"
    assert game_file.file_path != after.fs_path

    moved = real_library / f"{platform.slug}/roms/test_rom/test_rom.zip"
    assert moved.exists() and moved.read_bytes() == b"romdata"
    assert not (real_library / f"{platform.slug}/roms/test_rom.zip").exists()


def test_convert_already_folder_is_clean_noop(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom.zip",
        fs_name_no_ext="test_rom",
        fs_extension="zip",
    )
    # First call converts; second call is a clean no-op on the now-folder ROM.
    first = client.post(
        f"/api/roms/{rom.id}/convert-to-folder", headers=_auth(access_token)
    )
    assert first.status_code == status.HTTP_200_OK

    second = client.post(
        f"/api/roms/{rom.id}/convert-to-folder", headers=_auth(access_token)
    )
    assert second.status_code == status.HTTP_200_OK
    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_name == "test_rom"  # unchanged by the second call


def test_convert_folder_collision_returns_409(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom.zip",
        fs_name_no_ext="test_rom",
        fs_extension="zip",
    )
    # A folder already occupies the target name.
    (real_library / f"{platform.slug}/roms/test_rom").mkdir(parents=True)

    response = client.post(
        f"/api/roms/{rom.id}/convert-to-folder", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_409_CONFLICT

    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_name == "test_rom.zip"  # untouched


def test_convert_extensionless_uses_staging(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom",
        fs_name_no_ext="test_rom",
        fs_extension="",
    )

    response = client.post(
        f"/api/roms/{rom.id}/convert-to-folder", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK

    moved = real_library / f"{platform.slug}/roms/test_rom/test_rom"
    assert moved.is_file() and moved.read_bytes() == b"romdata"
    after = db_rom_handler.get_rom(rom.id)
    assert after.files[0].file_path == f"{platform.slug}/roms/test_rom"


def test_convert_extensionless_dir_collision_returns_409(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom",
        fs_name_no_ext="test_rom",
        fs_extension="",
    )
    # Stale row over a folder the user already created on disk (no rescan).
    lone = real_library / f"{platform.slug}/roms/test_rom"
    lone.unlink()
    lone.mkdir()
    (lone / "already_here.txt").write_text("keep me")

    response = client.post(
        f"/api/roms/{rom.id}/convert-to-folder", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_409_CONFLICT

    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_name == "test_rom"  # untouched
    assert (lone / "already_here.txt").read_text() == "keep me"  # user's dir intact


def test_convert_rolls_back_fs_on_db_failure(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom",
        fs_name_no_ext="test_rom",
        fs_extension="",
    )

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(db_rom_handler, "convert_rom_to_folder", boom)

    with pytest.raises(RuntimeError, match="db down"):
        client.post(
            f"/api/roms/{rom.id}/convert-to-folder", headers=_auth(access_token)
        )

    base = real_library / f"{platform.slug}/roms"
    assert (base / "test_rom").is_file()
    assert (base / "test_rom").read_bytes() == b"romdata"
    assert not (base / ".romm_tmp_test_rom").exists()
    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_name == "test_rom"
    assert after.has_simple_single_file


# ---------- auto-convert on upload (all three asset types) ----------


def test_soundtrack_upload_auto_converts_single_file_rom(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom.zip",
        fs_name_no_ext="test_rom",
        fs_extension="zip",
    )
    response = client.post(
        f"/api/roms/{rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": "track1.mp3"},
        files={"track1.mp3": ("track1.mp3", MP3_BYTES, "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_201_CREATED

    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_name == "test_rom"  # converted
    soundtracks = [f for f in after.files if f.category == RomFileCategory.SOUNDTRACK]
    assert len(soundtracks) == 1
    assert (
        real_library / f"{platform.slug}/roms/test_rom/soundtrack/track1.mp3"
    ).exists()


def test_manual_upload_auto_converts_single_file_rom(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom.zip",
        fs_name_no_ext="test_rom",
        fs_extension="zip",
    )
    response = client.post(
        f"/api/roms/{rom.id}/manuals/files",
        headers={**_auth(access_token), "x-upload-filename": "manual.pdf"},
        files={"manual.pdf": ("manual.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == status.HTTP_201_CREATED

    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_name == "test_rom"
    assert any(f.category == RomFileCategory.MANUAL for f in after.files)


def test_screenshot_upload_auto_converts_single_file_rom(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    real_library: Path,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="test_rom.zip",
        fs_name_no_ext="test_rom",
        fs_extension="zip",
    )
    response = client.post(
        f"/api/roms/{rom.id}/screenshots",
        headers={**_auth(access_token), "x-upload-filename": "shot1.png"},
        files={"shot1.png": ("shot1.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == status.HTTP_201_CREATED

    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_name == "test_rom"
    assert any(f.category == RomFileCategory.SCREENSHOT for f in after.files)


async def test_second_upload_racing_a_promotion_keeps_the_rom_in_its_folder(
    platform: Platform,
    admin_user: User,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="sf2ce.zip",
        fs_name_no_ext="sf2ce",
        fs_extension="zip",
    )
    second = db_rom_handler.get_rom(rom.id)

    # Holding both at the mkdir puts them past the collision check together.
    make_directory = fs_rom_handler.make_directory
    barrier = asyncio.Barrier(2)

    async def gated_make_directory(path: str) -> None:
        try:
            await asyncio.wait_for(barrier.wait(), 0.5)
        except (TimeoutError, asyncio.BrokenBarrierError):
            pass
        await make_directory(path)

    monkeypatch.setattr(fs_rom_handler, "make_directory", gated_make_directory)

    results = await asyncio.gather(
        promote_single_file_to_folder(rom),
        promote_single_file_to_folder(second),
        return_exceptions=True,
    )

    assert not [r for r in results if isinstance(r, BaseException)]
    inside = real_library / f"{platform.slug}/roms/sf2ce/sf2ce.zip"
    beside = real_library / f"{platform.slug}/roms/sf2ce.zip"
    assert inside.exists(), "the loser dragged the ROM back out of its folder"
    assert not beside.exists()


async def test_promotion_racing_across_workers_does_not_destroy_the_folder(
    platform: Platform,
    admin_user: User,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    rom = _single_file_rom(
        platform,
        admin_user,
        real_library,
        fs_name="sf2ce.zip",
        fs_name_no_ext="sf2ce",
        fs_extension="zip",
    )
    second = db_rom_handler.get_rom(rom.id)

    class _NoLock:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_: object) -> None:
            return None

    # Separate workers hold separate locks, so neither serializes the other.
    monkeypatch.setattr(rom_conversion, "_promotion_lock", _NoLock())

    make_directory = fs_rom_handler.make_directory
    barrier = asyncio.Barrier(2)

    async def gated_make_directory(path: str) -> None:
        try:
            await asyncio.wait_for(barrier.wait(), 0.5)
        except (TimeoutError, asyncio.BrokenBarrierError):
            pass
        await make_directory(path)

    monkeypatch.setattr(fs_rom_handler, "make_directory", gated_make_directory)

    await asyncio.gather(
        promote_single_file_to_folder(rom),
        promote_single_file_to_folder(second),
        return_exceptions=True,
    )

    inside = real_library / f"{platform.slug}/roms/sf2ce/sf2ce.zip"
    assert inside.exists(), "the loser destroyed the winner's folder"
    assert inside.read_bytes() == b"romdata"
