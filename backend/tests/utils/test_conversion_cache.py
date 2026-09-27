import asyncio
import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.services.rom_converto import RomConvertoOperationError, resolve_operation
from config import ROMM_BASE_PATH
from config.config_manager import ConvertoConfig
from models.rom import RomFile
from utils import conversion_cache
from utils.conversion_cache import (
    PARTIAL_PREFIX,
    converted_file_path,
    get_cached_converted,
    get_or_convert,
    get_redirect_path,
)


def _rom_file(**overrides: Any) -> RomFile:
    defaults: dict[str, Any] = {
        "rom_id": 1,
        "file_name": "game.iso",
        "file_path": "psp/roms",
        "file_size_bytes": 1000,
        "last_modified": 1700000000.0,
    }
    defaults.update(overrides)
    return RomFile(**defaults)


def _final_path(rom_file: RomFile) -> Path:
    resolved = resolve_operation("psp", "chd", rom_file.file_name)
    assert resolved is not None
    return converted_file_path(1, rom_file, *resolved)


def _partial_path(final: Path) -> Path:
    return final.with_name(f"{PARTIAL_PREFIX}{final.stem}.tmp{final.suffix}")


def _seed_cached(rom_file: RomFile, *, age_seconds: float = 0) -> Path:
    """Write a converted copy for `rom_file`, last served `age_seconds` ago."""
    final = _final_path(rom_file)
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"cached")
    served = time.time() - age_seconds
    os.utime(final, (served, served))
    return final


@contextmanager
def _held_lock(key_dir: Path) -> Iterator[None]:
    """Hold the key dir lock the way a converting worker does."""
    fd = os.open(key_dir, os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield
    finally:
        os.close(fd)


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
def convert_outputs(mocker) -> list[Path]:
    """Fake the adapter: write each requested output and record its path."""
    outputs: list[Path] = []

    async def convert(operation, src, out) -> None:
        outputs.append(out)
        out.write_bytes(b"converted")

    mocker.patch(
        "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
    )
    return outputs


class TestGetOrConvert:
    async def test_unresolvable_returns_none_without_touching_disk(
        self, cache_root, convert_outputs
    ):
        f = _rom_file(file_name="game.zip")

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert convert_outputs == []
        assert not any(cache_root.iterdir())

    async def test_cache_hit_returns_path_and_refreshes_mtime(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()
        final = _seed_cached(f, age_seconds=3600)

        assert await get_or_convert(1, f, "psp", "chd") == final
        assert final.stat().st_mtime > time.time() - 60
        assert convert_outputs == []

    async def test_full_cache_serves_original_without_converting(
        self, cache_root, convert_outputs, mocker
    ):
        mocker.patch.object(conversion_cache, "has_room_for", return_value=False)

        assert await get_or_convert(1, _rom_file(), "psp", "chd") is None
        assert convert_outputs == []

    async def test_locked_key_dir_serves_original(self, cache_root, convert_outputs):
        f = _rom_file()
        key_dir = _final_path(f).parent
        key_dir.mkdir(parents=True)

        with _held_lock(key_dir):
            assert await get_or_convert(1, f, "psp", "chd") is None
        assert convert_outputs == []

    async def test_concurrent_request_serves_original_while_one_converts(
        self, cache_root, mocker
    ):
        f = _rom_file()
        started = asyncio.Event()
        release = asyncio.Event()

        async def convert(op, src, out) -> None:
            started.set()
            await release.wait()
            out.write_bytes(b"converted")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        first = asyncio.create_task(get_or_convert(1, f, "psp", "chd"))
        await started.wait()
        assert await get_or_convert(1, f, "psp", "chd") is None
        release.set()
        assert await first == _final_path(f)

    async def test_writes_hidden_partial_then_renames_into_place(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()
        final = _final_path(f)

        assert await get_or_convert(1, f, "psp", "chd") == final
        assert convert_outputs == [_partial_path(final)]
        assert final.read_bytes() == b"converted"
        assert [p.name for p in final.parent.iterdir()] == [final.name]

    async def test_replaces_a_crashed_runs_partial_output(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()
        final = _final_path(f)
        final.parent.mkdir(parents=True)
        _partial_path(final).write_bytes(b"leftover")

        assert await get_or_convert(1, f, "psp", "chd") == final
        assert final.read_bytes() == b"converted"

    @pytest.mark.parametrize("writes_partial", [False, True])
    async def test_conversion_failure_leaves_the_key_dir_empty(
        self, cache_root, mocker, writes_partial
    ):
        f = _rom_file()

        async def convert(op, src, out) -> None:
            if writes_partial:
                out.write_bytes(b"partial")
            raise RomConvertoOperationError("boom")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert list(_final_path(f).parent.iterdir()) == []


class TestGetCachedConverted:
    @pytest.mark.parametrize("file_name", ["game.zip", "game.iso"])
    def test_returns_none_when_unresolvable_or_not_cached(self, cache_root, file_name):
        f = _rom_file(file_name=file_name)

        assert get_cached_converted(1, f, "psp", "chd") is None

    @pytest.mark.parametrize("touch", [False, True])
    def test_returns_the_copy_refreshing_mtime_only_when_asked(self, cache_root, touch):
        f = _rom_file()
        final = _seed_cached(f, age_seconds=3600)

        assert get_cached_converted(1, f, "psp", "chd", touch=touch) == final
        assert (final.stat().st_mtime > time.time() - 60) is touch


class TestHasRoomFor:
    def test_unbounded_when_cap_is_zero(self, cache_root, converto):
        converto.cache_max_size_gb = 0

        assert conversion_cache.has_room_for(10 * conversion_cache.BYTES_PER_GB)

    def test_counts_partial_output_against_the_cap(self, cache_root, converto, mocker):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        key_dir = cache_root / "1-a"
        key_dir.mkdir()
        (key_dir / "game.chd").write_bytes(b"x" * 40)
        (key_dir / f"{PARTIAL_PREFIX}other.tmp.chd").write_bytes(b"x" * 20)

        assert conversion_cache.has_room_for(40)
        assert not conversion_cache.has_room_for(41)


class TestGetRedirectPath:
    def test_relative_to_romm_base_path(self):
        converted_path = Path(ROMM_BASE_PATH) / "cache/converts/1-abc/Game.chd"
        assert get_redirect_path(converted_path) == Path(
            "/cache/converts/1-abc/Game.chd"
        )


class TestCleanupStaleConversions:
    def test_missing_root_is_noop(self, tmp_path, mocker):
        mocker.patch.object(
            conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(tmp_path / "nope")
        )
        assert conversion_cache.cleanup_stale_conversions() == 0

    def test_deletes_expired_and_keeps_fresh(self, cache_root):
        expired = _seed_cached(_rom_file(file_name="old.iso"), age_seconds=25 * 3600)
        fresh = _seed_cached(_rom_file(file_name="new.iso"))

        assert conversion_cache.cleanup_stale_conversions() == 1
        assert not expired.parent.exists()
        assert fresh.exists()

    @pytest.mark.parametrize("leftover", [None, f"{PARTIAL_PREFIX}game.tmp.chd"])
    def test_deletes_dirs_without_a_served_copy(self, cache_root, leftover):
        key_dir = cache_root / "1-e"
        key_dir.mkdir()
        if leftover:
            (key_dir / leftover).write_bytes(b"partial")

        assert conversion_cache.cleanup_stale_conversions() == 1
        assert not key_dir.exists()

    def test_skips_a_dir_whose_conversion_is_running(self, cache_root):
        key_dir = cache_root / "1-busy"
        key_dir.mkdir()
        (key_dir / f"{PARTIAL_PREFIX}game.tmp.chd").write_bytes(b"partial")

        with _held_lock(key_dir):
            assert conversion_cache.cleanup_stale_conversions() == 0
        assert key_dir.exists()

    def test_evicts_least_recently_served_over_the_cap(
        self, cache_root, converto, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        dirs = {}
        for name, age in (("old", 300), ("mid", 200), ("new", 100)):
            final = _seed_cached(_rom_file(file_name=f"{name}.iso"))
            final.write_bytes(b"x" * 40)
            os.utime(final, (time.time() - age, time.time() - age))
            dirs[name] = final.parent

        assert conversion_cache.cleanup_stale_conversions() == 1
        assert not dirs["old"].exists()
        assert dirs["mid"].exists()
        assert dirs["new"].exists()
