import hashlib
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.roms_handler import ParsedRomFiles
from handler.rom_files import refresh_rom_files
from models.platform import Platform
from models.rom import (
    Rom,
    RomFile,
    RomFileCategory,
    RomIdentity,
    SaveTargetLayout,
)
from models.user import User

FOLDER = "Multi"


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    monkeypatch.setattr(fs_rom_handler, "base_path", lib.resolve())
    return lib


def _write(lib: Path, rel: str, data: bytes) -> os.stat_result:
    path = lib / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path.stat()


def _folder_rom(
    platform: Platform, admin_user: User, lib: Path, files: dict[str, bytes]
) -> Rom:
    """A folder ROM whose rows describe the files on disk, with stored hashes."""
    rom = Rom(
        platform_id=platform.id,
        name=FOLDER,
        slug=f"{FOLDER}_slug",
        fs_name=FOLDER,
        fs_name_no_tags=FOLDER,
        fs_name_no_ext=FOLDER,
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
        st = _write(lib, f"{rom.fs_path}/{FOLDER}/{rel}", data)
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=Path(rel).name,
                file_path=str(Path(rom.fs_path, FOLDER, rel).parent),
                file_size_bytes=st.st_size,
                last_modified=st.st_mtime,
                crc_hash="row-crc",
                md5_hash="row-md5",
                sha1_hash="row-sha1",
            )
        )
    return db_rom_handler.get_rom(rom.id)


def _files_by_name(rom_id: int) -> dict[str, RomFile]:
    return {f.file_name: f for f in db_rom_handler.get_rom(rom_id).files}


async def test_registers_new_nested_file(platform, admin_user, library):
    rom = _folder_rom(
        platform, admin_user, library, {"game.bin": b"game", "readme.txt": b"readme"}
    )
    _write(library, f"{rom.fs_path}/{FOLDER}/patches/v2/fix.ips", b"patch bytes")

    result = await refresh_rom_files(rom)

    assert (result.new_files, result.updated_files, result.removed_files) == (1, 0, 0)
    new = _files_by_name(rom.id)["fix.ips"]
    assert new.category == RomFileCategory.PATCH
    assert (
        new.md5_hash == hashlib.md5(b"patch bytes", usedforsecurity=False).hexdigest()
    )
    after = db_rom_handler.get_rom(rom.id)
    assert after.fs_size_bytes == len(b"game") + len(b"readme") + len(b"patch bytes")
    assert after.md5_hash == "stored-md5"


async def test_top_level_addition_updates_rom_hashes_and_size(
    platform, admin_user, library
):
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})
    _write(library, f"{rom.fs_path}/{FOLDER}/extra.bin", b"extra")

    result = await refresh_rom_files(rom)

    assert result.new_files == 1
    either_order = {
        hashlib.md5(a + b, usedforsecurity=False).hexdigest()
        for a, b in ((b"game", b"extra"), (b"extra", b"game"))
    }
    after = db_rom_handler.get_rom(rom.id)
    assert after.md5_hash in either_order
    assert after.fs_size_bytes == len(b"game") + len(b"extra")
    assert (
        _files_by_name(rom.id)["game.bin"].md5_hash
        == hashlib.md5(b"game", usedforsecurity=False).hexdigest()
    )


async def test_unchanged_rom_writes_nothing(platform, admin_user, library, mocker):
    rom = _folder_rom(
        platform, admin_user, library, {"game.bin": b"game", "hack/x.bin": b"hack"}
    )
    sync = mocker.spy(db_rom_handler, "sync_rom_files")
    update = mocker.spy(db_rom_handler, "update_rom")

    result = await refresh_rom_files(rom)

    assert not result.changed
    sync.assert_not_called()
    update.assert_not_called()


async def test_removes_rows_for_vanished_files(platform, admin_user, library):
    rom = _folder_rom(
        platform, admin_user, library, {"game.bin": b"game", "hack/old.bin": b"old"}
    )
    (library / rom.fs_path / FOLDER / "hack/old.bin").unlink()

    result = await refresh_rom_files(rom)

    assert result.removed_files == 1
    assert set(_files_by_name(rom.id)) == {"game.bin"}
    # A nested file leaves the top level, and so the rom hash, alone.
    assert db_rom_handler.get_rom(rom.id).md5_hash == "stored-md5"


async def test_clears_missing_flag(platform, admin_user, library):
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})
    db_rom_handler.update_rom(rom.id, {"missing_from_fs": True})
    rom = db_rom_handler.get_rom(rom.id)

    result = await refresh_rom_files(rom)

    assert not result.changed
    assert db_rom_handler.get_rom(rom.id).missing_from_fs is False


async def test_empty_folder_keeps_recorded_rows(platform, admin_user, library):
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})
    (library / rom.fs_path / FOLDER / "game.bin").unlink()

    result = await refresh_rom_files(rom)

    assert not result.changed
    assert set(_files_by_name(rom.id)) == {"game.bin"}


async def test_edited_file_is_rehashed_in_place(platform, admin_user, library):
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"stale"})
    row_id = rom.files[0].id
    _write(library, f"{rom.fs_path}/{FOLDER}/game.bin", b"game")

    result = await refresh_rom_files(rom)

    assert result.updated_files == 1
    after = db_rom_handler.get_rom(rom.id)
    assert after.files[0].id == row_id
    assert (
        after.files[0].md5_hash
        == hashlib.md5(b"game", usedforsecurity=False).hexdigest()
    )
    assert after.md5_hash == hashlib.md5(b"game", usedforsecurity=False).hexdigest()


async def test_loads_files_when_relationship_is_unloaded(platform, admin_user, library):
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})
    lean = db_rom_handler.get_roms_by_fs_name(
        platform_id=platform.id, fs_names={FOLDER}
    )[FOLDER]
    _write(library, f"{rom.fs_path}/{FOLDER}/cheats/codes.cht", b"cheats")

    result = await refresh_rom_files(lean)

    assert result.new_files == 1
    assert _files_by_name(rom.id)["codes.cht"].category == RomFileCategory.CHEAT


async def test_disabled_hashing_keeps_stored_rom_hashes(
    platform, admin_user, library, mocker
):
    from config.config_manager import config_manager as cm

    config = cm.get_config()
    mocker.patch.object(config, "SKIP_HASH_CALCULATION", True)
    mocker.patch.object(cm, "get_config", return_value=config)
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})
    _write(library, f"{rom.fs_path}/{FOLDER}/extra.bin", b"extra")

    result = await refresh_rom_files(rom)

    assert result.new_files == 1
    after = db_rom_handler.get_rom(rom.id)
    assert (after.crc_hash, after.md5_hash, after.sha1_hash) == (
        "stored-crc",
        "stored-md5",
        "stored-sha1",
    )
    assert _files_by_name(rom.id)["extra.bin"].md5_hash == ""


async def test_disabled_title_id_extraction_is_passed_through(
    platform, admin_user, library, mocker
):
    from config.config_manager import config_manager as cm

    config = cm.get_config()
    mocker.patch.object(config, "SKIP_TITLE_ID_EXTRACTION", True)
    mocker.patch.object(cm, "get_config", return_value=config)
    get_rom_files = mocker.spy(fs_rom_handler, "get_rom_files")
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})

    await refresh_rom_files(rom)

    assert get_rom_files.call_args.kwargs["extract_title_ids"] is False


def _unchanged_parse(rom: Rom, identity: RomIdentity) -> ParsedRomFiles:
    """A listing that found every file untouched, carrying the given identity."""
    return ParsedRomFiles(
        rom_files=list(rom.files),
        crc_hash=rom.crc_hash or "",
        md5_hash=rom.md5_hash or "",
        sha1_hash=rom.sha1_hash or "",
        ra_hash="",
        top_level_changed=False,
        identity=identity,
    )


async def test_a_newly_read_identity_is_persisted(platform, admin_user, library):
    """The refresh pays for the parse, so the id it reads has to land somewhere."""
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})
    identity = RomIdentity(
        title_id="0100ABCD12340000",
        save_target="0100ABCD12340000",
        save_target_layout=SaveTargetLayout.FOLDER_EXACT,
    )

    with patch.object(
        fs_rom_handler,
        "get_rom_files",
        AsyncMock(return_value=_unchanged_parse(rom, identity)),
    ):
        await refresh_rom_files(rom)

    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed.title_id == "0100ABCD12340000"
    assert refreshed.save_target == "0100ABCD12340000"
    assert refreshed.save_target_layout == SaveTargetLayout.FOLDER_EXACT


async def test_a_stored_identity_survives_a_parse_that_read_none(
    platform, admin_user, library
):
    rom = _folder_rom(platform, admin_user, library, {"game.bin": b"game"})
    db_rom_handler.update_rom(rom.id, {"title_id": "ULUS-10041"})
    rom = db_rom_handler.get_rom(rom.id)

    with patch.object(
        fs_rom_handler,
        "get_rom_files",
        AsyncMock(return_value=_unchanged_parse(rom, RomIdentity())),
    ):
        await refresh_rom_files(rom)

    assert db_rom_handler.get_rom(rom.id).title_id == "ULUS-10041"
