import io
import os
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from tests.factories import make_platform, make_rom

from adapters.services.rom_converto import (
    RomConvertoOperationError,
    rom_converto_service,
)
from config.config_manager import ConvertoConfig
from config.config_manager import config_manager as cm
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User
from tasks.manual import convert_library
from tasks.manual.convert_library import ConvertLibraryTask
from utils.zip_cache import ensure_zipfile_writable


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


def _archive_rom(
    library: Path, admin_user: User, platform: Platform, files: dict[str, bytes]
) -> Rom:
    data = io.BytesIO()
    ensure_zipfile_writable()
    with zipfile.ZipFile(data, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    rom = _rom(library, admin_user, platform, {"Game.zip": data.getvalue()})
    db_rom_handler.update_rom(
        rom.id,
        {"fs_name": "Game.zip", "fs_name_no_ext": "Game", "fs_name_no_tags": "Game"},
    )
    db_rom_handler.update_rom_file(
        rom.files[0].id,
        {
            "archive_members": [
                {
                    "name": name,
                    "size": len(content),
                    "crc_hash": "crc",
                    "md5_hash": "md5",
                    "sha1_hash": "sha1",
                }
                for name, content in files.items()
            ]
        },
    )
    return _reload(rom)


@pytest.mark.parametrize(
    ("slug", "members"),
    [
        ("psp", {"Game.iso": b"x" * 100}),
        (
            "psx",
            {
                "Game.cue": (
                    b'FILE "Game (Track 1).bin" BINARY\n'
                    b"  TRACK 01 MODE2/2352\n"
                    b'FILE "Game (Track 2).bin" BINARY\n'
                    b"  TRACK 02 AUDIO\n"
                ),
                "Game (Track 1).bin": b"x" * 50,
                "Game (Track 2).bin": b"y" * 50,
            },
        ),
    ],
    ids=["iso", "cue-tracks"],
)
async def test_archive_is_replaced_and_keeps_its_id(
    library: Path, admin_user: User, converto, converted, slug, members
):
    rom = _archive_rom(library, admin_user, make_platform(slug), members)
    source = library / rom.full_path
    size = source.stat().st_size

    stats = await _run()

    assert stats["converted"] == 1
    assert stats["unsupported"] == 0
    assert stats["bytes_saved"] == size - 1
    assert not source.exists()
    assert sorted(p.name for p in source.parent.iterdir()) == ["Game.chd"]
    assert (source.parent / "Game.chd").read_bytes() == b"c"
    assert [name for name, _ in converted] == ["Game.zip"]
    assert converted[0][1].name == "Game.chd"
    after = _reload(rom)
    assert after.id == rom.id
    assert after.fs_name == "Game.chd"
    assert after.fs_extension == "chd"
    assert [f.file_name for f in after.files] == ["Game.chd"]


@pytest.mark.parametrize(
    "case",
    [
        "unlisted",
        "readme",
        "two-cues",
        "extra-track",
        "duplicate-basename",
        "untracked-file",
        "separator-hidden-track",
        "bom-cue",
        "oversized-cue",
        "cue-read-overflow",
        "corrupt",
        "listing-value-error",
        "listing-unicode-error",
        "filtered-member",
        "size-changed",
        "mtime-changed",
    ],
)
async def test_unsafe_archive_is_unsupported(
    library: Path, admin_user: User, converto, converted, case, mocker
):
    if case in (
        "two-cues",
        "extra-track",
        "duplicate-basename",
        "untracked-file",
        "separator-hidden-track",
        "bom-cue",
        "oversized-cue",
        "cue-read-overflow",
    ):
        slug = "psx"
        members = {
            "Game.cue": (
                b'FILE "Game (Track 1).bin" BINARY\n'
                b"  TRACK 01 MODE2/2352\n"
                b'FILE "Game (Track 2).bin" BINARY\n'
                b"  TRACK 02 AUDIO\n"
            ),
            "Game (Track 1).bin": b"x" * 50,
            "Game (Track 2).bin": b"y" * 50,
        }
        if case == "two-cues":
            members["Other.cue"] = (
                b'FILE "Game (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\n'
            )
        elif case == "duplicate-basename":
            track = members.pop("Game (Track 1).bin")
            members["a/Game (Track 1).bin"] = track
            members["b/Game (Track 1).bin"] = track
        elif case in ("extra-track", "untracked-file", "separator-hidden-track"):
            members["Game (Track 3).bin"] = b"z" * 50
            if case == "untracked-file":
                members["Game.cue"] += b'FILE "Game (Track 3).bin" BINARY\n'
            elif case == "separator-hidden-track":
                # The CLI reads \x1c as part of the word, so this is no TRACK to it.
                members[
                    "Game.cue"
                ] += b'FILE "Game (Track 3).bin" BINARY\n\x1cTRACK 03 AUDIO\n'
        elif case == "bom-cue":
            # The CLI keeps a BOM, so it doesn't see the first FILE line.
            members["Game.cue"] = "\ufeff".encode() + members["Game.cue"]
    else:
        slug = "psp"
        members = {"Game.iso": b"x" * 100}
        if case == "readme":
            members["readme.txt"] = b"keep me"
        elif case == "filtered-member":
            members["dump.log"] = b"keep me"
    rom = _archive_rom(library, admin_user, make_platform(slug), members)
    source = library / rom.full_path
    if case == "unlisted":
        db_rom_handler.update_rom_file(rom.files[0].id, {"archive_members": None})
    elif case == "filtered-member":
        recorded = rom.files[0].archive_members
        assert recorded is not None
        db_rom_handler.update_rom_file(
            rom.files[0].id,
            {"archive_members": [m for m in recorded if m["name"] != "dump.log"]},
        )
    elif case == "size-changed":
        before = source.stat()
        source.write_bytes(source.read_bytes() + b"changed")
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif case == "mtime-changed":
        before = source.stat()
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
    elif case == "corrupt":
        source.write_bytes(b"not a zip")
        db_rom_handler.update_rom_file(
            rom.files[0].id,
            {
                "file_size_bytes": source.stat().st_size,
                "last_modified": source.stat().st_mtime,
            },
        )
    elif case in ("listing-value-error", "listing-unicode-error"):
        error = (
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte")
            if case == "listing-unicode-error"
            else ValueError("invalid archive listing")
        )
        mocker.patch(
            "tasks.manual.convert_library.list_archive_members", side_effect=error
        )
    elif case == "oversized-cue":
        mocker.patch("tasks.manual.convert_library._MAX_CUE_BYTES", 1)
    elif case == "cue-read-overflow":
        mocker.patch("tasks.manual.convert_library._MAX_CUE_BYTES", 1)
        recorded = rom.files[0].archive_members
        assert recorded is not None
        db_rom_handler.update_rom_file(
            rom.files[0].id,
            {
                "archive_members": [
                    {**member, "size": 1} if member["name"] == "Game.cue" else member
                    for member in recorded
                ]
            },
        )
    read_member = mocker.spy(convert_library, "read_archive_member")
    original = source.read_bytes()

    stats = await _run()

    assert stats["unsupported"] == 1
    assert stats["converted"] == 0
    assert stats["failed"] == 0
    assert converted == []
    if case == "oversized-cue":
        read_member.assert_not_called()
    elif case == "cue-read-overflow":
        read_member.assert_called_once_with(source, "Game.cue", 1)
    assert source.read_bytes() == original
    assert sorted(p.name for p in source.parent.iterdir()) == ["Game.zip"]
    after = _reload(rom)
    assert after.fs_name == "Game.zip"
    assert [f.file_name for f in after.files] == ["Game.zip"]


async def test_archive_changed_during_conversion_is_kept(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _archive_rom(
        library, admin_user, make_platform("psp"), {"Game.iso": b"x" * 100}
    )
    source = library / rom.full_path
    before = source.stat()
    changed = source.read_bytes() + b"changed"
    warning = mocker.patch("tasks.manual.convert_library.log.warning")

    def convert(operation, src: Path, out: Path) -> None:
        src.write_bytes(changed)
        os.utime(src, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
        out.write_bytes(b"c")

    mocker.patch.object(rom_converto_service, "convert", AsyncMock(side_effect=convert))

    stats = await _run()

    assert stats["converted"] == 1
    assert stats["failed"] == 0
    assert stats["bytes_saved"] == -1
    assert source.read_bytes() == changed
    assert sorted(p.name for p in source.parent.iterdir()) == ["Game.chd", "Game.zip"]
    assert (source.parent / "Game.chd").read_bytes() == b"c"
    assert _reload(rom).fs_name == "Game.chd"
    # The file refresh afterwards may warn too, with no rom-converto binary in tests.
    assert any(
        "changed during the conversion" in call.args[0]
        for call in warning.call_args_list
    )


async def test_archive_removed_during_conversion_is_not_reported(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _archive_rom(
        library, admin_user, make_platform("psp"), {"Game.iso": b"x" * 100}
    )
    warning = mocker.patch("tasks.manual.convert_library.log.warning")

    def convert(operation, src: Path, out: Path) -> None:
        src.unlink()
        out.write_bytes(b"c")

    mocker.patch.object(rom_converto_service, "convert", AsyncMock(side_effect=convert))

    stats = await _run()

    assert stats["converted"] == 1
    assert _reload(rom).fs_name == "Game.chd"
    assert not any(
        "could not delete" in call.args[0] for call in warning.call_args_list
    )


async def test_a_single_file_rom_is_replaced_and_keeps_its_id(
    library: Path, admin_user: User, converto, converted
):
    psp = make_platform("psp")
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
    psx = make_platform("psx")
    cue = (
        'FILE "game (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\n'
        'FILE "game (Track 2).bin" BINARY\n  TRACK 02 AUDIO\n'
    )
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


async def test_a_bom_cue_and_playlist_still_follow_the_conversion(
    library: Path, admin_user: User, converto, converted
):
    bom = "\ufeff".encode()
    rom = _rom(
        library,
        admin_user,
        make_platform("psx"),
        {
            "game.cue": bom + b'FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n',
            "game.bin": b"x" * 50,
            "game.m3u": bom + b"./game.cue\n",
        },
        folder=True,
    )
    folder = library / rom.full_path

    await _run()

    assert sorted(p.name for p in folder.iterdir()) == ["game.chd", "game.m3u"]
    assert (folder / "game.m3u").read_text() == "game.chd\n"
    # Staged beside the rom folder, whose dot-prefixed subfolders count as its files.
    assert converted[0][1].parent.parent == library / rom.fs_path


async def test_one_roms_failure_does_not_stop_the_run(
    library: Path, admin_user: User, converto, converted, mocker
):
    _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
    _rom(library, admin_user, make_platform("psx"), {"game.cue": b""}, folder=True)
    mocker.patch(
        "tasks.manual.convert_library.refresh_rom_files",
        AsyncMock(side_effect=[RuntimeError("lock timeout"), None]),
    )

    stats = await _run()

    assert stats["failed"] == 1
    assert sorted(src for src, _ in converted) == ["game.cue", "game.iso"]


async def test_a_file_already_in_the_library_format_is_left_alone(
    library: Path, admin_user: User, converto, converted
):
    _rom(library, admin_user, make_platform("psp"), {"game.chd": b"x"})

    stats = await _run()

    assert stats["already_converted"] == 1
    assert converted == []


async def test_an_unmatched_rom_is_not_converted(
    library: Path, admin_user: User, converto, converted
):
    rom = _rom(
        library, admin_user, make_platform("psp"), {"game.iso": b"x"}, matched=False
    )

    stats = await _run()

    assert stats["unmatched"] == 1
    assert converted == []
    assert (library / rom.full_path).exists()


async def test_a_platform_without_a_library_format_is_skipped(
    library: Path, admin_user: User, converto, converted
):
    converto.platform_formats = {}
    _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})

    stats = await _run()

    assert stats["converted"] == 0
    assert converted == []


async def test_only_the_requested_platform_is_converted(
    library: Path, admin_user: User, converto, converted
):
    psp = make_platform("psp")
    _rom(library, admin_user, psp, {"game.iso": b"x" * 10})
    _rom(library, admin_user, make_platform("psx"), {"game.cue": b""}, folder=True)

    await _run(psp)

    assert [src for src, _ in converted] == ["game.iso"]


async def test_a_failed_conversion_leaves_the_original_and_no_staged_output(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
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
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
    (library / rom.fs_path / "game.chd").write_bytes(b"theirs")

    stats = await _run()

    assert stats["failed"] == 1
    assert converted == []
    assert (library / rom.fs_path / "game.chd").read_bytes() == b"theirs"
    assert (library / rom.full_path).exists()


async def test_an_output_appearing_during_conversion_is_never_overwritten(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
    theirs = library / rom.fs_path / "game.chd"

    def convert(operation, src: Path, out: Path) -> None:
        theirs.write_bytes(b"theirs")
        out.write_bytes(b"c")

    mocker.patch.object(rom_converto_service, "convert", AsyncMock(side_effect=convert))

    stats = await _run()

    assert stats["failed"] == 1
    assert theirs.read_bytes() == b"theirs"
    assert (library / rom.full_path).exists()


async def test_a_failed_rom_update_keeps_the_original(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
    mocker.patch.object(
        db_rom_handler, "update_rom", side_effect=SQLAlchemyError("conflict")
    )

    stats = await _run()

    assert stats["failed"] == 1
    assert sorted(p.name for p in (library / rom.fs_path).iterdir()) == ["game.iso"]


async def test_a_cue_track_held_by_another_rom_is_not_deleted(
    library: Path, admin_user: User, converto, converted
):
    psx = make_platform("psx")
    rom = _rom(
        library,
        admin_user,
        psx,
        {"game.cue": b'FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n'},
    )
    (library / rom.fs_path / "game.bin").write_bytes(b"x")
    make_rom(psx, "track", fs_stem="game", fs_extension="bin")

    stats = await _run(psx)

    assert stats["failed"] == 1
    assert converted == []
    assert (library / rom.fs_path / "game.bin").exists()


async def test_a_track_another_cue_shares_is_refused(
    library: Path, admin_user: User, converto, converted
):
    track = b'FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n'
    rom = _rom(
        library,
        admin_user,
        make_platform("psx"),
        {"disc 1.cue": track, "disc 2.cue": track, "game.bin": b"x"},
        folder=True,
    )

    stats = await _run()

    assert stats["failed"] == 2
    assert converted == []
    assert (library / rom.full_path / "game.bin").exists()


async def test_a_stage_left_by_a_killed_conversion_is_removed(
    library: Path, admin_user: User, converto, converted
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
    stale = library / rom.fs_path / ".romm_tmp_convert_old"
    stale.mkdir()
    os.utime(stale, (0, 0))

    await _run()

    assert not stale.exists()


async def test_a_rom_row_already_holding_the_output_name_is_left_alone(
    library: Path, admin_user: User, converto, converted
):
    psp = make_platform("psp")
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
        make_platform("psx"),
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
    _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})

    stats = await _run()

    assert stats["converted"] == 0
    assert converted == []
