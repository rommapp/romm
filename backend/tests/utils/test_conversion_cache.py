import os
import time
from pathlib import Path

import pytest

from models.rom import RomFile
from utils import conversion_cache
from utils.conversion_cache import (
    SENTINEL_NAME,
    TARGET_EXTENSIONS,
    converted_file_path,
    get_or_convert,
)


def _rom_file(**overrides) -> RomFile:
    defaults = {
        "rom_id": 1,
        "file_name": "game.3ds",
        "file_path": "3ds/roms",
        "file_size_bytes": 1000,
        "last_modified": 1700000000.0,
    }
    defaults.update(overrides)
    return RomFile(**defaults)


@pytest.fixture
def cache_root(tmp_path, mocker):
    mocker.patch.object(conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_convert(mocker):
    """Materialize a dummy output in dest_dir, like the real adapter does."""

    async def convert(target, src, dest_dir):
        out = Path(dest_dir) / f"{Path(src).stem}.converted"
        out.write_bytes(b"converted")
        return out

    return mocker.patch.object(
        conversion_cache.rom_converto_service, "convert", side_effect=convert
    )


class TestConvertedFilePath:
    def test_deterministic(self):
        f = _rom_file()
        assert converted_file_path(1, f, "cia-decrypted") == converted_file_path(
            1, f, "cia-decrypted"
        )

    def test_changes_with_last_modified(self):
        f1 = _rom_file()
        f2 = _rom_file(last_modified=1800000000.0)
        assert converted_file_path(1, f1, "cia-decrypted") != converted_file_path(
            1, f2, "cia-decrypted"
        )

    def test_output_extension(self):
        path = converted_file_path(1, _rom_file(), "cia-decrypted")
        assert path.name == "game.cia"
        assert converted_file_path(1, _rom_file(), "iso-decrypted").name == "game.iso"
        assert converted_file_path(1, _rom_file(), "nsp").name == "game.nsp"

    def test_key_dir_namespaces_rom_id(self):
        assert converted_file_path(
            1, _rom_file(), "cia-decrypted"
        ).parent != converted_file_path(
            2, _rom_file(), "cia-decrypted"
        ).parent


class TestGetOrConvert:
    async def test_cache_hit_skips_conversion(self, cache_root, fake_convert):
        f = _rom_file()
        final = converted_file_path(1, f, "cia-decrypted")
        final.parent.mkdir(parents=True)
        final.write_bytes(b"cached")

        assert await get_or_convert(1, f, "cia-decrypted") == final
        fake_convert.assert_not_called()

    async def test_converts_and_returns_final_path(self, cache_root, fake_convert):
        f = _rom_file()
        final = converted_file_path(1, f, "cia-decrypted")

        result = await get_or_convert(1, f, "cia-decrypted")

        assert result == final
        assert final.read_bytes() == b"converted"
        assert not (final.parent / SENTINEL_NAME).exists()
        fake_convert.assert_called_once()

    async def test_fresh_partial_returns_none(self, cache_root, fake_convert):
        f = _rom_file()
        key_dir = converted_file_path(1, f, "cia-decrypted").parent
        key_dir.mkdir(parents=True)
        (key_dir / SENTINEL_NAME).touch()

        assert await get_or_convert(1, f, "cia-decrypted") is None
        fake_convert.assert_not_called()

    async def test_stale_partial_is_reclaimed(self, cache_root, fake_convert):
        f = _rom_file()
        final = converted_file_path(1, f, "cia-decrypted")
        key_dir = final.parent
        key_dir.mkdir(parents=True)
        sentinel = key_dir / SENTINEL_NAME
        sentinel.touch()
        stale = time.time() - 7 * 3600
        os.utime(sentinel, (stale, stale))

        result = await get_or_convert(1, f, "cia-decrypted")

        assert result == final
        assert final.read_bytes() == b"converted"
        assert not sentinel.exists()

    async def test_conversion_failure_returns_none_and_cleans(
        self, cache_root, mocker
    ):
        mocker.patch.object(
            conversion_cache.rom_converto_service,
            "convert",
            side_effect=RuntimeError("boom"),
        )
        f = _rom_file()
        key_dir = converted_file_path(1, f, "cia-decrypted").parent

        assert await get_or_convert(1, f, "cia-decrypted") is None
        assert not any(key_dir.iterdir()) if key_dir.exists() else True

    async def test_existing_final_beats_windows_replace_error(
        self, cache_root, fake_convert, mocker
    ):
        # Windows: os.replace onto a final file a concurrent request is still
        # streaming raises PermissionError; an existing final counts as success.
        f = _rom_file()
        final = converted_file_path(1, f, "cia-decrypted")

        def busy_replace(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b"streamed")
            raise PermissionError(dst)

        mocker.patch.object(conversion_cache.os, "replace", side_effect=busy_replace)

        assert await get_or_convert(1, f, "cia-decrypted") == final
        assert final.read_bytes() == b"streamed"


class TestTargetExtensions:
    def test_covers_all_targets(self):
        assert set(TARGET_EXTENSIONS) == {
            "cia-decrypted",
            "iso",
            "chd",
            "rvz",
            "nsp",
            "iso-decrypted",
        }
