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


XBOX_DRIVE_E = 0xABE80000
XBOX_DRIVE_E_SIZE = 0x131F00000


def xbox_drive() -> bytes:
    """A blank Xbox hard-disk image as xemu keeps one: an 8 GiB qcow2 image
    holding a FATX partition E: with an empty root directory."""
    cluster = 0x10000
    per_l2 = cluster // 8
    size = 0x200000000
    fat_bytes = ((XBOX_DRIVE_E_SIZE // 0x4000 + 1) * 4 + 0xFFF) & ~0xFFF
    root = XBOX_DRIVE_E + 0x1000 + fat_bytes
    guest: dict[int, bytearray] = {}

    def put(offset: int, data: bytes) -> None:
        at = offset % cluster
        guest.setdefault(offset // cluster, bytearray(cluster))[
            at : at + len(data)
        ] = data

    superblock = b"FATX" + struct.pack("<III", 0x0D03A0, 32, 1) + b"\x00\x00"
    put(XBOX_DRIVE_E, superblock + b"\xff" * (0x1000 - len(superblock)))
    put(XBOX_DRIVE_E + 0x1000, struct.pack("<II", 0xFFFFFFF8, 0xFFFFFFFF))
    put(root, b"\xff" * 0x4000)

    # The header, the refcount table and its one block, the L1 table, one L2
    # table, then the drive's clusters.
    refcount_table, refcount_block, l1, l2, data = (n * cluster for n in range(1, 6))
    image = bytearray(data + len(guest) * cluster)
    for n, (index, content) in enumerate(sorted(guest.items())):
        host = data + n * cluster
        image[host : host + cluster] = content
        struct.pack_into(">Q", image, l2 + (index % per_l2) * 8, host | 1 << 63)
    struct.pack_into(
        ">Q", image, l1 + (XBOX_DRIVE_E // cluster // per_l2) * 8, l2 | 1 << 63
    )
    struct.pack_into(">Q", image, refcount_table, refcount_block)
    for n in range(len(image) // cluster):
        struct.pack_into(">H", image, refcount_block + n * 2, 1)
    struct.pack_into(
        ">IIQIIQIIQQIIQ",
        image,
        0,
        0x514649FB,
        3,
        0,
        0,
        16,
        size,
        0,
        size // (cluster * per_l2),
        l1,
        refcount_table,
        1,
        0,
        0,
    )
    struct.pack_into(">QQQII", image, 72, 0, 0, 0, 4, 104)
    return bytes(image)
