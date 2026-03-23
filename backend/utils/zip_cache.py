from __future__ import annotations

import dataclasses
import hashlib
import os
import tempfile
import time
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from config import LIBRARY_BASE_PATH, ZIP_CACHE_PATH
from logger.formatter import highlight as hl
from logger.logger import log

CACHE_KEY_LENGTH = 16
DISK_SPACE_MULTIPLIER = 2
SECONDS_PER_HOUR = 3600
LARGE_ZIP_THRESHOLD_BYTES = 8 * 1024 * 1024 * 1024  # 8 GB
DEFAULT_TTL_HOURS = 48
LARGE_ZIP_TTL_HOURS = 12
BULK_CACHE_MAX_ROMS = 100
MIN_EVICT_AGE_HOURS = 1


@dataclasses.dataclass(frozen=True)
class ZipFileEntry:
    """Thread-safe snapshot of a RomFile's download-relevant data."""

    download_name: str
    full_path: str
    file_size_bytes: int
    updated_at_epoch: float


def get_cache_key(
    namespace: str,
    entries: list[ZipFileEntry],
    hidden_folder: bool = False,
) -> str:
    """Deterministic cache key derived from content state."""
    parts = [
        namespace,
        str(hidden_folder),
        str(max(e.updated_at_epoch for e in entries)),
    ]
    for e in sorted(entries, key=lambda x: x.download_name):
        parts.append(f"{e.download_name}:{e.file_size_bytes}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:CACHE_KEY_LENGTH]


def _cache_dir(namespace: str) -> Path:
    return Path(ZIP_CACHE_PATH) / namespace


def _cache_file(namespace: str, cache_key: str) -> Path:
    return _cache_dir(namespace) / f"{cache_key}.zip"


def get_cached_zip(namespace: str, cache_key: str) -> Path | None:
    """Return the cached ZIP path if it exists on disk, else None."""
    path = _cache_file(namespace, cache_key)
    return path if path.exists() else None


def _get_available_space() -> int:
    cache_root = Path(ZIP_CACHE_PATH)
    cache_root.mkdir(parents=True, exist_ok=True)
    stat = os.statvfs(cache_root)
    return stat.f_bavail * stat.f_frsize


def _get_all_cached_zips() -> list[Path]:
    """Return all cached ZIP files sorted by mtime ascending (oldest first)."""
    cache_root = Path(ZIP_CACHE_PATH)
    if not cache_root.exists():
        return []
    zips = []
    for ns_dir in cache_root.iterdir():
        if not ns_dir.is_dir():
            continue
        for zip_file in ns_dir.glob("*.zip"):
            zips.append(zip_file)
    zips.sort(key=lambda p: p.stat().st_mtime)
    return zips


def ensure_space_for_cache(entries: list[ZipFileEntry]) -> bool:
    """Check available disk space, evicting oldest cached ZIPs if needed.

    Requires DISK_SPACE_MULTIPLIER times the estimated ZIP size. Evicts
    cached entries older than MIN_EVICT_AGE_HOURS until enough space is
    available or no more evictable entries remain.
    """
    estimated_size = sum(e.file_size_bytes for e in entries)
    required = estimated_size * DISK_SPACE_MULTIPLIER

    if _get_available_space() > required:
        return True

    evict_cutoff = time.time() - (MIN_EVICT_AGE_HOURS * SECONDS_PER_HOUR)
    for zip_file in _get_all_cached_zips():
        if zip_file.stat().st_mtime > evict_cutoff:
            continue
        freed = zip_file.stat().st_size
        zip_file.unlink()
        parent = zip_file.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
        log.debug(f"Evicted cached ZIP {hl(zip_file.name)} ({freed} bytes)")
        if _get_available_space() > required:
            return True

    return _get_available_space() > required


def build_cached_zip(
    namespace: str,
    entries: list[ZipFileEntry],
    m3u_content: bytes | None,
    m3u_filename: str | None,
    cache_key: str,
) -> Path:
    """Build a ZIP_STORED archive on disk and return its path.

    Writes to a temp file in the same directory, then atomically renames to
    the final path to prevent serving partial files. Uses ZipFile.write()
    to stream file content without loading entire files into memory.
    """
    target = _cache_file(namespace, cache_key)
    if target.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        os.close(fd)
        with ZipFile(tmp_path, "w", compression=ZIP_STORED) as zf:
            for entry in entries:
                src = Path(LIBRARY_BASE_PATH) / entry.full_path
                zf.write(src, arcname=entry.download_name)

            if m3u_content is not None and m3u_filename is not None:
                zf.writestr(m3u_filename, m3u_content)

        os.rename(tmp_path, target)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    log.info(f"Built cached ZIP in {hl(namespace)}: {hl(target.name)}")
    return target


def get_zip_redirect_path(namespace: str, cache_key: str) -> Path:
    """Return the nginx-internal URL path for the cached ZIP."""
    return Path(f"/cache/zips/{namespace}/{cache_key}.zip")


def get_ttl_hours(entries: list[ZipFileEntry]) -> int:
    """Return the appropriate TTL based on estimated ZIP size."""
    estimated_size = sum(e.file_size_bytes for e in entries)
    if estimated_size > LARGE_ZIP_THRESHOLD_BYTES:
        return LARGE_ZIP_TTL_HOURS
    return DEFAULT_TTL_HOURS


def cleanup_stale_zips() -> int:
    """Remove cached ZIPs that have exceeded their TTL.

    Files larger than LARGE_ZIP_THRESHOLD_BYTES use LARGE_ZIP_TTL_HOURS,
    all others use DEFAULT_TTL_HOURS.
    """
    cache_root = Path(ZIP_CACHE_PATH)
    if not cache_root.exists():
        return 0

    now = time.time()
    default_cutoff = now - (DEFAULT_TTL_HOURS * SECONDS_PER_HOUR)
    large_cutoff = now - (LARGE_ZIP_TTL_HOURS * SECONDS_PER_HOUR)
    deleted = 0

    for ns_dir in cache_root.iterdir():
        if not ns_dir.is_dir():
            continue
        for zip_file in ns_dir.glob("*.zip"):
            stat = zip_file.stat()
            cutoff = (
                large_cutoff
                if stat.st_size > LARGE_ZIP_THRESHOLD_BYTES
                else default_cutoff
            )
            if stat.st_mtime < cutoff:
                zip_file.unlink()
                deleted += 1
        if ns_dir.exists() and not any(ns_dir.iterdir()):
            ns_dir.rmdir()

    return deleted
