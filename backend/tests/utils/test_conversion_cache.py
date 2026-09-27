import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters.services.rom_converto import (
    Operation,
    RomConvertoOperationError,
    resolve_operation,
)
from config import ROMM_BASE_PATH
from config.config_manager import ConvertoConfig
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


def _resolved(rom_file: RomFile) -> tuple[Operation, str]:
    resolved = resolve_operation("psp", "chd", rom_file.file_name)
    assert resolved is not None
    return resolved


@pytest.fixture(autouse=True)
def converto(mocker) -> ConvertoConfig:
    """The converto.* settings every cache function reads, editable per test."""
    config = ConvertoConfig()
    mocker.patch(
        "utils.conversion_cache.cm.get_config",
        return_value=SimpleNamespace(CONVERTO=config),
    )
    return config


@pytest.fixture
def cache_root(tmp_path, mocker):
    mocker.patch.object(conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_convert(mocker):
    """Materialize the `.tmp` output file, like the real adapter does."""

    async def convert(operation, src, out) -> None:
        out.write_bytes(b"converted")

    return mocker.patch(
        "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
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
        operation, input_ext = _resolved(f)
        final = converted_file_path(1, f, operation, input_ext)
        final.parent.mkdir(parents=True)
        final.write_bytes(b"cached")
        old = time.time() - 3600
        os.utime(final, (old, old))

        result = await get_or_convert(1, f, "psp", "chd")

        assert result == final
        assert os.stat(final).st_mtime > old
        fake_convert.assert_not_called()

    async def test_full_cache_serves_original_without_converting(
        self, cache_root, fake_convert, mocker
    ):
        mocker.patch.object(conversion_cache, "has_room_for", return_value=False)

        assert await get_or_convert(1, _rom_file(), "psp", "chd") is None
        fake_convert.assert_not_called()

    async def test_fresh_sentinel_returns_none(self, cache_root, fake_convert):
        f = _rom_file()
        operation, input_ext = _resolved(f)
        key_dir = converted_file_path(1, f, operation, input_ext).parent
        key_dir.mkdir(parents=True)
        (key_dir / SENTINEL_NAME).touch()

        assert await get_or_convert(1, f, "psp", "chd") is None
        fake_convert.assert_not_called()

    async def test_stale_sentinel_is_reclaimed(self, cache_root, fake_convert):
        f = _rom_file()
        operation, input_ext = _resolved(f)
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
        operation, input_ext = _resolved(f)
        final = converted_file_path(1, f, operation, input_ext)
        seen_out: list[Path] = []

        async def convert(op, src, out) -> None:
            seen_out.append(out)
            out.write_bytes(b"converted")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
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
        operation, input_ext = _resolved(f)
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
        operation, input_ext = _resolved(f)
        key_dir = converted_file_path(1, f, operation, input_ext).parent

        async def convert(op, src, out) -> None:
            raise RomConvertoOperationError("boom")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert list(key_dir.iterdir()) == []

    async def test_conversion_failure_leaves_no_partial_tmp(self, cache_root, mocker):
        f = _rom_file()
        operation, input_ext = _resolved(f)
        key_dir = converted_file_path(1, f, operation, input_ext).parent

        async def convert(op, src, out) -> None:
            out.write_bytes(b"partial")
            raise RomConvertoOperationError("boom")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
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
        operation, input_ext = _resolved(f)
        final = converted_file_path(1, f, operation, input_ext)
        final.parent.mkdir(parents=True)
        final.write_bytes(b"cached")

        assert get_cached_converted(1, f, "psp", "chd") == final

    @pytest.mark.parametrize("touch", [False, True])
    def test_touch_refreshes_mtime_only_when_asked(self, cache_root, touch):
        f = _rom_file()
        operation, input_ext = _resolved(f)
        final = converted_file_path(1, f, operation, input_ext)
        final.parent.mkdir(parents=True)
        final.write_bytes(b"cached")
        old = time.time() - 3600
        os.utime(final, (old, old))

        get_cached_converted(1, f, "psp", "chd", touch=touch)

        assert (os.stat(final).st_mtime > old) is touch


class TestHasRoomFor:
    def test_unbounded_when_cap_is_zero(self, cache_root, converto):
        converto.cache_max_size_gb = 0

        assert conversion_cache.has_room_for(10 * conversion_cache.BYTES_PER_GB)

    def test_counts_cached_bytes_against_the_cap(self, cache_root, converto, mocker):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        key_dir = cache_root / "1-a"
        key_dir.mkdir()
        (key_dir / "game.chd").write_bytes(b"x" * 60)
        (key_dir / SENTINEL_NAME).touch()

        assert conversion_cache.has_room_for(40)
        assert not conversion_cache.has_room_for(41)


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

    def test_evicts_least_recently_served_over_the_cap(
        self, cleanup_cache_root, converto, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        now = time.time()
        dirs = {}
        for name, age in (("1-old", 300), ("1-mid", 200), ("1-new", 100)):
            key_dir = cleanup_cache_root / name
            key_dir.mkdir()
            (key_dir / "game.chd").write_bytes(b"x" * 40)
            os.utime(key_dir / "game.chd", (now - age, now - age))
            dirs[name] = key_dir

        deleted = conversion_cache.cleanup_stale_conversions()

        assert deleted == 1
        assert not dirs["1-old"].exists()
        assert dirs["1-mid"].exists()
        assert dirs["1-new"].exists()

    def test_never_evicts_an_in_flight_conversion(
        self, cleanup_cache_root, converto, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 10)
        key_dir = cleanup_cache_root / "1-busy"
        key_dir.mkdir()
        (key_dir / "game.tmp1.chd").write_bytes(b"x" * 40)
        (key_dir / SENTINEL_NAME).touch()

        assert conversion_cache.cleanup_stale_conversions() == 0
        assert key_dir.exists()
