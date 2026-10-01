from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from tests.factories import make_rom

from adapters.services.rom_converto import (
    RomConvertoOperationError,
    rom_converto_service,
)
from config.config_manager import ConvertoConfig
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User
from tasks.manual.convert_library import ConvertLibraryTask


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    monkeypatch.setattr(fs_rom_handler, "base_path", lib.resolve())
    return lib


@pytest.fixture
def converto(mocker) -> ConvertoConfig:
    config = ConvertoConfig(platform_formats={"psp": "chd", "psx": "chd"})
    # The file refresh after a conversion reads the rest of the same config.
    real = cm.get_config()
    mocker.patch.object(real, "CONVERTO", config)
    mocker.patch.object(cm, "get_config", return_value=real)
    return config


@pytest.fixture
def converted(mocker) -> list[tuple[str, Path]]:
    """Fake rom-converto: each conversion writes a small output and is recorded."""
    calls: list[tuple[str, Path]] = []

    def convert(operation, src: Path, out: Path) -> None:
        calls.append((src.name, out))
        out.write_bytes(b"c")

    mocker.patch.object(
        rom_converto_service, "is_enabled", AsyncMock(return_value=True)
    )
    mocker.patch.object(rom_converto_service, "convert", AsyncMock(side_effect=convert))
    return calls


def _platform(slug: str) -> Platform:
    return db_platform_handler.add_platform(
        Platform(name=slug, slug=slug, fs_slug=slug)
    )


def _rom(
    library: Path,
    admin_user: User,
    platform: Platform,
    files: dict[str, bytes],
    *,
    folder: bool = False,
    matched: bool = True,
) -> Rom:
    """A rom with `files` on disk: a single file, or a folder holding them all."""
    name = "game"
    rom = make_rom(
        platform,
        name,
        fs_extension="" if folder else Path(next(iter(files))).suffix.lstrip("."),
        igdb_id=1 if matched else None,
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    file_path = f"{rom.fs_path}/{rom.fs_name}" if folder else rom.fs_path
    for file_name, data in files.items():
        disk = library / file_path / file_name
        disk.parent.mkdir(parents=True, exist_ok=True)
        disk.write_bytes(data)
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=file_name,
                file_path=file_path,
                file_size_bytes=len(data),
                last_modified=disk.stat().st_mtime,
                category=RomFileCategory.GAME,
            )
        )
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    return refreshed


def _reload(rom: Rom) -> Rom:
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    return refreshed


async def _run(platform: Platform | None = None) -> dict[str, int]:
    return await ConvertLibraryTask().run(platform.id if platform else None)


async def test_a_single_file_rom_is_replaced_and_keeps_its_id(
    library: Path, admin_user: User, converto, converted
):
    psp = _platform("psp")
    rom = _rom(library, admin_user, psp, {"game.iso": b"x" * 100})
    folder = library / rom.fs_path

    stats = await _run()

    assert stats["converted"] == 1
    assert stats["bytes_saved"] == 99
    assert sorted(p.name for p in folder.iterdir()) == ["game.chd"]
    after = _reload(rom)
    assert after.fs_name == "game.chd"
    assert after.fs_extension == "chd"
    assert [f.file_name for f in after.files] == ["game.chd"]


async def test_a_cue_folder_becomes_one_chd_and_its_playlist_follows(
    library: Path, admin_user: User, converto, converted
):
    psx = _platform("psx")
    cue = 'FILE "game (Track 1).bin" BINARY\nFILE "game (Track 2).bin" BINARY\n'
    rom = _rom(
        library,
        admin_user,
        psx,
        {
            "game.cue": cue.encode(),
            "game (Track 1).bin": b"x" * 50,
            "game (Track 2).bin": b"x" * 50,
            "game.m3u": b"game.cue\n",
        },
        folder=True,
    )
    folder = library / rom.full_path

    stats = await _run()

    assert stats["converted"] == 1
    assert sorted(p.name for p in folder.iterdir()) == ["game.chd", "game.m3u"]
    assert (folder / "game.m3u").read_text() == "game.chd\n"
    after = _reload(rom)
    assert after.fs_name == rom.fs_name
    assert sorted(f.file_name for f in after.files) == ["game.chd", "game.m3u"]


async def test_a_file_already_in_the_library_format_is_left_alone(
    library: Path, admin_user: User, converto, converted
):
    _rom(library, admin_user, _platform("psp"), {"game.chd": b"x"})

    stats = await _run()

    assert stats["already_converted"] == 1
    assert converted == []


async def test_an_unmatched_rom_is_not_converted(
    library: Path, admin_user: User, converto, converted
):
    rom = _rom(library, admin_user, _platform("psp"), {"game.iso": b"x"}, matched=False)

    stats = await _run()

    assert stats["unmatched"] == 1
    assert converted == []
    assert (library / rom.full_path).exists()


async def test_a_platform_without_a_library_format_is_skipped(
    library: Path, admin_user: User, converto, converted
):
    converto.platform_formats = {}
    _rom(library, admin_user, _platform("psp"), {"game.iso": b"x"})

    stats = await _run()

    assert stats["converted"] == 0
    assert converted == []


async def test_only_the_requested_platform_is_converted(
    library: Path, admin_user: User, converto, converted
):
    psp = _platform("psp")
    _rom(library, admin_user, psp, {"game.iso": b"x" * 10})
    _rom(library, admin_user, _platform("psx"), {"game.cue": b""}, folder=True)

    await _run(psp)

    assert [src for src, _ in converted] == ["game.iso"]


async def test_a_failed_conversion_leaves_the_original_and_no_staged_output(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _rom(library, admin_user, _platform("psp"), {"game.iso": b"x"})
    mocker.patch.object(
        rom_converto_service,
        "convert",
        AsyncMock(side_effect=RomConvertoOperationError("boom")),
    )

    stats = await _run()

    assert stats["failed"] == 1
    assert sorted(p.name for p in (library / rom.fs_path).iterdir()) == ["game.iso"]
    assert _reload(rom).fs_name == "game.iso"


async def test_an_existing_output_is_never_overwritten(
    library: Path, admin_user: User, converto, converted
):
    rom = _rom(library, admin_user, _platform("psp"), {"game.iso": b"x"})
    (library / rom.fs_path / "game.chd").write_bytes(b"theirs")

    stats = await _run()

    assert stats["failed"] == 1
    assert converted == []
    assert (library / rom.fs_path / "game.chd").read_bytes() == b"theirs"
    assert (library / rom.full_path).exists()


async def test_a_rom_row_already_holding_the_output_name_is_left_alone(
    library: Path, admin_user: User, converto, converted
):
    psp = _platform("psp")
    rom = _rom(library, admin_user, psp, {"game.iso": b"x"})
    make_rom(psp, "other", fs_stem="game", fs_extension="chd")

    stats = await _run()

    assert stats["failed"] == 1
    assert converted == []
    assert (library / rom.full_path).exists()


async def test_a_cue_pointing_outside_its_folder_is_refused(
    library: Path, admin_user: User, converto, converted
):
    rom = _rom(
        library,
        admin_user,
        _platform("psx"),
        {"game.cue": b'FILE "../other.bin" BINARY\n'},
        folder=True,
    )

    stats = await _run()

    assert stats["failed"] == 1
    assert converted == []
    assert (library / rom.full_path / "game.cue").exists()


async def test_nothing_runs_without_rom_converto(
    library: Path, admin_user: User, converto, converted, mocker
):
    mocker.patch.object(
        rom_converto_service, "is_enabled", AsyncMock(return_value=False)
    )
    _rom(library, admin_user, _platform("psp"), {"game.iso": b"x"})

    stats = await _run()

    assert stats["converted"] == 0
    assert converted == []
