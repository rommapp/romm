import asyncio
import fcntl
import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from adapters.services.rom_converto import (
    RomConvertoBinaryNotFoundError,
    RomConvertoOperationError,
    RomConvertoTimeoutError,
    resolve_operation,
)
from config import ROMM_BASE_PATH
from config.config_manager import ConvertoConfig
from models.rom import Rom, RomFile
from utils import conversion_cache
from utils.conversion_cache import (
    FAILED_FILE,
    PARTIAL_DIR,
    SERVE_GRACE_SECONDS,
    FormatOutcome,
    FormatResolution,
    converted_file_path,
    get_cached_converted,
    get_or_convert,
    get_redirect_path,
    parse_formats,
    resolve_format_download,
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
    return final.parent / PARTIAL_DIR / final.name


def _seed_cached(rom_file: RomFile, *, age_seconds: float = 0) -> Path:
    """Write a converted copy for `rom_file`, last served `age_seconds` ago."""
    final = _final_path(rom_file)
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"cached")
    served = time.time() - age_seconds
    os.utime(final, (served, served))
    return final


@contextmanager
def _held_lock(key_dir: Path, *, shared: bool = False) -> Iterator[None]:
    """Hold a key dir lock while a request or worker uses it."""
    fd = os.open(key_dir, os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
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

    async def test_oversized_conversion_returns_none_without_converting(
        self, cache_root, converto, convert_outputs, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)

        assert (
            await get_or_convert(1, _rom_file(file_size_bytes=101), "psp", "chd")
            is None
        )
        assert convert_outputs == []

    async def test_admission_reserves_room_for_a_decompression(
        self, cache_root, converto, convert_outputs, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        f = _rom_file(file_name="game.chd", file_size_bytes=30)

        assert await get_or_convert(1, f, "psp", "iso") is None
        assert convert_outputs == []

    async def test_admission_evicts_an_older_copy_to_make_room(
        self, cache_root, converto, convert_outputs, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        older = _seed_cached(_rom_file(file_name="older.iso"))
        older.write_bytes(b"x" * 40)
        served = time.time() - 300
        os.utime(older, (served, served))
        f = _rom_file(file_size_bytes=70)

        assert await get_or_convert(1, f, "psp", "chd") == _final_path(f)
        assert not older.parent.exists()
        assert _final_path(f).read_bytes() == b"converted"

    async def test_admission_does_not_evict_a_recently_served_copy(
        self, cache_root, converto, convert_outputs, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        recent = _seed_cached(_rom_file(file_name="recent.iso"))
        recent.write_bytes(b"x" * 80)
        f = _rom_file(file_size_bytes=50)

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert recent.read_bytes() == b"x" * 80
        assert convert_outputs == []

    @pytest.mark.parametrize(
        ("size_bytes", "blocked"),
        [
            pytest.param(101, "none", id="larger-than-cap"),
            pytest.param(70, "grace", id="insufficient-outside-grace"),
            pytest.param(70, "exclusive", id="conversion-locked"),
            pytest.param(70, "shared", id="download-locked"),
        ],
    )
    async def test_impossible_admission_preserves_other_copies(
        self, cache_root, converto, convert_outputs, mocker, size_bytes, blocked
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        older = _seed_cached(_rom_file(file_name="older.iso"))
        protected = _seed_cached(_rom_file(file_name="protected.iso"))
        older.write_bytes(b"x" * 40)
        protected.write_bytes(b"x" * 50)
        now = time.time()
        os.utime(older, (now - 300, now - 300))
        protected_age = 0 if blocked == "grace" else SERVE_GRACE_SECONDS * 2
        os.utime(protected, (now - protected_age, now - protected_age))
        holder = (
            _held_lock(protected.parent, shared=blocked == "shared")
            if blocked in ("exclusive", "shared")
            else nullcontext()
        )

        with holder:
            assert (
                await get_or_convert(
                    1, _rom_file(file_size_bytes=size_bytes), "psp", "chd"
                )
                is None
            )

        assert older.read_bytes() == b"x" * 40
        assert protected.read_bytes() == b"x" * 50
        assert convert_outputs == []

    async def test_conversion_evicts_the_least_recently_served_other_copy(
        self, cache_root, converto, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        oldest = _seed_cached(_rom_file(file_name="old.iso"), age_seconds=300)
        newer = _seed_cached(_rom_file(file_name="newer.iso"), age_seconds=200)
        oldest.write_bytes(b"x" * 40)
        newer.write_bytes(b"x" * 40)
        now = time.time()
        os.utime(oldest, (now - 300, now - 300))
        os.utime(newer, (now - 200, now - 200))
        f = _rom_file(file_size_bytes=10)

        async def convert(op, src, out) -> None:
            out.write_bytes(b"converted" * 6)

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        final = await get_or_convert(1, f, "psp", "chd")

        assert final == _final_path(f)
        assert final is not None
        assert final.read_bytes() == b"converted" * 6
        assert not oldest.parent.exists()
        assert newer.exists()
        assert conversion_cache.cache_size_bytes() <= 100

    async def test_post_conversion_cleanup_failure_still_serves_the_copy(
        self, cache_root, convert_outputs, mocker
    ):
        f = _rom_file()
        final = _final_path(f)
        cleanup = conversion_cache.cleanup_stale_conversions

        def fail_after_publication(*args, **kwargs):
            if final.exists():
                raise RuntimeError("cleanup failed")
            return cleanup(*args, **kwargs)

        mocker.patch.object(
            conversion_cache,
            "cleanup_stale_conversions",
            side_effect=fail_after_publication,
        )

        assert await get_or_convert(1, f, "psp", "chd") == final
        assert final.read_bytes() == b"converted"

    async def test_locked_key_dir_returns_none(self, cache_root, convert_outputs):
        f = _rom_file()
        key_dir = _final_path(f).parent
        key_dir.mkdir(parents=True)

        with _held_lock(key_dir):
            assert await get_or_convert(1, f, "psp", "chd") is None
        assert convert_outputs == []

    async def test_concurrent_request_returns_none_while_one_converts(
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

    async def test_queued_conversion_checks_budget_after_a_slot_opens(
        self, cache_root, converto, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        mocker.patch.object(
            conversion_cache, "_convert_semaphore", asyncio.Semaphore(1)
        )
        first_file = _rom_file(file_size_bytes=10)
        second_file = _rom_file(file_name="second.iso", file_size_bytes=10)
        second_dir = _final_path(second_file).parent
        started = asyncio.Event()
        release = asyncio.Event()

        async def convert(op, src, out) -> None:
            started.set()
            await release.wait()
            out.write_bytes(b"x" * 100)

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        first = asyncio.create_task(get_or_convert(1, first_file, "psp", "chd"))
        await started.wait()
        second = asyncio.create_task(get_or_convert(1, second_file, "psp", "chd"))
        try:
            while not second.done():
                if second_dir.exists():
                    with conversion_cache._try_lock(second_dir) as locked:
                        if not locked:
                            break
                await asyncio.sleep(0)
            queued = not second.done()
        finally:
            release.set()
            results = await asyncio.gather(first, second)

        assert queued
        assert list(results) == [_final_path(first_file), None]
        assert _final_path(first_file).read_bytes() == b"x" * 100
        assert not _final_path(second_file).exists()

    async def test_writes_in_partial_dir_then_renames_into_place(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()
        final = _final_path(f)

        assert await get_or_convert(1, f, "psp", "chd") == final
        assert convert_outputs == [_partial_path(final)]
        assert final.read_bytes() == b"converted"
        assert [p.name for p in final.parent.iterdir()] == [final.name]

    async def test_leading_dot_copy_survives_cleanup(self, cache_root, convert_outputs):
        f = _rom_file(file_name=".hack - Infection (USA).iso")
        final = _final_path(f)

        assert await get_or_convert(1, f, "psp", "chd") == final
        assert final.name == ".hack - Infection (USA).chd"
        assert conversion_cache.cleanup_stale_conversions() == 0
        assert final.read_bytes() == b"converted"
        assert get_cached_converted(1, f, "psp", "chd") == final

    async def test_removes_all_a_crashed_runs_partial_outputs(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()
        final = _final_path(f)
        final.parent.mkdir(parents=True)
        partial = _partial_path(final)
        partial.parent.mkdir()
        for path in (
            partial,
            partial.with_name(f".{partial.name}.ABCDEF.tmp"),
            partial.with_suffix(".bin"),
        ):
            path.write_bytes(b"leftover")

        assert await get_or_convert(1, f, "psp", "chd") == final
        assert final.read_bytes() == b"converted"
        assert list(final.parent.iterdir()) == [final]

    @pytest.mark.parametrize(
        ("error", "writes_partial"),
        [
            pytest.param(RomConvertoOperationError, False, id="nonzero-exit-no-output"),
            pytest.param(RomConvertoOperationError, True, id="nonzero-exit-partials"),
            pytest.param(RomConvertoTimeoutError, True, id="timeout-partials"),
        ],
    )
    async def test_failed_conversion_retries_only_after_marker_expires(
        self, cache_root, converto, mocker, error, writes_partial
    ):
        f = _rom_file()
        final = _final_path(f)
        marker = final.parent / FAILED_FILE

        async def convert(op, src, out) -> None:
            if writes_partial:
                out.write_bytes(b"partial")
                out.with_name(f".{out.name}.ABCDEF.tmp").write_bytes(b"scratch")
                out.with_suffix(".bin").write_bytes(b"data")
            raise error("boom")

        convert_mock = mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert list(final.parent.iterdir()) == [marker]
        assert await get_or_convert(1, f, "psp", "chd") is None
        convert_mock.assert_awaited_once()
        expired = time.time() - converto.cache_ttl_hours * 3600 - 1
        os.utime(marker, (expired, expired))
        assert conversion_cache.cleanup_stale_conversions() == 1

        async def succeed(op, src, out) -> None:
            out.write_bytes(b"converted")

        convert_mock.side_effect = succeed
        assert await get_or_convert(1, f, "psp", "chd") == final
        assert final.read_bytes() == b"converted"
        assert not marker.exists()

    @pytest.mark.parametrize(
        "stage",
        [
            pytest.param("mkdir", id="partial-dir-error"),
            pytest.param("replace", id="publication-error"),
            pytest.param("convert-os-error", id="subprocess-os-error"),
            pytest.param("missing-binary", id="binary-not-found"),
        ],
    )
    async def test_transient_failure_retries_the_next_download(
        self, cache_root, mocker, stage
    ):
        f = _rom_file()
        final = _final_path(f)
        failed = False

        async def convert(op, src, out) -> None:
            nonlocal failed
            if not failed and stage in ("convert-os-error", "missing-binary"):
                failed = True
                error = (
                    RomConvertoBinaryNotFoundError
                    if stage == "missing-binary"
                    else OSError
                )
                raise error("temporary failure")
            out.write_bytes(b"converted")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )
        if stage in ("mkdir", "replace"):
            write = Path.mkdir if stage == "mkdir" else os.replace

            def fail_write_once(*args, **kwargs):
                nonlocal failed
                if not failed and (stage == "replace" or args[0].name == PARTIAL_DIR):
                    failed = True
                    raise OSError("temporary filesystem failure")
                return write(*args, **kwargs)

            mocker.patch(
                "pathlib.Path.mkdir" if stage == "mkdir" else "os.replace",
                side_effect=fail_write_once,
                autospec=True,
            )

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert not (final.parent / FAILED_FILE).exists()
        assert not (final.parent / PARTIAL_DIR).exists()
        assert await get_or_convert(1, f, "psp", "chd") == final
        assert final.read_bytes() == b"converted"

    async def test_split_conversion_returns_none_without_publishing(
        self, cache_root, mocker
    ):
        f = _rom_file()
        final = _final_path(f)

        async def convert(op, src, out) -> None:
            out.write_bytes(b'FILE "game.bin" BINARY')
            out.with_suffix(".bin").write_bytes(b"data")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        assert await get_or_convert(1, f, "psp", "chd") is None
        assert not final.exists()
        assert list(final.parent.iterdir()) == [final.parent / FAILED_FILE]

    async def test_cancellation_removes_every_partial_output(self, cache_root, mocker):
        f = _rom_file()
        final = _final_path(f)
        started = asyncio.Event()

        async def convert(op, src, out) -> None:
            out.write_bytes(b"partial")
            out.with_name(f".{out.name}.ABCDEF.tmp").write_bytes(b"scratch")
            out.with_suffix(".bin").write_bytes(b"data")
            started.set()
            await asyncio.Event().wait()

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        conversion = asyncio.create_task(get_or_convert(1, f, "psp", "chd"))
        await started.wait()
        conversion.cancel()
        with pytest.raises(asyncio.CancelledError):
            await conversion

        assert not final.exists()
        assert list(final.parent.iterdir()) == []


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

    @pytest.mark.parametrize(
        "touch",
        [
            pytest.param(False, id="lookup"),
            pytest.param(True, id="download"),
        ],
    )
    def test_returns_none_while_key_dir_is_locked(self, cache_root, touch):
        f = _rom_file()
        final = _seed_cached(f)

        with _held_lock(final.parent):
            assert get_cached_converted(1, f, "psp", "chd", touch=touch) is None

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(FileNotFoundError, id="touch-not-found"),
            pytest.param(PermissionError, id="permission-denied"),
        ],
    )
    def test_touch_failure_still_serves_the_copy(self, cache_root, mocker, error):
        f = _rom_file()
        final = _seed_cached(f)
        mocker.patch("os.utime", side_effect=error)

        assert get_cached_converted(1, f, "psp", "chd", touch=True) == final
        assert final.read_bytes() == b"cached"

    def test_lock_open_failure_returns_none(self, cache_root, mocker):
        f = _rom_file()
        _seed_cached(f)
        mocker.patch("os.open", side_effect=PermissionError)

        assert get_cached_converted(1, f, "psp", "chd") is None

    @pytest.mark.parametrize(
        "recreate",
        [
            pytest.param(False, id="removed"),
            pytest.param(True, id="recreated"),
        ],
    )
    def test_does_not_serve_a_replaced_key_dir(self, cache_root, mocker, recreate):
        f = _rom_file()
        final = _seed_cached(f)
        flock = fcntl.flock

        def replace_dir(fd, mode):
            flock(fd, mode)
            shutil.rmtree(final.parent)
            if recreate:
                final.parent.mkdir()
                final.write_bytes(b"replacement")

        mocker.patch("fcntl.flock", side_effect=replace_dir)

        assert get_cached_converted(1, f, "psp", "chd") is None


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
        partial_dir = key_dir / PARTIAL_DIR
        partial_dir.mkdir()
        (partial_dir / "other.chd").write_bytes(b"x" * 20)

        assert conversion_cache.has_room_for(40)
        assert not conversion_cache.has_room_for(41)

    @pytest.mark.parametrize(
        "vanishes",
        [
            pytest.param("file", id="vanishing-file"),
            pytest.param("dir", id="vanishing-dir"),
        ],
    )
    def test_size_walk_tolerates_vanishing_entries(self, cache_root, mocker, vanishes):
        vanished = _seed_cached(_rom_file(file_name="vanished.iso"))
        survivor = _seed_cached(_rom_file(file_name="survivor.iso"))
        stat = os.stat
        scandir = os.scandir

        if vanishes == "file":

            def stat_after_removal(path, *args, **kwargs):
                if path == str(vanished):
                    vanished.unlink(missing_ok=True)
                return stat(path, *args, **kwargs)

            mocker.patch("os.stat", side_effect=stat_after_removal)
        else:

            def scan_after_removal(path):
                if path == str(vanished.parent):
                    shutil.rmtree(vanished.parent)
                return scandir(path)

            mocker.patch("os.scandir", side_effect=scan_after_removal)

        assert conversion_cache.cache_size_bytes() == len(b"cached")
        assert survivor.read_bytes() == b"cached"


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

    def test_removes_partial_outputs_from_a_kept_dir(self, cache_root):
        final = _seed_cached(_rom_file())
        partial = _partial_path(final)
        partial.parent.mkdir()
        for path in (
            partial,
            partial.with_name(f".{partial.name}.ABCDEF.tmp"),
            partial.with_suffix(".bin"),
        ):
            path.write_bytes(b"leftover")

        assert conversion_cache.cleanup_stale_conversions() == 0
        assert final.read_bytes() == b"cached"
        assert list(final.parent.iterdir()) == [final]

    @pytest.mark.parametrize(
        "leftover",
        [
            pytest.param(False, id="empty"),
            pytest.param(True, id="partial"),
        ],
    )
    def test_deletes_dirs_without_a_served_copy(self, cache_root, leftover):
        key_dir = cache_root / "1-e"
        key_dir.mkdir()
        if leftover:
            partial_dir = key_dir / PARTIAL_DIR
            partial_dir.mkdir()
            (partial_dir / "game.chd").write_bytes(b"partial")

        assert conversion_cache.cleanup_stale_conversions() == 1
        assert not key_dir.exists()

    def test_skips_a_dir_whose_conversion_is_running(self, cache_root):
        key_dir = cache_root / "1-busy"
        key_dir.mkdir()
        partial_dir = key_dir / PARTIAL_DIR
        partial_dir.mkdir()
        (partial_dir / "game.chd").write_bytes(b"partial")

        with _held_lock(key_dir):
            assert conversion_cache.cleanup_stale_conversions() == 0
        assert key_dir.exists()

    def test_kept_copy_remains_available_during_cleanup(self, cache_root, mocker):
        f = _rom_file()
        final = _seed_cached(f)
        files = conversion_cache._files

        def serve_during_listing(key_dir):
            listed = files(key_dir)
            assert get_cached_converted(1, f, "psp", "chd") == final
            return listed

        mocker.patch.object(
            conversion_cache, "_files", side_effect=serve_during_listing
        )

        assert conversion_cache.cleanup_stale_conversions() == 0
        assert final.read_bytes() == b"cached"

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

    @pytest.mark.parametrize(
        "reserve_bytes",
        [
            pytest.param(0, id="post-conversion"),
            pytest.param(70, id="admission"),
        ],
    )
    def test_size_eviction_preserves_failure_markers(
        self, cache_root, converto, mocker, reserve_bytes
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        marker_dir = cache_root / "1-failed"
        marker_dir.mkdir()
        marker = marker_dir / FAILED_FILE
        marker.touch()
        served = time.time() - 3600
        os.utime(marker, (served, served))
        recent = _seed_cached(_rom_file())
        recent.write_bytes(b"x" * 120)

        assert conversion_cache.cleanup_stale_conversions(reserve_bytes) == 0
        assert marker.exists()
        assert recent.read_bytes() == b"x" * 120

    @pytest.mark.parametrize(
        ("age_seconds", "kept"),
        [
            pytest.param(SERVE_GRACE_SECONDS // 2, True, id="within-grace"),
            pytest.param(SERVE_GRACE_SECONDS * 2, False, id="after-grace"),
        ],
    )
    def test_size_eviction_respects_serve_grace(
        self, cache_root, converto, mocker, age_seconds, kept
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        final = _seed_cached(_rom_file())
        final.write_bytes(b"x" * 120)
        served = time.time() - age_seconds
        os.utime(final, (served, served))

        assert conversion_cache.cleanup_stale_conversions() == (0 if kept else 1)
        assert final.exists() is kept

    def test_size_eviction_rechecks_a_copy_served_after_the_ttl_pass(
        self, cache_root, converto, mocker
    ):
        converto.cache_max_size_gb = 1
        mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)
        f = _rom_file()
        final = _seed_cached(f)
        final.write_bytes(b"x" * 120)
        served = time.time() - 120
        os.utime(final, (served, served))
        iterdir = Path.iterdir

        def serve_after_listing(path):
            yield from iterdir(path)
            if path == cache_root:
                assert get_cached_converted(1, f, "psp", "chd", touch=True) == final

        mocker.patch.object(
            Path, "iterdir", side_effect=serve_after_listing, autospec=True
        )

        assert conversion_cache.cleanup_stale_conversions() == 0
        assert final.read_bytes() == b"x" * 120


class TestParseFormats:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param("zso,iso", ("zso", "iso"), id="in-order"),
            pytest.param(" ZSO , iso,zso ", ("zso", "iso"), id="trimmed-deduplicated"),
            pytest.param(",,", (), id="empty"),
        ],
    )
    def test_parses_the_list(self, raw: str, expected: tuple[str, ...]):
        assert parse_formats(raw) == expected


class TestResolveFormatDownload:
    @pytest.fixture(autouse=True)
    def enabled(self, converto, mocker):
        converto.download_conversion_enabled = True
        mocker.patch(
            "utils.conversion_cache.rom_converto_service.is_enabled",
            AsyncMock(return_value=True),
        )

    @staticmethod
    def _rom() -> Rom:
        return cast(Rom, SimpleNamespace(id=1, platform_slug="psp"))

    async def test_a_listed_stored_format_wins_over_a_cached_copy(self, cache_root):
        f = _rom_file()
        _seed_cached(f)

        resolution = await resolve_format_download(
            self._rom(), f, ("chd", "iso"), allowed=True, start=True, touch=True
        )

        assert resolution == FormatResolution(FormatOutcome.ORIGINAL)

    async def test_a_cached_copy_wins_over_an_earlier_uncached_format(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()
        final = _seed_cached(f)

        resolution = await resolve_format_download(
            self._rom(), f, ("cso", "chd"), allowed=True, start=True, touch=True
        )

        assert resolution == FormatResolution(FormatOutcome.CONVERTED, final)
        assert convert_outputs == []

    async def test_converts_to_the_first_listed_format_it_can_produce(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()

        resolution = await resolve_format_download(
            self._rom(), f, ("rvz", "cso", "chd"), allowed=True, start=True, touch=True
        )

        assert resolution.outcome == FormatOutcome.CONVERTED
        assert resolution.path is not None and resolution.path.suffix == ".cso"
        assert [out.suffix for out in convert_outputs] == [".cso"]

    async def test_skips_a_format_whose_conversion_failed(
        self, cache_root, convert_outputs
    ):
        f = _rom_file()
        failed = _final_path(f).parent
        failed.mkdir(parents=True)
        (failed / FAILED_FILE).touch()

        resolution = await resolve_format_download(
            self._rom(), f, ("chd", "cso"), allowed=True, start=True, touch=True
        )

        assert resolution.path is not None and resolution.path.suffix == ".cso"

    async def test_reports_pending_without_starting(self, cache_root, convert_outputs):
        resolution = await resolve_format_download(
            self._rom(), _rom_file(), ("chd",), allowed=True, start=False, touch=False
        )

        assert resolution.outcome == FormatOutcome.PENDING
        assert convert_outputs == []

    async def test_falls_back_to_a_later_format_when_a_conversion_fails(
        self, cache_root, mocker
    ):
        async def convert(operation, src, out) -> None:
            if out.suffix == ".cso":
                raise RomConvertoOperationError("bad image")
            out.write_bytes(b"converted")

        mocker.patch(
            "utils.conversion_cache.rom_converto_service.convert", side_effect=convert
        )

        resolution = await resolve_format_download(
            self._rom(),
            _rom_file(),
            ("cso", "chd"),
            allowed=True,
            start=True,
            touch=True,
        )

        assert resolution.path is not None and resolution.path.suffix == ".chd"

    async def test_a_locked_key_dir_without_partial_output_is_pending(
        self, cache_root, convert_outputs
    ):
        key_dir = _final_path(_rom_file()).parent
        key_dir.mkdir(parents=True)

        with _held_lock(key_dir):
            resolution = await resolve_format_download(
                self._rom(), _rom_file(), ("chd",), allowed=True, start=True, touch=True
            )

        assert resolution.outcome == FormatOutcome.PENDING
        assert convert_outputs == []

    async def test_is_pending_without_starting_once_too_many_conversions_run(
        self, cache_root, convert_outputs, mocker
    ):
        mocker.patch.object(conversion_cache, "MAX_STARTED_CONVERSIONS", 0)

        resolution = await resolve_format_download(
            self._rom(), _rom_file(), ("chd",), allowed=True, start=True, touch=True
        )

        assert resolution.outcome == FormatOutcome.PENDING
        assert convert_outputs == []
