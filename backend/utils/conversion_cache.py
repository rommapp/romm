from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from adapters.services.rom_converto import (
    Operation,
    resolve_operation,
    rom_converto_service,
)
from config import (
    LIBRARY_BASE_PATH,
    ROM_CONVERTO_CACHE_MAX_SIZE_GB,
    ROM_CONVERTO_CACHE_PATH,
    ROM_CONVERTO_MAX_SYNC_SIZE_MB,
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
# A fresher sentinel means another worker is actively converting.
PARTIAL_STALE_SECONDS = 6 * SECONDS_PER_HOUR
SENTINEL_NAME = ".partial"


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


def _cached_files(key_dir: Path) -> list[Path]:
    """Every file a key dir holds on disk, in-flight temporaries included."""
    return [
        p
        for p in key_dir.iterdir()
        if p.is_file() and not p.name.startswith(SENTINEL_NAME)
    ]


def _dir_size(files: list[Path]) -> int:
    total = 0
    for p in files:
        with contextlib.suppress(OSError):
            total += p.stat().st_size
    return total


def _sentinel_is_fresh(sentinel: Path, now: float) -> bool:
    """Whether a `.partial` sentinel marks a conversion still in flight."""
    return sentinel.stat().st_mtime >= now - PARTIAL_STALE_SECONDS


def cache_size_bytes() -> int:
    """Bytes every key dir holds on disk, in-flight temporaries included."""
    cache_root = Path(ROM_CONVERTO_CACHE_PATH)
    if not cache_root.exists():
        return 0
    return sum(_dir_size(_cached_files(d)) for d in cache_root.iterdir() if d.is_dir())


def has_room_for(size_bytes: int) -> bool:
    """Whether adding `size_bytes` keeps the cache under ROM_CONVERTO_CACHE_MAX_SIZE_GB."""
    max_bytes = ROM_CONVERTO_CACHE_MAX_SIZE_GB * BYTES_PER_GB
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
    if not final_path.exists():
        return None
    if touch:
        # Keep a served file fresh so TTL cleanup measures demand.
        with contextlib.suppress(OSError):
            os.utime(final_path)
    return final_path


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
    rom: Rom, file: RomFile, *, start_conversion: bool
) -> Path | None:
    """The converted copy of a single-file download, or None to serve the original.

    Args:
        start_conversion: Convert when nothing is cached, waiting for files
            within ROM_CONVERTO_MAX_SYNC_SIZE_MB and converting larger ones
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

    cached = get_cached_converted(
        rom.id, file, rom.platform_slug, target, touch=start_conversion
    )
    if cached or not start_conversion:
        return cached
    # The conversion always finishes into the cache; past the size cap or
    # the deadline the original is served meanwhile, instead of a 504.
    conversion = fire_and_forget(
        get_or_convert(rom.id, file, rom.platform_slug, target)
    )
    if (
        file.file_size_bytes or rom.fs_size_bytes
    ) > ROM_CONVERTO_MAX_SYNC_SIZE_MB * 1024 * 1024:
        return None
    done, _ = await asyncio.wait({conversion}, timeout=SYNC_CONVERSION_DEADLINE_SECONDS)
    return conversion.result() if done else None


async def get_or_convert(
    rom_id: int,
    rom_file: RomFile,
    platform_slug: str,
    target: str,
) -> Path | None:
    """The converted file, converting it once under a `.partial` sentinel, or None to serve the original."""
    found = _lookup(rom_id, rom_file, platform_slug, target)
    if found is None:
        return None
    operation, final_path = found
    key_dir = final_path.parent
    sentinel = key_dir / SENTINEL_NAME

    try:
        if cached := _serve_cached(final_path, touch=True):
            return cached

        if not await asyncio.to_thread(has_room_for, rom_file.file_size_bytes or 0):
            log.info(
                f"Conversion cache is full, not converting ROM {rom_id} (target {hl(target)})"
            )
            return None

        key_dir.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _sentinel_is_fresh(sentinel, time.time()):
                # Another worker is converting; serve the original meanwhile.
                return None
            # Stale sentinel from a crashed run: rename it aside atomically so
            # the key dir never disappears under a worker that lost the race.
            stale = sentinel.with_name(
                f"{SENTINEL_NAME}.stale-{os.getpid()}-{time.time_ns()}"
            )
            os.replace(sentinel, stale)
            fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with contextlib.suppress(OSError):
                stale.unlink()
        os.close(fd)
    except Exception as e:
        log.warning(
            f"Conversion cache unavailable for ROM {rom_id} (target {hl(target)}): {e}; serving original"
        )
        return None

    # A per-process temporary name hides partial output from readers and from
    # the worker a stale-sentinel takeover displaced.
    produced = final_path.with_name(
        f"{final_path.stem}.tmp{os.getpid()}{final_path.suffix}"
    )
    try:
        produced.unlink(missing_ok=True)
        await rom_converto_service.convert(
            operation, src=Path(LIBRARY_BASE_PATH) / rom_file.full_path, out=produced
        )
        os.replace(produced, final_path)
    except Exception as e:
        log.warning(
            f"Conversion failed for ROM {rom_id} (target {hl(target)}): {e}; serving original"
        )
        return None
    finally:
        with contextlib.suppress(OSError):
            produced.unlink(missing_ok=True)
            sentinel.unlink()

    # The file can vanish (e.g. TTL cleanup) between the replace and here;
    # only return a path that actually exists right now.
    return final_path if final_path.exists() else None


def cleanup_stale_conversions() -> int:
    """Remove expired or leaked key dirs, then evict the least recently served until under the size cap."""
    cache_root = Path(ROM_CONVERTO_CACHE_PATH)
    if not cache_root.exists():
        return 0

    ttl_seconds = cm.get_config().CONVERTO.cache_ttl_hours * SECONDS_PER_HOUR
    now = time.time()
    deleted = 0
    # (last served, size, key dir) for the dirs that survive the TTL pass.
    kept: list[tuple[float, int, Path]] = []

    for key_dir in cache_root.iterdir():
        if not key_dir.is_dir():
            continue
        sentinel = key_dir / SENTINEL_NAME
        # A conversion finishing or a download racing this pass can rename or
        # remove a file between listing and stat; leave that dir to next run.
        try:
            files = _cached_files(key_dir)
            if not files:
                # Only an in-flight sentinel makes an empty dir meaningful.
                if sentinel.exists() and _sentinel_is_fresh(sentinel, now):
                    continue
            else:
                stats = [p.stat() for p in files]
                last_served = max(st.st_mtime for st in stats)
                if last_served >= now - ttl_seconds:
                    if not sentinel.exists():
                        size = sum(st.st_size for st in stats)
                        kept.append((last_served, size, key_dir))
                    continue
        except FileNotFoundError:
            continue
        shutil.rmtree(key_dir, ignore_errors=True)
        deleted += 1

    max_bytes = ROM_CONVERTO_CACHE_MAX_SIZE_GB * BYTES_PER_GB
    used = sum(size for _, size, _ in kept)
    for _, size, key_dir in sorted(kept):
        if not max_bytes or used <= max_bytes:
            break
        shutil.rmtree(key_dir, ignore_errors=True)
        used -= size
        deleted += 1

    return deleted
