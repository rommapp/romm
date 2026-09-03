from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from adapters.services.rom_converto import rom_converto_service
from config import LIBRARY_BASE_PATH, ROM_CONVERTO_CACHE_PATH
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

# Target slug -> output file extension.
TARGET_EXTENSIONS = {
    "cia-decrypted": ".cia",
    "iso": ".iso",
    "chd": ".chd",
    "rvz": ".rvz",
    "nsp": ".nsp",
    "iso-decrypted": ".iso",
}


def converted_file_path(rom_id: int, rom_file: RomFile, target: str) -> Path:
    """Deterministic cache path for a converted ROM file."""
    key = hashlib.sha1(
        f"{rom_file.file_path}/{rom_file.file_name}|{rom_file.last_modified}|{rom_file.file_size_bytes}|{target}".encode()
    ).hexdigest()[:CACHE_KEY_LENGTH]
    key_dir = Path(ROM_CONVERTO_CACHE_PATH) / f"{rom_id}-{key}"
    return key_dir / f"{Path(rom_file.file_name).stem}{TARGET_EXTENSIONS[target]}"


def _remove_dir_contents(key_dir: Path) -> None:
    for entry in key_dir.iterdir():
        with contextlib.suppress(OSError):
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()


def get_cached_converted(rom_id: int, rom_file: RomFile, target: str) -> Path | None:
    """Cache-hit-only lookup: return the converted file if present, else None."""
    final_path = converted_file_path(rom_id, rom_file, target)
    return final_path if final_path.exists() else None


async def get_or_convert(rom_id: int, rom_file: RomFile, target: str) -> Path | None:
    """Return the converted file's path, converting it on demand.

    Single-flight via a `.partial` sentinel; never raises and never blocks
    the HTTP request longer than one conversion. Returns None whenever the
    file cannot be served converted, so the caller serves the original.
    """
    final_path = converted_file_path(rom_id, rom_file, target)
    key_dir = final_path.parent
    sentinel = key_dir / SENTINEL_NAME

    try:
        if final_path.exists():
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

    try:
        produced = await rom_converto_service.convert(
            target,
            src=Path(LIBRARY_BASE_PATH) / rom_file.full_path,
            dest_dir=key_dir,
        )
        # The adapter derives its own output name from the source stem, so
        # reconcile whatever it produced onto the final path.
        if not produced.exists():
            extensions = tuple(TARGET_EXTENSIONS.values())
            outputs = [
                p
                for p in key_dir.iterdir()
                if p.is_file()
                and p.name.startswith(final_path.stem)
                and p.name.endswith(extensions)
                and not p.name.startswith(SENTINEL_NAME)
            ]
            if not outputs:
                raise FileNotFoundError("rom-converto produced no output")
            produced = outputs[0]
        try:
            os.replace(produced, final_path)
        except PermissionError:
            # Windows: a concurrent request may still stream the old final
            # file; if a final file is in place, serving it is success.
            if not final_path.exists():
                raise
    except Exception as e:
        _remove_dir_contents(key_dir)
        log.warning(
            f"Conversion failed for ROM {rom_id} (target {hl(target)}): {e}; serving original"
        )
        return None

    # The file can vanish (e.g. TTL cleanup) between the replace and here;
    # only return a path that actually exists right now.
    if not final_path.exists():
        return None

    with contextlib.suppress(OSError):
        sentinel.unlink()
    return final_path


def cleanup_stale_conversions() -> int:
    """Remove key dirs whose final file exceeded the configured TTL, and
    sentinel-only dirs whose last conversion attempt is older than 6 hours."""
    cache_root = Path(ROM_CONVERTO_CACHE_PATH)
    if not cache_root.exists():
        return 0

    ttl_seconds = cm.get_config().CONVERTTO.cache_ttl_hours * SECONDS_PER_HOUR
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
