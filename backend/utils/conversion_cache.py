from __future__ import annotations

import asyncio
import contextlib
import fcntl
import hashlib
import os
import shutil
import time
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Final

from adapters.services.rom_converto import (
    UNCOMPRESSED_TARGETS,
    Operation,
    RomConvertoOperationError,
    RomConvertoTimeoutError,
    resolve_operation,
    rom_converto_service,
)
from config import (
    LIBRARY_BASE_PATH,
    ROM_CONVERTO_CACHE_PATH,
    ROM_CONVERTO_MAX_CONCURRENCY,
    ROMM_BASE_PATH,
)
from config.config_manager import config_manager as cm
from logger.formatter import highlight as hl
from logger.logger import log
from utils.background_tasks import fire_and_forget
from utils.zip_cache import CACHE_KEY_LENGTH, SECONDS_PER_HOUR

if TYPE_CHECKING:
    from models.rom import Rom, RomFile

BYTES_PER_GB = 1024**3
# Kept under the proxy_read_timeout nginx applies to /api (300s).
SYNC_CONVERSION_DEADLINE_SECONDS = 240
PARTIAL_DIR: Final = ".partial"
FAILED_FILE: Final = ".failed"
# Give nginx time to open a copy after the X-Accel-Redirect response.
SERVE_GRACE_SECONDS: Final = 60
# Room a conversion to an uncompressed target reserves per input byte; the
# cleanup pass after it evicts any overshoot.
EXPANSION_RESERVE_FACTOR: Final = 4

# Each conversion reads and writes whole disc images.
_convert_semaphore = asyncio.Semaphore(ROM_CONVERTO_MAX_CONCURRENCY)


def converted_file_path(
    rom_id: int, rom_file: RomFile, operation: Operation, input_ext: str
) -> Path:
    """Deterministic cache path for a converted ROM file."""
    key = hashlib.sha1(
        f"{rom_file.file_path}/{rom_file.file_name}|{rom_file.last_modified}|{rom_file.file_size_bytes}|{operation.target}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:CACHE_KEY_LENGTH]
    key_dir = Path(ROM_CONVERTO_CACHE_PATH) / f"{rom_id}-{key}"
    return key_dir / operation.output_name(Path(rom_file.file_name), input_ext)


def get_redirect_path(converted_path: Path) -> Path:
    """The nginx-internal path for a converted file (`/cache/` aliases `${ROMM_BASE_PATH}/cache/`)."""
    return Path("/") / converted_path.relative_to(ROMM_BASE_PATH)


def _dir_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            with contextlib.suppress(OSError):
                total += os.stat(os.path.join(root, name)).st_size
    return total


def _files(key_dir: Path) -> list[Path]:
    return [p for p in key_dir.iterdir() if p.is_file()]


@contextlib.contextmanager
def _try_lock(key_dir: Path, *, shared: bool = False) -> Generator[bool]:
    """Lock the key dir without blocking, yielding False if it is busy, removed or replaced."""
    fd = os.open(key_dir, os.O_RDONLY)
    try:
        try:
            mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            fcntl.flock(fd, mode | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            current_dir = os.path.samestat(os.fstat(fd), os.stat(key_dir))
        except FileNotFoundError:
            current_dir = False
        yield current_dir
    finally:
        os.close(fd)


def cache_size_bytes() -> int:
    """Bytes every key dir holds on disk, partial output included."""
    return _dir_size(Path(ROM_CONVERTO_CACHE_PATH))


def has_room_for(size_bytes: int) -> bool:
    """Whether adding `size_bytes` keeps the cache under `converto.cache_max_size_gb`."""
    max_bytes = cm.get_config().CONVERTO.cache_max_size_gb * BYTES_PER_GB
    return not max_bytes or cache_size_bytes() + size_bytes <= max_bytes


def _lookup(
    rom_id: int, rom_file: RomFile, platform_slug: str, target: str
) -> tuple[Operation, Path] | None:
    """The operation bringing `rom_file` to `target` and its cache path."""
    resolved = resolve_operation(platform_slug, target, rom_file.file_name)
    if resolved is None:
        return None
    operation, input_ext = resolved
    return operation, converted_file_path(rom_id, rom_file, operation, input_ext)


def _serve_cached(final_path: Path, *, touch: bool) -> Path | None:
    """`final_path` if it is cached, or None while cleanup or a conversion holds its dir."""
    with (
        contextlib.suppress(OSError),
        _try_lock(final_path.parent, shared=True) as locked,
    ):
        if locked and final_path.exists():
            if touch:
                # Keep a served file fresh so TTL cleanup measures demand.
                with contextlib.suppress(OSError):
                    os.utime(final_path)
            return final_path
    return None


def get_cached_converted(
    rom_id: int,
    rom_file: RomFile,
    platform_slug: str,
    target: str,
    *,
    touch: bool = False,
) -> Path | None:
    """The converted file if it is already cached, without converting.

    Args:
        touch: Refresh its mtime so TTL cleanup measures demand.
    """
    found = _lookup(rom_id, rom_file, platform_slug, target)
    return _serve_cached(found[1], touch=touch) if found else None


async def resolve_converted_download(
    rom: Rom, file: RomFile, *, touch: bool, start_conversion: bool
) -> Path | None:
    """The converted copy of a single-file download, or None to serve the original.

    Args:
        touch: Refresh a cached copy's mtime when serving a download.
        start_conversion: Convert when nothing is cached, waiting for files
            within `converto.max_sync_size_mb` and converting larger ones
            in the background for the next download.
    """
    converto = cm.get_config().CONVERTO
    target = converto.platform_formats.get(rom.platform_slug)
    if (
        not converto.download_conversion_enabled
        or not target
        or not await rom_converto_service.is_enabled()
    ):
        return None

    cached = get_cached_converted(rom.id, file, rom.platform_slug, target, touch=touch)
    if cached or not start_conversion:
        return cached
    # The conversion always finishes into the cache; past the size cap or
    # the deadline the original is served meanwhile, instead of a 504.
    conversion = fire_and_forget(
        get_or_convert(rom.id, file, rom.platform_slug, target)
    )
    if (
        file.file_size_bytes or rom.fs_size_bytes
    ) > converto.max_sync_size_mb * 1024 * 1024:
        return None
    done, _ = await asyncio.wait({conversion}, timeout=SYNC_CONVERSION_DEADLINE_SECONDS)
    return conversion.result() if done else None


async def get_or_convert(
    rom_id: int,
    rom_file: RomFile,
    platform_slug: str,
    target: str,
) -> Path | None:
    """The converted file, converting it under a lock on its key dir, or None to serve the original."""
    found = _lookup(rom_id, rom_file, platform_slug, target)
    if found is None:
        return None
    operation, final_path = found

    try:
        if cached := _serve_cached(final_path, touch=True):
            return cached

        final_path.parent.mkdir(parents=True, exist_ok=True)
        with _try_lock(final_path.parent) as locked:
            if not locked:
                # Another worker is converting; serve the original meanwhile.
                return None
            # A conversion may have finished between the check above and the lock.
            if final_path.exists():
                with contextlib.suppress(OSError):
                    os.utime(final_path)
                return final_path
            if (final_path.parent / FAILED_FILE).exists():
                return None
            async with _convert_semaphore:
                shutil.rmtree(final_path.parent / PARTIAL_DIR, ignore_errors=True)
                size_bytes = (rom_file.file_size_bytes or 0) * (
                    EXPANSION_RESERVE_FACTOR
                    if operation.target in UNCOMPRESSED_TARGETS
                    else 1
                )
                await asyncio.to_thread(cleanup_stale_conversions, size_bytes)
                if not await asyncio.to_thread(has_room_for, size_bytes):
                    log.info(
                        f"Conversion cache is full, not converting ROM {rom_id} (target {hl(target)})"
                    )
                    return None
                converted = await _convert(
                    rom_id, rom_file, target, operation, final_path
                )
        if converted:
            try:
                await asyncio.to_thread(cleanup_stale_conversions)
            except Exception as e:
                log.warning(
                    f"Conversion cache cleanup failed for ROM {rom_id}: {e}; serving converted copy"
                )
        return converted
    except Exception as e:
        log.warning(
            f"Conversion cache unavailable for ROM {rom_id} (target {hl(target)}): {e}; serving original"
        )
        return None


async def _convert(
    rom_id: int, rom_file: RomFile, target: str, operation: Operation, final_path: Path
) -> Path | None:
    """Convert into a partial file and rename it into place; the caller holds the key dir lock."""
    partial_dir = final_path.parent / PARTIAL_DIR
    produced = partial_dir / final_path.name
    try:
        partial_dir.mkdir()
        await rom_converto_service.convert(
            operation, src=Path(LIBRARY_BASE_PATH) / rom_file.full_path, out=produced
        )
        if any(p != produced for p in _files(partial_dir)):
            log.warning(
                f"Conversion output split into several files for ROM {rom_id} (target {hl(target)}); serving original"
            )
            (final_path.parent / FAILED_FILE).touch()
            return None
        os.replace(produced, final_path)
    except Exception as e:
        log.warning(
            f"Conversion failed for ROM {rom_id} (target {hl(target)}): {e}; serving original"
        )
        if isinstance(e, (RomConvertoOperationError, RomConvertoTimeoutError)):
            (final_path.parent / FAILED_FILE).touch()
        return None
    finally:
        shutil.rmtree(partial_dir, ignore_errors=True)
    return final_path


def cleanup_stale_conversions(reserve_bytes: int = 0) -> int:
    """Remove expired or leaked key dirs, then evict least recently served copies to make room."""
    cache_root = Path(ROM_CONVERTO_CACHE_PATH)
    if not cache_root.exists():
        return 0

    converto = cm.get_config().CONVERTO
    ttl_seconds = converto.cache_ttl_hours * SECONDS_PER_HOUR
    now = time.time()
    deleted = 0
    # (last served, size) of the final copies in each dir that survives the TTL pass.
    kept: list[tuple[float, int, Path]] = []

    for key_dir in cache_root.iterdir():
        if not key_dir.is_dir():
            continue
        with contextlib.suppress(FileNotFoundError):
            stats = {p.name: p.stat() for p in _files(key_dir)}
            last_served = max((st.st_mtime for st in stats.values()), default=0.0)
            partial_dir = key_dir / PARTIAL_DIR
            if last_served < now - ttl_seconds or partial_dir.exists():
                with _try_lock(key_dir) as locked:
                    if locked:
                        stats = {p.name: p.stat() for p in _files(key_dir)}
                        last_served = max(
                            (st.st_mtime for st in stats.values()), default=0.0
                        )
                        if last_served < now - ttl_seconds:
                            shutil.rmtree(key_dir, ignore_errors=True)
                            deleted += 1
                            continue
                        shutil.rmtree(partial_dir, ignore_errors=True)
            # A failure marker frees nothing, and evicting it would retry the conversion.
            stats.pop(FAILED_FILE, None)
            if stats:
                kept.append(
                    (
                        max(st.st_mtime for st in stats.values()),
                        sum(st.st_size for st in stats.values()),
                        key_dir,
                    )
                )

    max_bytes = converto.cache_max_size_gb * BYTES_PER_GB
    if not max_bytes:
        return deleted
    used = cache_size_bytes()
    candidates = sorted(c for c in kept if c[0] < now - SERVE_GRACE_SECONDS)
    if reserve_bytes and used + reserve_bytes > max_bytes:
        evictable = 0
        for _, size, key_dir in candidates:
            # A dir a download or conversion holds right now can't be evicted.
            with contextlib.suppress(FileNotFoundError), _try_lock(key_dir) as locked:
                evictable += size if locked else 0
        if used + reserve_bytes - evictable > max_bytes:
            # Evicting every candidate would still not make room, so keep them.
            return deleted
    for _, _, key_dir in candidates:
        if used + reserve_bytes <= max_bytes:
            break
        with contextlib.suppress(FileNotFoundError), _try_lock(key_dir) as locked:
            # A download may have touched the copy since the pass above.
            if not locked or any(
                p.stat().st_mtime >= now - SERVE_GRACE_SECONDS for p in _files(key_dir)
            ):
                continue
            size = _dir_size(key_dir)
            shutil.rmtree(key_dir, ignore_errors=True)
            used -= size
            deleted += 1

    return deleted
