"""Memory cards and backup RAM volumes built for tests of sigil's card handling."""

import io
import struct
import tempfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

from tests._zipfile_shim import reload_zipfile

PS1_FRAME = 128
PS1_BLOCK = 8192
GAMECUBE_BLOCK = 8192
SATURN_BLOCK = 64
SATURN_VOLUME = 32 * 1024
# Past the archive block's save fields and its empty block list's terminator.
SATURN_DATA_OFFSET = 0x24
SATURN_DATA = SATURN_BLOCK - SATURN_DATA_OFFSET


def ps1_card(
    saves: list[tuple[str, int]], fills: dict[int, int] | None = None
) -> bytes:
    """A raw PS1 card: `saves` is (directory name, block count) each, laid out in
    order, and `fills` sets a block's data to one byte."""
    card = bytearray(128 * 1024)
    card[0:2] = b"MC"
    for frame in range(1, 16):
        card[frame * PS1_FRAME] = 0xA0
        card[frame * PS1_FRAME + 8 : frame * PS1_FRAME + 10] = b"\xff\xff"
    block = 1
    for name, blocks in saves:
        for i in range(blocks):
            frame = (block + i) * PS1_FRAME
            state = 0x51 if i == 0 else (0x53 if i == blocks - 1 else 0x52)
            link = 0xFFFF if i == blocks - 1 else block + i
            card[frame : frame + 4] = struct.pack("<I", state)
            card[frame + 4 : frame + 8] = struct.pack(
                "<I", blocks * PS1_BLOCK if i == 0 else 0
            )
            card[frame + 8 : frame + 10] = struct.pack("<H", link)
            if i == 0:
                card[frame + 10 : frame + 10 + len(name)] = name.encode("ascii")
        block += blocks
    for index, value in (fills or {}).items():
        card[index * PS1_BLOCK : (index + 1) * PS1_BLOCK] = bytes([value]) * PS1_BLOCK
    return bytes(card)


def saturn_volume(saves: list[tuple[str, int]]) -> bytes:
    """A 32 KiB Saturn internal backup RAM volume: `saves` is (name, fill byte)
    each, one block apiece holding SATURN_DATA bytes."""
    volume = bytearray(SATURN_VOLUME)
    volume[:SATURN_BLOCK] = b"BackUpRam Format" * (SATURN_BLOCK // 16)
    for block, (name, fill) in enumerate(saves, start=2):
        archive = bytearray(SATURN_BLOCK)
        archive[0:4] = struct.pack(">I", 0x80000000)
        archive[4:15] = name.encode("ascii").ljust(11, b"\0")
        archive[0x1E:0x22] = struct.pack(">I", SATURN_DATA)
        archive[SATURN_DATA_OFFSET:] = bytes([fill]) * SATURN_DATA
        volume[block * SATURN_BLOCK : (block + 1) * SATURN_BLOCK] = archive
    return bytes(volume)


def gci(game_code: str, maker: str, name: str, blocks: int, fill: int) -> bytes:
    """A GameCube save file as Dolphin exports it: its directory entry, then its blocks."""
    entry = bytearray(b"\xff" * 64)
    entry[0:4] = game_code.encode("ascii")
    entry[4:6] = maker.encode("ascii")
    entry[7] = 0
    entry[8:40] = name.encode("ascii").ljust(32, b"\0")
    entry[0x28:0x34] = bytes(12)
    entry[0x34] = 4
    entry[0x35] = 0
    entry[0x36:0x3A] = struct.pack(">HH", 0, blocks)
    entry[0x3C:0x40] = bytes(4)
    return bytes(entry) + bytes([fill]) * (GAMECUBE_BLOCK * blocks)


def ps2_folder_unit(folder: str, data: bytes) -> bytes:
    """A PS2 save as a zip of one PCSX2 save folder, a shape sigil's restore reads."""
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"{folder}/data", data)
    return buffer.getvalue()


def _built_card(
    binding: ModuleType,
    core: str,
    options: dict[str, str],
    path: str,
    saves: list[tuple[Any, bytes]],
) -> bytes:
    """A shared card sigil builds by restoring each (game result, unit) onto it in turn."""
    with tempfile.TemporaryDirectory() as tmp:
        for game, unit in saves:
            binding.restore(
                unit,
                game,
                core,
                "game.iso",
                tmp,
                options=options,
                game_ids=(game.title_id,),
                mode="unmanaged",
                overwrite_local=True,
            )
        return Path(tmp, path).read_bytes()


def ps2_card(binding: ModuleType, saves: list[tuple[Any, bytes]]) -> bytes:
    """An 8 MiB PCSX2 card holding each (game result, folder unit)."""
    return _built_card(binding, "pcsx2", {}, "Mcd001.ps2", saves)


def gamecube_card(
    binding: ModuleType, saves: list[tuple[Any, bytes]], region: str = "USA"
) -> bytes:
    """A Dolphin raw card of `region`'s folder holding each (game result, gci)."""
    return _built_card(
        binding,
        "dolphin",
        {"SlotA": "1"},
        f"User/GC/MemoryCardA.{region}.raw",
        saves,
    )


def card_entries(binding: ModuleType, data: bytes) -> dict[str, str]:
    """Each save on a card by name, with the game id it carries."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "card")
        path.write_bytes(data)
        listing = binding.list_card(path)
    return {entry.name: entry.owner_id for entry in listing.entries}
