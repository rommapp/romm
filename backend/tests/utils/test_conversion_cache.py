import os
import time
from pathlib import Path

import pytest

from adapters.services.rom_converto import RomConvertoOperationError, resolve_operation
from config import ROMM_BASE_PATH
from models.rom import RomFile
from utils import conversion_cache
from utils.conversion_cache import (
    SENTINEL_NAME,
    converted_file_path,
    get_cached_converted,
    get_or_convert,
    get_redirect_path,
)


def _rom_file(**overrides) -> RomFile:
    defaults = {
        "rom_id": 1,
        "file_name": "game.iso",
        "file_path": "psp/roms",
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
    """Materialize the `.tmp` output file, like the real adapter does."""

    async def convert(operation, src, out) -> None:
        out.write_bytes(b"converted")

    return mocker.patch.object(
        conversion_cache.rom_converto_service, "convert", side_effect=convert
    )


class TestGetOrConvert:
    async def test_unresolvable_returns_none_without_touching_disk(
        self, cache_root, fake_convert
    ):
        f = _rom_file(file_name="game.zip")

        assert await get_or_convert(1, f, "psp", "chd") is None
        fake_convert.assert_not_called()
        assert not any(cache_root.iterdir())

    async def test_cache_hit_returns_path_and_refreshes_mtime(
        self, cache_root, fake_convert
    ):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        final = converted_file_path(1, f, operation, input_ext)
        final.parent.mkdir(parents=True)
        final.write_bytes(b"cached")
        old = time.time() - 3600
        os.utime(final, (old, old))

        result = await get_or_convert(1, f, "psp", "chd")

        assert result == final
        assert os.stat(final).st_mtime > old
        fake_convert.assert_not_called()

    async def test_fresh_sentinel_returns_none(self, cache_root, fake_convert):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        key_dir = converted_file_path(1, f, operation, input_ext).parent
        key_dir.mkdir(parents=True)
        (key_dir / SENTINEL_NAME).touch()

        assert await get_or_convert(1, f, "psp", "chd") is None
        fake_convert.assert_not_called()

    async def test_stale_sentinel_is_reclaimed(self, cache_root, fake_convert):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        final = converted_file_path(1, f, operation, input_ext)
        key_dir = final.parent
        key_dir.mkdir(parents=True)
        sentinel = key_dir / SENTINEL_NAME
        sentinel.touch()
        stale = time.time() - 7 * 3600
        os.utime(sentinel, (stale, stale))

        result = await get_or_convert(1, f, "psp", "chd")

        assert result == final
        assert final.read_bytes() == b"converted"
        assert not sentinel.exists()

    async def test_success_writes_via_tmp_then_final(self, cache_root, mocker):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        final = converted_file_path(1, f, operation, input_ext)
        seen_out: list[Path] = []

        async def convert(op, src, out) -> None:
            seen_out.append(out)
            out.write_bytes(b"converted")

        mocker.patch.object(
            conversion_cache.rom_converto_service, "convert", side_effect=convert
        )

        result = await get_or_convert(1, f, "psp", "chd")

        assert result == final
        assert seen_out == [
            final.with_name(f"{final.stem}.tmp{os.getpid()}{final.suffix}")
        ]
        assert final.exists()
        assert not (final.parent / SENTINEL_NAME).exists()

    async def test_stale_tmp_from_this_pid_is_removed_before_convert(
        self, cache_root, fake_convert
    ):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        final = converted_file_path(1, f, operation, input_ext)
        final.parent.mkdir(parents=True)
        tmp = final.with_name(f"{final.stem}.tmp{os.getpid()}{final.suffix}")
        tmp.write_bytes(b"leftover")

        result = await get_or_convert(1, f, "psp", "chd")

        assert result == final
        assert final.read_bytes() == b"converted"

    async def test_conversion_failure_returns_none_and_empties_key_dir(
        self, cache_root, mocker
    ):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        key_dir = converted_file_path(1, f, operation, input_ext).parent

        async def convert(op, src, out) -> None:
            raise RomConvertoOperationError("boom", returncode=1, stderr="boom")

        mocker.patch.object(
            conversion_cache.rom_converto_service, "convert", side_effect=convert
        )

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert list(key_dir.iterdir()) == []

    async def test_conversion_failure_leaves_no_partial_tmp(self, cache_root, mocker):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        key_dir = converted_file_path(1, f, operation, input_ext).parent

        async def convert(op, src, out) -> None:
            out.write_bytes(b"partial")
            raise RomConvertoOperationError("boom", returncode=1, stderr="boom")

        mocker.patch.object(
            conversion_cache.rom_converto_service, "convert", side_effect=convert
        )

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert list(key_dir.iterdir()) == []


class TestGetCachedConverted:
    def test_returns_none_when_unresolvable(self, cache_root):
        f = _rom_file(file_name="game.zip")

        assert get_cached_converted(1, f, "psp", "chd") is None

    def test_returns_none_when_not_cached(self, cache_root):
        f = _rom_file()

        assert get_cached_converted(1, f, "psp", "chd") is None

    def test_returns_final_path_when_cached(self, cache_root):
        f = _rom_file()
        operation, input_ext = resolve_operation("psp", "chd", f.file_name)
        final = converted_file_path(1, f, operation, input_ext)
        final.parent.mkdir(parents=True)
        final.write_bytes(b"cached")

        assert get_cached_converted(1, f, "psp", "chd") == final


class TestGetRedirectPath:
    def test_relative_to_romm_base_path(self):
        converted_path = Path(ROMM_BASE_PATH) / "cache/converts/1-abc/Game.chd"
        assert get_redirect_path(converted_path) == Path(
            "/cache/converts/1-abc/Game.chd"
        )


class TestCleanupStaleConversions:
    @pytest.fixture
    def cleanup_cache_root(self, tmp_path, mocker):
        mocker.patch.object(conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(tmp_path))
        mocker.patch.object(
            conversion_cache.cm,
            "get_config",
            return_value=mocker.Mock(**{"CONVERTO.cache_ttl_hours": 24}),
        )
        return tmp_path

    def test_missing_root_is_noop(self, tmp_path, mocker):
        mocker.patch.object(
            conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(tmp_path / "nope")
        )
        assert conversion_cache.cleanup_stale_conversions() == 0

    def test_deletes_expired_and_keeps_fresh(self, cleanup_cache_root):
        expired = cleanup_cache_root / "1-a"
        expired.mkdir()
        (expired / "game.chd").write_bytes(b"x")
        old = time.time() - 25 * 3600
        os.utime(expired / "game.chd", (old, old))

        fresh = cleanup_cache_root / "1-b"
        fresh.mkdir()
        (fresh / "game.chd").write_bytes(b"x")

        deleted = conversion_cache.cleanup_stale_conversions()

        assert deleted == 1
        assert not expired.exists()
        assert fresh.exists()

    def test_deletes_stale_sentinel_only_dirs(self, cleanup_cache_root):
        stale = cleanup_cache_root / "1-c"
        stale.mkdir()
        sentinel = stale / SENTINEL_NAME
        sentinel.touch()
        old = time.time() - 7 * 3600
        os.utime(sentinel, (old, old))

        fresh = cleanup_cache_root / "1-d"
        fresh.mkdir()
        (fresh / SENTINEL_NAME).touch()

        deleted = conversion_cache.cleanup_stale_conversions()

        assert deleted == 1
        assert not stale.exists()
        assert fresh.exists()

    def test_deletes_empty_leaked_dirs(self, cleanup_cache_root):
        leaked = cleanup_cache_root / "1-e"
        leaked.mkdir()

        deleted = conversion_cache.cleanup_stale_conversions()

        assert deleted == 1
        assert not leaked.exists()
