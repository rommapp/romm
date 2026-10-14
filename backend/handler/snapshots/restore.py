"""A stored save restored as the files one emulator core reads, through sigil."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

from adapters.services.sigil import (
    NATIVE_SAVE_PLATFORM_SLUGS,
    SIGIL_RESTORE_PLATFORM_SLUGS,
    SigilGame,
    SigilService,
)
from adapters.services.sigil_restore import (
    RestoreCompanion,
    RestoredSave,
    RestoreTarget,
)
from handler.database import db_rom_handler, db_snapshot_handler
from handler.snapshots.legacy import sync_file
from models.assets import Save, SaveShape
from models.rom import Rom, RomFile

Restore = Callable[
    [bytes, SigilGame, RestoreTarget, list[RestoreCompanion]],
    Awaitable[RestoredSave],
]

# Units that travel as an archive, which no core reads as its save file.
_ARCHIVED_SHAPES: Final = frozenset({SaveShape.MULTI, SaveShape.FOLDER})


class NotConvertible(ValueError):
    """A save or platform no core conversion applies to."""


class ConversionUnavailable(RuntimeError):
    """This server lacks the sigil binding a conversion needs."""

    def __init__(self) -> None:
        super().__init__("Save conversion needs sigil, which this server lacks")


def restore_platform(platform_slug: str) -> str:
    """Sigil's slug for a RomM platform whose saves it restores.

    Raises:
        NotConvertible: sigil restores no saves for the platform.
    """
    sigil_platform = SIGIL_RESTORE_PLATFORM_SLUGS.get(platform_slug)
    if sigil_platform is None:
        raise NotConvertible(f"Saves for {platform_slug} can't be converted for a core")
    return sigil_platform


def convertible_rom(save: Save) -> Rom | None:
    """The save's ROM when a core needs it converted, or None when it serves as stored.

    Raises:
        NotConvertible: the save has no ROM, or is an archived unit on a
            platform sigil can't convert.
    """
    rom = save.rom
    if rom is None:
        raise NotConvertible(f"Save {save.id} has no ROM to convert it for")
    if rom.platform_slug not in NATIVE_SAVE_PLATFORM_SLUGS:
        return rom
    if save.shape in _ARCHIVED_SHAPES:
        raise NotConvertible(
            f"A {save.shape} save for {rom.platform_slug} can't be "
            "converted for a core"
        )
    return None


def _stored_game(rom: Rom) -> tuple[SigilGame, list[RomFile]]:
    restore_platform(rom.platform_slug)
    rom_files = db_rom_handler.rom_files_for_rom_id(rom.id)
    game = SigilService.stored_game(rom, rom_files)
    if game is None:
        raise ConversionUnavailable()
    return game, rom_files


def _content_path(save: Save, rom: Rom, rom_files: Sequence[RomFile]) -> str:
    """The ROM file name a restore names files after: the save's channel file,
    else the file the ROM's channels key to."""
    channel = (
        db_snapshot_handler.get_channel(save.channel_id) if save.channel_id else None
    )
    rom_file = (
        db_snapshot_handler.get_channel_file(channel) if channel else None
    ) or sync_file(rom_files)
    return rom_file.file_name if rom_file else rom.fs_name


async def _companions(
    companions: Sequence[tuple[Save, Path]],
) -> list[RestoreCompanion]:
    restored: list[RestoreCompanion] = []
    for save, path in companions:
        if save.rom is None:
            raise NotConvertible(f"Companion save {save.id} has no ROM")
        game, _ = _stored_game(save.rom)
        restored.append(
            RestoreCompanion(
                game_ids=game.game_ids, unit=await asyncio.to_thread(path.read_bytes)
            )
        )
    return restored


async def restore_for_core(
    save: Save,
    rom: Rom,
    file_path: Path,
    *,
    core: str,
    options: Mapping[str, str],
    profile: str | None,
    companions: Sequence[tuple[Save, Path]],
    restore: Restore,
) -> RestoredSave:
    """The save at `file_path` restored for `core` by `restore`.

    Args:
        companions: each companion save the caller may read, with its stored file.

    Raises:
        NotConvertible: sigil restores no saves for a game's platform.
        ConversionUnavailable: the sigil binding is absent.
        SaveRestoreError: sigil refused the restore.
    """
    game, rom_files = _stored_game(rom)
    restored_companions = await _companions(companions)
    target = RestoreTarget(
        core=core,
        options=options,
        profile=profile,
        content_path=_content_path(save, rom, rom_files),
    )
    unit = await asyncio.to_thread(file_path.read_bytes)
    return await restore(unit, game, target, restored_companions)
