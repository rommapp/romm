"""Restores through the real sigil binding; every test skips where it isn't built."""

import io
import struct
import zipfile
from pathlib import Path
from types import ModuleType

import pytest
from tests._zipfile_shim import reload_zipfile
from tests.sigil_cards import (
    PS1_BLOCK,
    SATURN_BLOCK,
    SATURN_DATA,
    SATURN_DATA_OFFSET,
    ps1_card,
    saturn_volume,
)

from adapters.services.sigil import SigilGame
from adapters.services.sigil_restore import (
    ContainerMismatch,
    RefusalCode,
    RestoreCompanion,
    RestoreTarget,
    SharedContainerRequired,
    SigilRefusal,
    merge_into_container,
    restore_layouts,
    restore_per_game,
)

SEGACD_BLOCK = 64
SEGACD_VOLUME = 0x2000


@pytest.fixture
def binding() -> ModuleType:
    module: ModuleType = pytest.importorskip("sigil")
    return module


def _crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1) & 0xFFFF
    return crc


def _gf_mul(bits: int, poly: int, a: int, b: int) -> int:
    product = 0
    while b:
        if b & 1:
            product ^= a
        b >>= 1
        a <<= 1
        if a & (1 << bits):
            a ^= poly
    return product


# (bits, polynomial, 1/(alpha+1), alpha powers), as sigil's card_segacd.c has them.
_GF6 = (6, 0x43, 0x3E, (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x03, 0x06))
_GF8 = (8, 0x11D, 0xF4, (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80))
_RS6_LAST = (0x2D, 0x2E, 0x2F, 0x08, 0x11, 0x1A, 0x23, 0x2C)


def _rs_encode(field: tuple[int, int, int, tuple[int, ...]], code: list[int]) -> None:
    bits, poly, inverse, alpha = field
    s0 = s1 = 0
    for i in range(6):
        s0 ^= code[i]
        s1 ^= _gf_mul(bits, poly, code[i], alpha[7 - i])
    code[6] = _gf_mul(bits, poly, s0 ^ s1, inverse)
    code[7] = s0 ^ code[6]


def _rs6_pos(column: int, i: int) -> int:
    if i < 5:
        return column + i * 9
    if i == 5:
        return _RS6_LAST[column]
    return (0x30 if i == 6 else 0x38) + column


def _segacd_block(payload: bytes) -> bytes:
    """A directory block as the Mega CD BIOS protects it: CRC, then two
    Reed-Solomon passes."""
    crc = _crc16(payload)
    buf = (
        bytes([crc >> 8, crc & 0xFF]) + payload + bytes([~crc >> 8 & 0xFF, ~crc & 0xFF])
    )
    out = bytearray(SEGACD_BLOCK)
    for group in range(12):
        value = int.from_bytes(buf[3 * group : 3 * group + 3], "big")
        for k in range(4):
            out[4 * group + k] = ((value >> (18 - 6 * k)) & 0x3F) << 2
    for column in range(8):
        code = [out[_rs6_pos(column, i)] >> 2 for i in range(8)]
        _rs_encode(_GF6, code)
        for i in range(8):
            at = _rs6_pos(column, i)
            out[at] = (code[i] << 2) | (out[at] & 3)
    for column in range(8):
        code = [
            sum(((out[column + 8 * r] >> (7 - j)) & 1) << (7 - r) for r in range(8))
            for j in range(8)
        ]
        _rs_encode(_GF8, code)
        for r in range(8):
            out[column + 8 * r] = sum(
                ((code[j] >> (7 - r)) & 1) << (7 - j) for j in range(8)
            )
    return bytes(out)


def segacd_volume(saves: list[tuple[str, int, int]]) -> bytes:
    """An 8 KiB Sega CD backup RAM volume: `saves` is (name, blocks, fill byte) each."""
    blocks = SEGACD_VOLUME // SEGACD_BLOCK
    volume = bytearray(SEGACD_VOLUME)
    directory: dict[int, bytearray] = {}
    start = 1
    for slot, (name, count, fill) in enumerate(saves):
        volume[start * SEGACD_BLOCK : (start + count) * SEGACD_BLOCK] = (
            bytes([fill]) * count * SEGACD_BLOCK
        )
        entry = name.encode("ascii").ljust(11, b"\0") + b"\0"
        entry += struct.pack(">HH", start, count)
        half = 0 if slot & 1 else 16
        directory.setdefault(blocks - 2 - slot // 2, bytearray(32))[
            half : half + 16
        ] = entry
        start += count
    for block, payload in directory.items():
        volume[block * SEGACD_BLOCK : (block + 1) * SEGACD_BLOCK] = _segacd_block(
            bytes(payload)
        )
    files = len(saves)
    end = blocks - 1 - (files + 1) // 2
    held = 0 if files & 1 else 1
    free = max(end - start - held, 0)
    form = bytearray(SEGACD_BLOCK)
    form[0:11] = b"_" * 11
    form[0x0B:0x10] = b"\0\0\0\0\x40"
    form[0x10:0x18] = struct.pack(">4H", *[free] * 4)
    form[0x18:0x20] = struct.pack(">4H", *[files] * 4)
    form[0x20:0x40] = b"SEGA_CD_ROM\0\1\0\0\0RAM_CARTRIDGE___"
    volume[-SEGACD_BLOCK:] = form
    return bytes(volume)


def saturn_saves(binding: ModuleType, data: bytes, tmp_path: Path) -> dict[str, bytes]:
    """Each save on a Saturn volume by name, with its data bytes."""
    path = tmp_path / "listed.bkr"
    path.write_bytes(data)
    saves: dict[str, bytes] = {}
    for entry in binding.list_card(path).entries:
        start = entry.first_block * SATURN_BLOCK + SATURN_DATA_OFFSET
        saves[entry.name] = data[start : start + SATURN_DATA]
    return saves


def card_saves(binding: ModuleType, data: bytes, tmp_path: Path) -> dict[str, bytes]:
    """Each save on a card or volume by name, with its first block's bytes."""
    path = tmp_path / "listed.card"
    path.write_bytes(data)
    listing = binding.list_card(path)
    block = PS1_BLOCK if listing.format.startswith("ps1") else SEGACD_BLOCK
    return {
        entry.name: data[entry.first_block * block : (entry.first_block + 1) * block]
        for entry in listing.entries
    }


def collected(
    binding: ModuleType,
    game: SigilGame,
    core: str,
    content_path: str,
    files: dict[str, bytes],
    tmp_path: Path,
    **kwargs: object,
) -> bytes:
    """The unit sigil collects from `files`, as a client running sigil uploads it."""
    source = tmp_path / "source"
    source.mkdir(parents=True)
    for name, data in files.items():
        (source / name).write_bytes(data)
    unit = binding.collect(game.result, core, content_path, source, **kwargs).data
    assert isinstance(unit, bytes)
    return unit


def cross(binding: ModuleType) -> SigilGame:
    return SigilGame(
        result=binding.SigilResult.persisted("psx", "SLUS-01041", "SLUS-01041", 0),
        game_ids=("SLUS-01041",),
    )


def lunar(binding: ModuleType) -> SigilGame:
    return SigilGame(
        result=binding.SigilResult.persisted("segacd", "", "", 0), game_ids=()
    )


def target(core: str, content_path: str, **options: str) -> RestoreTarget:
    return RestoreTarget(
        core=core, options=options, profile=None, content_path=content_path
    )


@pytest.mark.asyncio
async def test_a_per_game_ps1_card_is_built_from_nothing(binding, tmp_path: Path):
    game = cross(binding)
    card = ps1_card([("BASLUSP01041CROSS", 2)], {1: 0x11})
    unit = collected(
        binding,
        game,
        "pcsx_rearmed",
        "Chrono Cross.cue",
        {"Chrono Cross.srm": card},
        tmp_path,
    )

    restored = await restore_per_game(
        unit, game, target("duckstation", "Chrono Cross.cue", Card1Type="PerGame")
    )

    assert list(restored.files) == ["memcards/SLUS-01041_1.mcd"]
    saves = card_saves(binding, restored.files["memcards/SLUS-01041_1.mcd"], tmp_path)
    assert saves == {"BASLUSP01041CROSS": bytes([0x11]) * PS1_BLOCK}


@pytest.mark.asyncio
async def test_a_shared_card_target_names_the_container(binding, tmp_path: Path):
    game = cross(binding)
    unit = collected(
        binding,
        game,
        "pcsx_rearmed",
        "Chrono Cross.cue",
        {"Chrono Cross.srm": ps1_card([("BASLUSP01041CROSS", 2)])},
        tmp_path,
    )

    with pytest.raises(SharedContainerRequired) as excinfo:
        await restore_per_game(
            unit,
            game,
            target("pcsx_rearmed", "Chrono Cross.cue", pcsx_rearmed_memcard1="shared"),
        )

    assert excinfo.value.container_path == "pcsx-card1.mcd"


@pytest.mark.asyncio
async def test_a_ps1_shared_card_merge_keeps_another_games_save(
    binding, tmp_path: Path
):
    game = cross(binding)
    unit = collected(
        binding,
        game,
        "pcsx_rearmed",
        "Chrono Cross.cue",
        {"Chrono Cross.srm": ps1_card([("BASLUSP01041CROSS", 2)], {1: 0x11, 2: 0x11})},
        tmp_path,
    )
    sent = ps1_card(
        [("BASLUSP01041CROSS", 2), ("BASLUS-00067OTHER", 1)],
        {1: 0x22, 2: 0x22, 3: 0x33},
    )

    restored = await merge_into_container(
        unit,
        game,
        target("pcsx_rearmed", "Chrono Cross.cue", pcsx_rearmed_memcard1="shared"),
        "pcsx-card1.mcd",
        sent,
    )

    assert list(restored.files) == ["pcsx-card1.mcd"]
    saves = card_saves(binding, restored.files["pcsx-card1.mcd"], tmp_path)
    assert saves == {
        "BASLUSP01041CROSS": bytes([0x11]) * PS1_BLOCK,
        "BASLUS-00067OTHER": bytes([0x33]) * PS1_BLOCK,
    }


@pytest.mark.asyncio
async def test_a_segacd_volume_merge_replaces_only_the_games_save(
    binding, tmp_path: Path
):
    game = lunar(binding)
    unit = collected(
        binding,
        game,
        "genesis_plus_gx",
        "Lunar (USA).cue",
        {"scd_U.brm": segacd_volume([("LUNAR_SAVE1", 2, 0x11)])},
        tmp_path,
        claimed=["LUNAR_SAVE1"],
    )
    sent = segacd_volume([("OTHER_GAME1", 1, 0x33), ("LUNAR_SAVE1", 2, 0x22)])

    restored = await merge_into_container(
        unit, game, target("genesis_plus_gx", "Lunar (USA).cue"), "scd_U.brm", sent
    )

    saves = card_saves(binding, restored.files["scd_U.brm"], tmp_path)
    assert saves == {
        "OTHER_GAME1": bytes([0x33]) * SEGACD_BLOCK,
        "LUNAR_SAVE1": bytes([0x11]) * SEGACD_BLOCK,
    }


@pytest.mark.asyncio
async def test_a_segacd_volume_of_another_region_is_refused(binding, tmp_path: Path):
    game = lunar(binding)
    unit = collected(
        binding,
        game,
        "genesis_plus_gx",
        "Lunar (USA).cue",
        {"scd_U.brm": segacd_volume([("LUNAR_SAVE1", 2, 0x11)])},
        tmp_path,
        claimed=["LUNAR_SAVE1"],
    )
    sent = segacd_volume([("OTHER_GAME1", 1, 0x33)])

    with pytest.raises(ContainerMismatch) as excinfo:
        await merge_into_container(
            unit, game, target("genesis_plus_gx", "Lunar (USA).cue"), "scd_E.brm", sent
        )
    assert excinfo.value.written == ("scd_U.brm",)
    assert excinfo.value.options == {"genesis_plus_gx_region_detect": None}

    forced = await merge_into_container(
        unit,
        game,
        target(
            "genesis_plus_gx", "Lunar (USA).cue", genesis_plus_gx_region_detect="pal"
        ),
        "scd_E.brm",
        sent,
    )
    assert set(card_saves(binding, forced.files["scd_E.brm"], tmp_path)) == {
        "OTHER_GAME1",
        "LUNAR_SAVE1",
    }


def saturn_game(binding: ModuleType, *game_ids: str) -> SigilGame:
    return SigilGame(
        result=binding.SigilResult.persisted("saturn", "", "", 0), game_ids=game_ids
    )


@pytest.mark.asyncio
async def test_a_shared_saturn_volume_merge_replaces_a_companions_old_save(
    binding, tmp_path: Path
):
    per_game = {"beetle_saturn_save_method": "mednafen"}
    rayman = saturn_game(binding)
    unit = collected(
        binding,
        rayman,
        "mednafen_saturn",
        "Rayman (USA) (R2).cue",
        {"Rayman (USA) (R2).bkr": saturn_volume([("RAYMAN_NTS", 0x11)])},
        tmp_path / "rayman",
        options=per_game,
    )
    dwarves = collected(
        binding,
        saturn_game(binding),
        "mednafen_saturn",
        "Three Dirty Dwarves (USA).cue",
        {"Three Dirty Dwarves (USA).bkr": saturn_volume([("THREE_DIRTY", 0x33)])},
        tmp_path / "dwarves",
        options=per_game,
    )
    sent = saturn_volume(
        [("RAYMAN_NTS", 0x22), ("THREE_DIRTY", 0x44), ("PANDRA_ZWEI", 0x55)]
    )

    restored = await merge_into_container(
        unit,
        rayman,
        target(
            "mednafen_saturn",
            "Rayman (USA) (R2).cue",
            beetle_saturn_save_method="mednafen",
            beetle_saturn_shared_int="enabled",
        ),
        "mednafen_saturn_libretro_shared.bkr",
        sent,
        [RestoreCompanion(game_ids=("T-30401H",), unit=dwarves)],
    )

    saves = saturn_saves(
        binding, restored.files["mednafen_saturn_libretro_shared.bkr"], tmp_path
    )
    assert saves == {
        "RAYMAN_NTS": bytes([0x11]) * SATURN_DATA,
        "THREE_DIRTY": bytes([0x33]) * SATURN_DATA,
        "PANDRA_ZWEI": bytes([0x55]) * SATURN_DATA,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("core", "save_id", "written"),
    [
        (
            "dolphin",
            "525a4445",
            "User/Wii/title/00010000/525a4445/data/rs_save.dat",
        ),
        (
            "dolphin_standalone",
            "00010001/574b5445",
            "Wii/title/00010001/574b5445/data/rs_save.dat",
        ),
    ],
)
async def test_a_wii_unit_is_restored_under_its_title_category(
    binding, core: str, save_id: str, written: str
):
    code = save_id.rpartition("/")[2]
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"{code}/data/rs_save.dat", b"wii save")
    game = SigilGame(
        result=binding.SigilResult.persisted("wii", code.upper(), save_id, 0),
        game_ids=(code.upper(),),
    )

    restored = await restore_per_game(buffer.getvalue(), game, target(core, "Game.rvz"))

    assert restored.files == {written: b"wii save"}


def test_layouts_name_the_region_option(binding):
    rows = restore_layouts("segacd")

    assert rows[0].id == "libretro"
    gpgx = next(row for row in rows if row.id == "genesis_plus_gx")
    assert gpgx.region_option == "genesis_plus_gx_region_detect"


def gb_clock_game(binding: ModuleType) -> SigilGame:
    return SigilGame(
        result=binding.SigilResult.persisted("gbc", "", "", binding.FEATURE_RTC),
        game_ids=(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("core", "sizes"),
    [
        ("mgba_standalone", {"game.sav": 32768 + 48}),
        ("gambatte", {"game.srm": 32768, "game.rtc": 8}),
    ],
)
async def test_a_gb_clock_is_written_in_the_cores_format(
    binding, tmp_path: Path, core: str, sizes: dict[str, int]
):
    game = gb_clock_game(binding)
    ram = b"s" * 32768
    unit = collected(
        binding,
        game,
        "gambatte",
        "game.gbc",
        {"game.srm": ram, "game.rtc": b"\x07" * 48},
        tmp_path,
    )

    restored = await restore_per_game(unit, game, target(core, "game.gbc"))

    assert {path: len(data) for path, data in restored.files.items()} == sizes
    primary = next(path for path in restored.files if not path.endswith(".rtc"))
    assert restored.files[primary][: len(ram)] == ram


@pytest.mark.asyncio
async def test_companions_on_a_cartridge_are_refused_naming_both_cases(
    binding, tmp_path: Path
):
    game = gb_clock_game(binding)
    unit = collected(
        binding,
        game,
        "gambatte",
        "game.gbc",
        {"game.srm": b"s" * 32768, "game.rtc": b"\x07" * 48},
        tmp_path,
    )

    with pytest.raises(SigilRefusal) as excinfo:
        await restore_per_game(
            unit,
            game,
            target("gambatte", "game.gbc"),
            [RestoreCompanion(game_ids=("OTHER",), unit=unit)],
        )

    assert excinfo.value.code is RefusalCode.INVALID_ARG
    assert "profiles" in str(excinfo.value)
    assert "cartridges" in str(excinfo.value)


def test_a_zip_unit_lists_each_volume(binding, tmp_path: Path):
    from adapters.services.sigil_restore import _unit_save_names

    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("a.brm", segacd_volume([("FIRST_SAVE1", 1, 1)]))
        zf.writestr("clock.rtc", b"\0" * 8)
        zf.writestr("b.brm", segacd_volume([("SECOND_SAV1", 1, 2)]))

    assert _unit_save_names(buffer.getvalue(), tmp_path) == [
        "FIRST_SAVE1",
        "SECOND_SAV1",
    ]


def test_a_zip_unit_skips_a_volume_over_the_card_cap(
    binding, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from adapters.services import sigil_restore

    reload_zipfile()
    small = segacd_volume([("FIRST_SAVE1", 1, 1)])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.brm", small)
        zf.writestr("bomb.brm", b"\0" * (len(small) * 4))
    monkeypatch.setattr(sigil_restore, "MEMORY_CARD_MAX_BYTES", len(small))

    assert sigil_restore._unit_save_names(buffer.getvalue(), tmp_path) == [
        "FIRST_SAVE1"
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["volume-0"]
