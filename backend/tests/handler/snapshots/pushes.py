"""Builders for the pushes the snapshot tests send."""

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import func, select
from tests.factories import make_platform, make_rom

from handler.auth.rom_visibility import UNRESTRICTED
from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from handler.filesystem import fs_asset_handler
from handler.snapshots.manifest import Manifest, SaveEntry
from handler.snapshots.write import (
    SAVE_PART,
    ChannelTarget,
    SnapshotWrite,
    UploadPart,
    WriteResult,
    state_part,
    write_snapshot,
)
from models.assets import SaveFormat, SaveShape
from models.channel import DEFAULT_CHANNEL_LABEL
from models.rom import Rom, RomFile
from models.user import User

SRAM = b"sram-bytes"
STATE_A = b"state-a"
STATE_B = b"state-b"


def md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def red_ram(changes: dict[int, int] | None = None) -> bytes:
    """A 32 KiB Pokemon Red RAM with `changes` written in and a valid main-data
    checksum, the complement of the 8-bit sum of 0x2598-0x3522, stored at 0x3523."""
    ram = bytearray((i * 31 + i // 97) & 0xFF for i in range(0x8000))
    for offset, value in (changes or {}).items():
        ram[offset] = value
    ram[0x3523] = ~sum(ram[0x2598:0x3523]) & 0xFF
    return bytes(ram)


def pokemon_red(features: int) -> tuple[Rom, RomFile]:
    """A Pokemon Red ROM on gb whose file carries the sigil cart `features`."""
    rom = make_rom(make_platform("gb"), "Pokemon Red")
    rom_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Pokemon Red.gb",
            file_path=rom.fs_path,
            file_size_bytes=1024,
            sha1_hash="b" * 40,
            sigil_features=features,
        )
    )
    return rom, rom_file


def stored_files(base: Path) -> list[Path]:
    return sorted(path for path in base.rglob("*") if path.is_file())


def stored_bytes(full_path: str) -> bytes:
    return (fs_asset_handler.base_path / full_path).read_bytes()


def save_entry(data: bytes = SRAM, fmt: SaveFormat = SaveFormat.NEUTRAL) -> SaveEntry:
    return SaveEntry(hash=md5(data), shape=SaveShape.SINGLE, format=fmt)


def push(
    user: User,
    rom: Rom,
    rom_file: RomFile,
    manifest: Manifest,
    expected: int | None,
    channel_id: uuid.UUID | None = None,
    label: str | None = DEFAULT_CHANNEL_LABEL,
    parts: dict[str, UploadPart] | None = None,
    device_id: str | None = None,
    **fields,
) -> SnapshotWrite:
    return SnapshotWrite(
        author=user,
        rom=rom,
        rom_file=rom_file,
        visibility=UNRESTRICTED,
        manifest=manifest,
        channel=ChannelTarget(expected_current_id=expected, id=channel_id, label=label),
        parts=parts or {},
        device_id=device_id,
        **fields,
    )


def part(data: bytes, name: str = "game.srm") -> UploadPart:
    return UploadPart(content=data, file_name=name)


def count(model) -> int:
    with sync_session() as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


async def first_push(user: User, rom: Rom, rom_file: RomFile, **fields) -> WriteResult:
    return await write_snapshot(
        push(
            user,
            rom,
            rom_file,
            Manifest(
                save=save_entry(),
                states={"snes9x": {"auto": md5(STATE_A)}},
                emulator="argosy",
            ),
            expected=None,
            parts={
                SAVE_PART: part(SRAM),
                state_part("snes9x", "auto"): part(STATE_A, "game.state"),
            },
            **fields,
        )
    )


async def push_save(
    user: User, rom: Rom, rom_file: RomFile, previous: WriteResult, data: bytes
) -> WriteResult:
    """Push `data` as the next save on top of `previous`."""
    return await write_snapshot(
        push(
            user,
            rom,
            rom_file,
            Manifest(save=save_entry(data)),
            expected=previous.snapshot.id,
            channel_id=previous.snapshot.channel_id,
            parts={SAVE_PART: part(data)},
        )
    )
