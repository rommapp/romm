from __future__ import annotations

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
from config import LIBRARY_BASE_PATH, ROM_CONVERTO_CACHE_PATH, ROMM_BASE_PATH
from config.config_manager import config_manager as cm
from logger.formatter import highlight as hl
from logger.logger import log

if TYPE_CHECKING:
    from models.rom import RomFile

CACHE_KEY_LENGTH = 16
SECONDS_PER_HOUR = 3600
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
    """The nginx-internal path for a converted file (`/cache/` aliases
    `${ROMM_BASE_PATH}/cache/`)."""
    return Path("/") / converted_path.relative_to(ROMM_BASE_PATH)


def get_cached_converted(
    rom_id: int, rom_file: RomFile, platform_slug: str, target: str
) -> Path | None:
    """The converted file if it is already cached, without converting."""
    resolved = resolve_operation(platform_slug, target, rom_file.file_name)
    if resolved is None:
        return None
    final_path = converted_file_path(rom_id, rom_file, *resolved)
    return final_path if final_path.exists() else None


async def get_or_convert(
    rom_id: int, rom_file: RomFile, platform_slug: str, target: str
) -> Path | None:
    """Return the converted file's path, converting it on demand.

    Single-flight via a `.partial` sentinel. Never raises; returns None
    whenever the file cannot be served converted (already in the target
    format, no subcommand accepts it, another worker is converting it, or
    the conversion failed) so the caller serves the original.
    """
    resolved = resolve_operation(platform_slug, target, rom_file.file_name)
    if resolved is None:
        return None
    operation, input_ext = resolved
    final_path = converted_file_path(rom_id, rom_file, operation, input_ext)
    key_dir = final_path.parent
    sentinel = key_dir / SENTINEL_NAME

    try:
        if final_path.exists():
            # Keep a served file fresh so TTL cleanup measures demand.
            os.utime(final_path)
            return final_path

        key_dir.mkdir(parents=True, exist_ok=True)
        stale_sentinel = None
        try:
            fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if sentinel.stat().st_mtime >= time.time() - PARTIAL_STALE_SECONDS:
                # Another worker is converting; serve the original meanwhile.
                return None
            # Stale sentinel from a crashed run: rename it aside atomically
            # (rmtree-then-recreate would leave a window with no key dir for
            # a concurrent worker that lost the race) and clean it up below.
            stale_sentinel = sentinel.with_name(
                f"{SENTINEL_NAME}.stale-{os.getpid()}-{time.time_ns()}"
            )
            os.replace(sentinel, stale_sentinel)
            fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        if stale_sentinel is not None:
            with contextlib.suppress(OSError):
                stale_sentinel.unlink()
    except Exception as e:
        log.warning(
            f"Conversion cache unavailable for ROM {rom_id} (target {hl(target)}): {e}; serving original"
        )
        return None

    # Written under a per-process temporary name so a reader never sees a
    # partial file and a worker that took over a stale sentinel never
    # collides with the one it displaced.
    produced = final_path.with_name(
        f"{final_path.stem}.tmp{os.getpid()}{final_path.suffix}"
    )
    try:
        produced.unlink(missing_ok=True)
        await rom_converto_service.convert(
            operation, src=Path(LIBRARY_BASE_PATH) / rom_file.full_path, out=produced
        )
        try:
            os.replace(produced, final_path)
        except PermissionError:
            # Windows: a concurrent request may still stream the old final
            # file; if a final file is in place, serving it is success.
            if not final_path.exists():
                raise
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
    """Remove key dirs whose final file exceeded the configured TTL, and
    sentinel-only dirs whose last conversion attempt is older than 6 hours."""
    cache_root = Path(ROM_CONVERTO_CACHE_PATH)
    if not cache_root.exists():
        return 0

    ttl_seconds = cm.get_config().CONVERTO.cache_ttl_hours * SECONDS_PER_HOUR
    now = time.time()
    deleted = 0

    for key_dir in cache_root.iterdir():
        if not key_dir.is_dir():
            continue
        files = [
            p
            for p in key_dir.iterdir()
            if p.is_file() and not p.name.startswith(SENTINEL_NAME)
        ]
        stale_cutoff = now - (PARTIAL_STALE_SECONDS if not files else ttl_seconds)
        if not files:
            sentinel = key_dir / SENTINEL_NAME
            if not sentinel.exists():
                # Neither a final file nor an in-flight sentinel: an empty
                # leaked dir. Only sentinels and final files are meaningful.
                shutil.rmtree(key_dir, ignore_errors=True)
                deleted += 1
                continue
            if sentinel.stat().st_mtime >= stale_cutoff:
                continue
        elif any(p.stat().st_mtime >= stale_cutoff for p in files):
            continue
        shutil.rmtree(key_dir, ignore_errors=True)
        deleted += 1

    return deleted
