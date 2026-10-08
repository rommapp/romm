import hashlib
import io
import zipfile
from unittest.mock import patch

import pytest
from tests._zipfile_shim import reload_zipfile

from adapters.services import sigil as sigil_service
from adapters.services.sigil import SigilService
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


def _md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def _without_binding():
    return patch.object(sigil_service, "sigil", None)


@pytest.mark.parametrize("members", UNITS.values(), ids=UNITS.keys())
async def test_sigil_and_the_fallback_agree(members: dict[str, bytes]):
    pytest.importorskip("sigil")
    content = _zip(members)
    answers: list[str | None] = []
    real = hashing._sigil.unit_identity_hash

    def record(*args, **kwargs):
        answers.append(real(*args, **kwargs))
        return answers[-1]

    with patch.object(hashing._sigil, "unit_identity_hash", side_effect=record):
        by_sigil = await hashing.identity_hash(content)
    with _without_binding():
        by_fallback = await hashing.identity_hash(content)

    assert answers and answers[0] is not None
    assert by_sigil == by_fallback


async def test_sigil_hashes_a_raw_file_as_itself():
    pytest.importorskip("sigil")

    assert await hashing.identity_hash(b"only") == _md5(b"only")


async def test_a_unit_past_the_unpack_limit_never_reaches_disk():
    content = _zip(UNITS["neutral clock"])
    with (
        patch.object(hashing, "SIGIL_UNPACK_MAX_BYTES", 2),
        patch.object(SigilService, "is_enabled", return_value=True),
        patch.object(hashing._sigil, "unit_identity_hash") as unit_identity_hash,
        patch.object(zipfile.ZipFile, "extract") as extract,
    ):
        identity = await hashing.identity_hash(content)

    unit_identity_hash.assert_not_called()
    extract.assert_not_called()
    assert identity == _md5(b"sram")


async def test_without_the_binding_the_clock_is_left_out():
    with _without_binding():
        identity = await hashing.identity_hash(_zip(UNITS["neutral clock"]))

    assert identity == _md5(b"sram")


async def test_an_unreadable_archive_hashes_as_one_file():
    content = _zip(UNITS["chips"])
    broken = content[:10] + b"\x00" * 40 + content[50:]

    assert await hashing.identity_hash(broken) == _md5(broken)


async def test_a_file_on_disk_hashes_like_its_bytes(tmp_path):
    content = _zip(UNITS["native clock"])
    path = tmp_path / "save.zip"
    path.write_bytes(content)

    assert await hashing.identity_hash_of_file(path) == await hashing.identity_hash(
        content
    )
