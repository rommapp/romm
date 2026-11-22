import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from tests.factories import make_platform, make_rom, make_state
from tests.handler.snapshots.pushes import first_push, part, push, save_entry

from adapters.services.rom_converto import (
    RomConvertoOperationError,
    rom_converto_service,
)
from config.config_manager import ConvertoConfig
from config.config_manager import config_manager as cm
from handler.database import db_rom_handler, db_snapshot_handler
from handler.database.base_handler import sync_session
from handler.filesystem import fs_asset_handler, fs_rom_handler
from handler.rom_files import refresh_rom_files
from handler.snapshots.file_key import FileKey
from handler.snapshots.legacy import sync_file
from handler.snapshots.manifest import Manifest
from handler.snapshots.write import SAVE_PART, Outcome, write_snapshot
from models.assets import State
from models.channel import Channel
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
                sha1_hash=hashlib.sha1(data, usedforsecurity=False).hexdigest(),
                md5_hash=hashlib.md5(data, usedforsecurity=False).hexdigest(),
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


def _file(rom: Rom, file_name: str) -> RomFile:
    return next(f for f in _reload(rom).files if f.file_name == file_name)


def _channel(user: User, rom: Rom, file_name: str, label: str = "default") -> Channel:
    return db_snapshot_handler.add_channel(
        FileKey.of_file(_file(rom, file_name)).new_channel(
            user.id, rom.id, rom.platform_id, label
        )
    )


def _channel_file(channel: Channel) -> str | None:
    """The name of the library file the channel is keyed to now, if any."""
    stored = db_snapshot_handler.get_channel(channel.id)
    assert stored is not None
    rom_file = db_snapshot_handler.get_channel_file(stored)
    return rom_file.file_name if rom_file else None


def _listed(user: User, rom: Rom, file_name: str) -> list[str]:
    """The labels of the user's channels a client finds for the file."""
    key = FileKey.of_file(_file(rom, file_name))
    return sorted(
        c.label
        for c in db_snapshot_handler.get_channels_for_file(
            user.id, rom.platform_id, key
        )
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


async def test_a_bom_cue_and_playlist_still_follow_the_conversion(
    library: Path, admin_user: User, converto, converted
):
    bom = "\ufeff".encode()
    rom = _rom(
        library,
        admin_user,
        make_platform("psx"),
        {
            "game.cue": bom + b'FILE "game.bin" BINARY\n',
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
    psp_rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
    _rom(library, admin_user, make_platform("psx"), {"game.cue": b""}, folder=True)
    real_refresh = refresh_rom_files

    async def refresh(rom: Rom, **kwargs):
        if rom.id == psp_rom.id:
            raise RuntimeError("lock timeout")
        return await real_refresh(rom, **kwargs)

    mocker.patch(
        "tasks.manual.convert_library.refresh_rom_files", AsyncMock(side_effect=refresh)
    )

    stats = await _run()

    assert stats["failed"] == 1
    assert stats["converted"] == 1
    assert sorted(src for src, _ in converted) == ["game.cue", "game.iso"]
    assert sorted(p.name for p in (library / psp_rom.fs_path).iterdir()) == ["game.iso"]
    assert _reload(psp_rom).fs_name == "game.iso"


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
    rom = _rom(library, admin_user, psx, {"game.cue": b'FILE "game.bin" BINARY\n'})
    (library / rom.fs_path / "game.bin").write_bytes(b"x")
    make_rom(psx, "track", fs_stem="game", fs_extension="bin")

    stats = await _run(psx)

    assert stats["failed"] == 1
    assert converted == []
    assert (library / rom.fs_path / "game.bin").exists()


async def test_a_track_another_cue_shares_is_refused(
    library: Path, admin_user: User, converto, converted
):
    track = b'FILE "game.bin" BINARY\n'
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


async def test_every_users_channels_follow_a_converted_file(
    library: Path, admin_user: User, editor_user: User, converto, converted
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x" * 100})
    ours = _channel(admin_user, rom, "game.iso")
    theirs = _channel(editor_user, rom, "game.iso", "Second run")
    with sync_session.begin() as session:
        session.execute(
            update(Channel).values(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        )
    played = db_snapshot_handler.get_channel(ours.id)

    await _run()

    assert _channel_file(ours) == _channel_file(theirs) == "game.chd"
    assert _listed(admin_user, rom, "game.chd") == ["default"]
    assert _listed(editor_user, rom, "game.chd") == ["Second run"]
    # Moving a channel is not a play, so it keeps its place in the user's list.
    moved = db_snapshot_handler.get_channel(ours.id)
    assert played is not None and moved is not None
    assert moved.updated_at == played.updated_at


async def test_a_push_into_a_converted_games_channel_is_accepted(
    library: Path, tmp_path: Path, admin_user: User, converto, converted, monkeypatch
):
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(fs_asset_handler, "base_path", assets.resolve())
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x" * 100})
    first = await first_push(admin_user, rom, _file(rom, "game.iso"))

    await _run()

    later = b"later progress"
    result = await write_snapshot(
        push(
            admin_user,
            _reload(rom),
            _file(rom, "game.chd"),
            Manifest(save=save_entry(later)),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
            parts={SAVE_PART: part(later)},
        )
    )

    assert result.outcome == Outcome.CREATED
    assert result.snapshot.channel_id == first.snapshot.channel_id
    assert result.snapshot.parent_snapshot_id == first.snapshot.id


async def test_each_disc_and_playlist_channel_follows_its_own_file(
    library: Path, admin_user: User, converto, converted, mocker
):
    def convert(operation, src: Path, out: Path) -> None:
        out.write_bytes(src.name.encode())

    mocker.patch.object(rom_converto_service, "convert", AsyncMock(side_effect=convert))
    rom = _rom(
        library,
        admin_user,
        make_platform("psx"),
        {
            "game (Disc 1).cue": b'FILE "game (Disc 1).bin" BINARY\n',
            "game (Disc 1).bin": b"1" * 50,
            "game (Disc 2).cue": b'FILE "game (Disc 2).bin" BINARY\n',
            "game (Disc 2).bin": b"2" * 50,
            "game.m3u": b"game (Disc 1).cue\ngame (Disc 2).cue\n",
        },
        folder=True,
    )
    _channel(admin_user, rom, "game (Disc 1).cue")
    _channel(admin_user, rom, "game (Disc 2).cue", "Disc 2 run")
    _channel(admin_user, rom, "game.m3u", "Playlist run")

    await _run()

    after = _reload(rom)
    assert sorted(f.file_name for f in after.files) == [
        "game (Disc 1).chd",
        "game (Disc 2).chd",
        "game.m3u",
    ]
    assert _listed(admin_user, rom, "game (Disc 1).chd") == ["default"]
    assert _listed(admin_user, rom, "game (Disc 2).chd") == ["Disc 2 run"]
    assert _listed(admin_user, rom, "game.m3u") == ["Playlist run"]
    chosen = sync_file(after.files)
    assert chosen is not None and chosen.file_name == "game (Disc 1).chd"


async def test_a_channel_on_the_sync_file_moves_to_the_roms_new_sync_file(
    library: Path, admin_user: User, converto, converted
):
    # With the cue gone, the first file by name is the sync file, and this playlist sorts first.
    rom = _rom(
        library,
        admin_user,
        make_platform("psx"),
        {
            "game_disc1.cue": b'FILE "game_disc1.bin" BINARY\n',
            "game_disc1.bin": b"x" * 50,
            "game.m3u": b"game_disc1.cue\n",
        },
        folder=True,
    )
    _channel(admin_user, rom, "game_disc1.cue")

    await _run()

    chosen = sync_file(_reload(rom).files)
    assert chosen is not None and chosen.file_name == "game.m3u"
    assert _listed(admin_user, rom, "game.m3u") == ["default"]


async def test_a_copy_of_the_file_in_another_rom_keeps_its_channels(
    library: Path, admin_user: User, converto, converted
):
    psp = make_platform("psp")
    rom = _rom(library, admin_user, psp, {"game.iso": b"x" * 100})
    copy = make_rom(psp, "copy", fs_extension="iso")
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=copy.id,
            file_name="copy.iso",
            file_path=copy.fs_path,
            file_size_bytes=100,
            sha1_hash=_file(rom, "game.iso").sha1_hash,
        )
    )
    kept = _channel(admin_user, copy, "copy.iso")

    await _run()

    stored = db_snapshot_handler.get_channel(kept.id)
    assert stored is not None and FileKey.of_channel(stored) == FileKey.of_channel(kept)


async def test_a_failed_conversion_leaves_the_channels_on_the_original(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x"})
    channel = _channel(admin_user, rom, "game.iso")
    mocker.patch.object(
        rom_converto_service,
        "convert",
        AsyncMock(side_effect=RomConvertoOperationError("boom")),
    )

    await _run()

    assert _channel_file(channel) == "game.iso"


def _discs(library: Path, admin_user: User) -> Rom:
    return _rom(
        library,
        admin_user,
        make_platform("psx"),
        {
            "game (Disc 1).cue": b'FILE "game (Disc 1).bin" BINARY\n',
            "game (Disc 1).bin": b"1" * 50,
            "game (Disc 2).cue": b'FILE "game (Disc 2).bin" BINARY\n',
            "game (Disc 2).bin": b"2" * 50,
            "game.m3u": b"game (Disc 1).cue\ngame (Disc 2).cue\n",
        },
        folder=True,
    )


def _distinct_outputs(mocker, fail: str | None = None) -> None:
    """Fake rom-converto writing each output from its source's name, failing on `fail`."""

    def convert(operation, src: Path, out: Path) -> None:
        if src.name == fail:
            raise RomConvertoOperationError("boom")
        out.write_bytes(src.name.encode())

    mocker.patch.object(rom_converto_service, "convert", AsyncMock(side_effect=convert))


async def test_a_disc_left_unconverted_does_not_take_the_converted_discs_channels(
    library: Path, admin_user: User, converto, converted, mocker
):
    _distinct_outputs(mocker, fail="game (Disc 2).cue")
    rom = _discs(library, admin_user)
    _channel(admin_user, rom, "game (Disc 1).cue", "Disc 1 run")
    _channel(admin_user, rom, "game (Disc 2).cue", "Disc 2 run")

    await _run()
    _distinct_outputs(mocker)
    await _run()

    assert _listed(admin_user, rom, "game (Disc 1).chd") == ["Disc 1 run"]
    assert _listed(admin_user, rom, "game (Disc 2).chd") == ["Disc 2 run"]


async def test_a_sync_file_channel_keeps_its_disc_when_its_label_is_taken(
    library: Path, admin_user: User, converto, converted
):
    rom = _rom(
        library,
        admin_user,
        make_platform("psx"),
        {
            "game_disc1.cue": b'FILE "game_disc1.bin" BINARY\n',
            "game_disc1.bin": b"x" * 50,
            "game.m3u": b"game_disc1.cue\n",
        },
        folder=True,
    )
    on_disc = _channel(admin_user, rom, "game_disc1.cue")
    on_playlist = _channel(admin_user, rom, "game.m3u", "DEFAULT")

    await _run()

    assert _listed(admin_user, rom, "game.m3u") == ["DEFAULT"]
    assert _channel_file(on_playlist) == "game.m3u"
    assert _channel_file(on_disc) == "game_disc1.chd"


async def test_channels_move_before_the_originals_are_deleted(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x" * 100})
    channel = _channel(admin_user, rom, "game.iso")
    original = library / rom.full_path
    real_refresh = refresh_rom_files

    async def refresh(rom: Rom, **kwargs):
        if not original.exists():
            raise RuntimeError("lock timeout")
        return await real_refresh(rom, **kwargs)

    mocker.patch(
        "tasks.manual.convert_library.refresh_rom_files", AsyncMock(side_effect=refresh)
    )

    await _run()

    assert sorted(p.name for p in (library / rom.fs_path).iterdir()) == ["game.chd"]
    assert _channel_file(channel) == "game.chd"


async def test_a_refresh_missing_the_output_keeps_the_originals_and_channels(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x" * 100})
    channel = _channel(admin_user, rom, "game.iso")
    # A refresh that keeps the old rows, as one does when the mount drops out.
    mocker.patch("tasks.manual.convert_library.refresh_rom_files", AsyncMock())

    stats = await _run()

    assert stats["failed"] == 1
    assert sorted(p.name for p in (library / rom.fs_path).iterdir()) == ["game.iso"]
    assert _reload(rom).fs_name == "game.iso"
    assert _channel_file(channel) == "game.iso"


async def test_snapshots_take_the_converted_files_hash(
    library: Path, tmp_path: Path, admin_user: User, converto, converted, monkeypatch
):
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(fs_asset_handler, "base_path", assets.resolve())
    rom = _rom(library, admin_user, make_platform("psp"), {"game.iso": b"x" * 100})
    first = await first_push(admin_user, rom, _file(rom, "game.iso"))

    await _run()

    snapshot = db_snapshot_handler.get_snapshot(first.snapshot.id)
    assert snapshot is not None
    assert snapshot.rom_sha1 == _file(rom, "game.chd").sha1_hash


async def test_a_state_keeps_the_disc_it_was_captured_on(
    library: Path, admin_user: User, converto, converted, mocker
):
    _distinct_outputs(mocker)
    rom = _discs(library, admin_user)
    state = make_state(
        rom, admin_user, "disc2.state", disc_file_id=_file(rom, "game (Disc 2).cue").id
    )

    await _run()

    with sync_session.begin() as session:
        stored = session.get_one(State, state.id)
        assert stored.disc_file_id == _file(rom, "game (Disc 2).chd").id


async def test_a_failed_playlist_rewrite_removes_the_outputs(
    library: Path, admin_user: User, converto, converted, mocker
):
    rom = _discs(library, admin_user)
    folder = library / rom.full_path
    before = sorted(p.name for p in folder.iterdir())
    read_only = mocker.patch.object(
        fs_rom_handler, "_atomic_write", side_effect=OSError("read-only")
    )

    stats = await _run()

    assert stats["failed"] == 2
    assert sorted(p.name for p in folder.iterdir()) == before

    mocker.stop(read_only)
    stats = await _run()

    assert stats["converted"] == 2


async def test_the_originals_are_not_reread_and_the_rom_hash_covers_the_outputs(
    library: Path, admin_user: User, converto, converted, mocker
):
    _distinct_outputs(mocker)
    rom = _discs(library, admin_user)
    hashed = mocker.spy(fs_rom_handler, "_calculate_rom_hashes")

    await _run()

    read = sorted(call.args[0].name for call in hashed.call_args_list)
    assert not [name for name in read if name.endswith((".cue", ".bin"))]
    # Each output is read once for its own hash and once for the ROM-level hash.
    assert read.count("game (Disc 1).chd") == 2
    after = _reload(rom)
    full = await fs_rom_handler.get_rom_files(after)
    assert after.sha1_hash == full.sha1_hash != ""
