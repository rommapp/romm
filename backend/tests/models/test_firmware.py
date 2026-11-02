import json
from unittest.mock import patch

import pytest

from models.firmware import KNOWN_BIOS_FILE, KNOWN_BIOS_KEY, Firmware

NAOMI_BIOS = {"size": 100, "md5": "abc", "sha1": "def", "crc": "123"}


def _verify(platform_slug: str) -> bool:
    return Firmware.verify_file_hashes(
        platform_slug=platform_slug,
        file_name="naomi.zip",
        file_size_bytes=100,
        md5_hash="abc",
        sha1_hash="",
        crc_hash="",
    )


def _known_bios(key: str, field: str) -> str | None:
    assert key == KNOWN_BIOS_KEY
    return json.dumps(NAOMI_BIOS) if field == "arcade:naomi.zip" else None


@pytest.mark.parametrize(
    "platform_slug", ["arcade", "mame", "naomi", "atomiswave", "neogeoaes", "neogeomvs"]
)
def test_an_arcade_platform_verifies_against_the_arcade_bios_list(
    platform_slug: str,
):
    with patch("models.firmware.sync_cache.hget", side_effect=_known_bios):
        assert _verify(platform_slug)


def test_a_non_arcade_platform_does_not_borrow_the_arcade_bios_list():
    with patch("models.firmware.sync_cache.hget", side_effect=_known_bios):
        assert not _verify("snes")


def _verify_gb_bios(
    platform_slug: str,
    file_name: str,
    *,
    size_offset: int = 0,
    with_md5: bool = True,
    with_sha1: bool = True,
) -> bool:
    with KNOWN_BIOS_FILE.open() as f:
        dump = json.load(f)["gb:gb_bios.bin"]
    with patch("models.firmware.sync_cache.hget", return_value=None):
        return Firmware.verify_file_hashes(
            platform_slug=platform_slug,
            file_name=file_name,
            file_size_bytes=int(dump["size"]) + size_offset,
            md5_hash=dump["md5"] if with_md5 else "",
            sha1_hash=dump["sha1"] if with_sha1 else "",
            crc_hash=dump["crc"],
        )


@pytest.mark.parametrize(
    ("platform_slug", "file_name"),
    [
        ("gb", "GB_BIOS.BIN"),
        ("gb", "gb_bios (copy).bin"),
        ("gbc", "gb_bios.bin"),
    ],
)
def test_a_known_dump_verifies_by_hash_whatever_its_name_or_platform(
    platform_slug: str, file_name: str
):
    assert _verify_gb_bios(platform_slug, file_name)


def test_a_known_dump_verifies_by_sha1_alone():
    assert _verify_gb_bios("gbc", "boot.bin", with_md5=False)


def test_a_known_hash_with_the_wrong_size_does_not_verify():
    assert not _verify_gb_bios("gbc", "boot.bin", size_offset=1)


def test_a_crc_alone_does_not_verify_without_a_name_match():
    assert not _verify_gb_bios("gbc", "boot.bin", with_md5=False, with_sha1=False)
