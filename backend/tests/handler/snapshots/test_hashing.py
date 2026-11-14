import io
import zipfile
from pathlib import Path

import pytest
from tests._zipfile_shim import reload_zipfile
from tests.handler.snapshots.pushes import md5

from handler.filesystem.assets_handler import is_clock_member
from handler.snapshots import hashing

UNITS: dict[str, dict[str, bytes]] = {
    "neutral clock": {"save.sram": b"sram", "clock.rtc": b"tick"},
    "native clock": {"Pokemon.srm": b"sram", "Pokemon.rtc": b"tick"},
    "chips": {"eeprom": b"e", "pak1": b"p", "sram": b"s"},
    "folder": {"SAVE01/data.bin": b"d", "SAVE01/icon.png": b"i"},
    "clock and two": {"a.srm": b"a", "b.srm": b"b", "c.rtc": b"t"},
}


def _zip(members: dict[str, bytes]) -> bytes:
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def _by_sigil(sigil, members: dict[str, bytes], root: Path) -> str:
    for name, data in members.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    unit = sigil.SigilSaveUnit(
        key=root.name,
        shape="multi",
        members=tuple(
            sigil.SigilSaveMember(
                path=name,
                entry=name,
                role="rtc" if is_clock_member(name) else "primary",
                present=True,
            )
            for name in sorted(members)
        ),
        expected=(),
        unkeyed=(),
        artifact=root.name,
        content_hash="",
        identity_hash="",
    )
    identity: str = sigil.hash_saves(unit, root).identity_hash
    return identity


@pytest.mark.parametrize("members", UNITS.values(), ids=UNITS.keys())
async def test_the_hash_is_the_one_sigil_gives(members: dict[str, bytes], tmp_path):
    sigil = pytest.importorskip("sigil")

    assert await hashing.identity_hash(_zip(members)) == _by_sigil(
        sigil, members, tmp_path
    )


async def test_a_raw_file_hashes_as_itself():
    assert await hashing.identity_hash(b"only") == md5(b"only")


async def test_the_clock_is_left_out():
    identity = await hashing.identity_hash(_zip(UNITS["neutral clock"]))

    assert identity == md5(b"sram")


async def test_an_unreadable_archive_hashes_as_one_file():
    content = _zip(UNITS["chips"])
    broken = content[:10] + b"\x00" * 40 + content[50:]

    assert await hashing.identity_hash(broken) == md5(broken)


async def test_a_file_on_disk_hashes_like_its_bytes(tmp_path):
    content = _zip(UNITS["native clock"])
    path = tmp_path / "save.zip"
    path.write_bytes(content)

    assert await hashing.identity_hash_of_file(path) == await hashing.identity_hash(
        content
    )
