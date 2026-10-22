import json
from unittest.mock import patch

import pytest

from models.firmware import KNOWN_BIOS_KEY, Firmware

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


@pytest.mark.parametrize("platform_slug", ["arcade", "mame", "naomi", "atomiswave"])
def test_an_arcade_platform_verifies_against_the_arcade_bios_list(
    platform_slug: str,
):
    with patch("models.firmware.sync_cache.hget", side_effect=_known_bios):
        assert _verify(platform_slug)


def test_a_non_arcade_platform_does_not_borrow_the_arcade_bios_list():
    with patch("models.firmware.sync_cache.hget", side_effect=_known_bios):
        assert not _verify("snes")
