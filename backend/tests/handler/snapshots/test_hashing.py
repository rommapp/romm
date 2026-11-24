import io
import zipfile
from pathlib import Path

import pytest
from tests._embedded_archives import EMBEDDINGS, embedded_archive
from tests._zipfile_shim import reload_zipfile
from tests.handler.snapshots.pushes import md5, red_ram

from handler.filesystem import assets_handler
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


async def _identity(content: bytes, platform_slug: str | None = None) -> str:
    return await hashing.identity_hash(content, platform_slug=platform_slug, features=0)


@pytest.mark.parametrize("members", UNITS.values(), ids=UNITS.keys())
async def test_the_hash_is_the_one_sigil_gives(members: dict[str, bytes], tmp_path):
    sigil = pytest.importorskip("sigil")

    assert await _identity(_zip(members)) == _by_sigil(sigil, members, tmp_path)


async def test_sigil_answers_for_a_platform_it_has_a_rule_for():
    sigil = pytest.importorskip("sigil")
    feature = sigil.FEATURE_GB_SCRATCH_GEN1
    scratch_written = red_ram({0x0100: 0x5A})

    saved = await hashing.identity_hash(red_ram(), platform_slug="gb", features=feature)

    assert saved == sigil.unit_identity("gb", feature, scratch_written)
    assert saved != md5(red_ram())


async def test_without_sigil_a_platform_with_a_rule_hashes_its_content(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(hashing, "sigil_binding", lambda: None)

    assert await _identity(red_ram(), "gb") == md5(red_ram())


async def test_a_binding_without_unit_identities_hashes_its_content(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(hashing, "sigil_binding", lambda: object())

    assert await _identity(red_ram(), "gb") == md5(red_ram())


async def test_a_unit_sigil_has_no_rule_for_hashes_its_content():
    pytest.importorskip("sigil")

    assert await _identity(b"only", "psx") == md5(b"only")


class _RefusingBinding:
    class SigilError(Exception):
        pass

    @classmethod
    def unit_identity(cls, platform: str, features: int, unit: bytes) -> str:
        raise cls.SigilError(platform)


async def test_a_unit_sigil_refuses_hashes_its_content(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(hashing, "sigil_binding", lambda: _RefusingBinding)

    assert await _identity(red_ram(), "gb") == md5(red_ram())


async def test_a_raw_file_hashes_as_itself():
    assert await _identity(b"only") == md5(b"only")


async def test_the_clock_is_left_out():
    identity = await _identity(_zip(UNITS["neutral clock"]))

    assert identity == md5(b"sram")


async def test_an_unreadable_archive_hashes_as_one_file():
    content = _zip(UNITS["chips"])
    broken = content[:10] + b"\x00" * 40 + content[50:]

    assert await _identity(broken) == md5(broken)


@pytest.mark.parametrize("embedding", EMBEDDINGS)
async def test_bytes_that_only_end_like_a_zip_hash_as_one_file(embedding: str):
    content = embedded_archive(embedding)

    assert await _identity(content) == md5(content)


async def test_an_archive_past_the_limits_hashes_as_one_file(
    monkeypatch: pytest.MonkeyPatch,
):
    content = _zip(UNITS["chips"])
    monkeypatch.setattr(assets_handler, "MAX_DECOMPRESSED_ARCHIVE_BYTES", 1)

    assert await _identity(content) == md5(content)


async def test_a_file_on_disk_hashes_like_its_bytes(tmp_path):
    content = _zip(UNITS["native clock"])
    path = tmp_path / "save.zip"
    path.write_bytes(content)

    assert await hashing.identity_hash_of_file(
        path, platform_slug="gb", features=0
    ) == await _identity(content, "gb")
