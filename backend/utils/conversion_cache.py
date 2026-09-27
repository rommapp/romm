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
from typing import TYPE_CHECKING

from adapters.services.rom_converto import (
    Operation,
    resolve_operation,
    rom_converto_service,
)
from config import (
    LIBRARY_BASE_PATH,
    ROM_CONVERTO_CACHE_PATH,
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
# Partial output is hidden so cleanup never takes it for a served copy.
PARTIAL_PREFIX = "."


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


def _dir_size(files: list[Path]) -> int:
    total = 0
    for p in files:
        with contextlib.suppress(OSError):
            total += p.stat().st_size
    return total


def _files(key_dir: Path) -> list[Path]:
    return [p for p in key_dir.iterdir() if p.is_file()]


@contextlib.contextmanager
def _try_lock(key_dir: Path) -> Generator[bool]:
    """Lock `key_dir` unless another task or process holds it; the kernel frees it if the holder dies."""
    fd = os.open(key_dir, os.O_RDONLY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        os.close(fd)


def cache_size_bytes() -> int:
    """Bytes every key dir holds on disk, partial output included."""
    cache_root = Path(ROM_CONVERTO_CACHE_PATH)
    if not cache_root.exists():
        return 0
    return sum(_dir_size(_files(d)) for d in cache_root.iterdir() if d.is_dir())


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

        if not await asyncio.to_thread(has_room_for, rom_file.file_size_bytes or 0):
            log.info(
                f"Conversion cache is full, not converting ROM {rom_id} (target {hl(target)})"
            )
            return None

        final_path.parent.mkdir(parents=True, exist_ok=True)
        with _try_lock(final_path.parent) as locked:
            if not locked:
                # Another worker is converting; serve the original meanwhile.
                return None
            # A conversion may have finished between the check above and the lock.
            if cached := _serve_cached(final_path, touch=True):
                return cached
            return await _convert(rom_id, rom_file, target, operation, final_path)
    except Exception as e:
        log.warning(
            f"Conversion cache unavailable for ROM {rom_id} (target {hl(target)}): {e}; serving original"
        )
        return None


async def _convert(
    rom_id: int, rom_file: RomFile, target: str, operation: Operation, final_path: Path
) -> Path | None:
    """Convert into a partial file and rename it into place; the caller holds the key dir lock."""
    produced = final_path.with_name(
        f"{PARTIAL_PREFIX}{final_path.stem}.tmp{final_path.suffix}"
    )
    try:
        # A crashed run can leave its partial output behind.
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
    return final_path


def cleanup_stale_conversions() -> int:
    """Remove expired or leaked key dirs, then evict the least recently served until under the size cap."""
    cache_root = Path(ROM_CONVERTO_CACHE_PATH)
    if not cache_root.exists():
        return 0

    converto = cm.get_config().CONVERTO
    ttl_seconds = converto.cache_ttl_hours * SECONDS_PER_HOUR
    now = time.time()
    deleted = 0
    # (last served, size, key dir) for the dirs that survive the TTL pass.
    kept: list[tuple[float, int, Path]] = []

    for key_dir in cache_root.iterdir():
        if not key_dir.is_dir():
            continue
        # A download racing this pass can remove a file between listing and
        # stat; leave that dir to the next run.
        with contextlib.suppress(FileNotFoundError), _try_lock(key_dir) as locked:
            if not locked:
                continue
            stats = [
                p.stat()
                for p in _files(key_dir)
                if not p.name.startswith(PARTIAL_PREFIX)
            ]
            last_served = max((st.st_mtime for st in stats), default=0.0)
            if last_served >= now - ttl_seconds:
                kept.append((last_served, sum(st.st_size for st in stats), key_dir))
                continue
            # Expired, or holding only a crashed run's partial output.
            shutil.rmtree(key_dir, ignore_errors=True)
            deleted += 1

    max_bytes = converto.cache_max_size_gb * BYTES_PER_GB
    used = sum(size for _, size, _ in kept)
    for _, size, key_dir in sorted(kept):
        if not max_bytes or used <= max_bytes:
            break
        with contextlib.suppress(FileNotFoundError), _try_lock(key_dir) as locked:
            if not locked:
                continue
            shutil.rmtree(key_dir, ignore_errors=True)
            used -= size
            deleted += 1

    return deleted
