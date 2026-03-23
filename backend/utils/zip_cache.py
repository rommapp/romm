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


@dataclasses.dataclass(frozen=True)
class ZipFileEntry:
    """Thread-safe snapshot of a RomFile's download-relevant data."""

    download_name: str
    full_path: str
    file_size_bytes: int
    updated_at_epoch: float


def get_cache_key(
    rom_id: int,
    entries: list[ZipFileEntry],
    hidden_folder: bool,
) -> str:
    """Deterministic cache key derived from ROM state."""
    parts = [
        str(rom_id),
        str(hidden_folder),
        str(max(e.updated_at_epoch for e in entries)),
    ]
    for e in sorted(entries, key=lambda x: x.download_name):
        parts.append(f"{e.download_name}:{e.file_size_bytes}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:CACHE_KEY_LENGTH]


def _cache_dir(rom_id: int) -> Path:
    return Path(ZIP_CACHE_PATH) / str(rom_id)


def _cache_file(rom_id: int, cache_key: str) -> Path:
    return _cache_dir(rom_id) / f"{cache_key}.zip"


def get_cached_zip(rom_id: int, cache_key: str) -> Path | None:
    """Return the cached ZIP path if it exists on disk, else None."""
    path = _cache_file(rom_id, cache_key)
    return path if path.exists() else None


def has_space_for_cache(entries: list[ZipFileEntry]) -> bool:
    """Check if available disk space exceeds the estimated ZIP size
    multiplied by DISK_SPACE_MULTIPLIER."""
    estimated_size = sum(e.file_size_bytes for e in entries)
    cache_root = Path(ZIP_CACHE_PATH)
    cache_root.mkdir(parents=True, exist_ok=True)
    stat = os.statvfs(cache_root)
    available = stat.f_bavail * stat.f_frsize
    return available > estimated_size * DISK_SPACE_MULTIPLIER


def build_cached_zip(
    rom_id: int,
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
    target = _cache_file(rom_id, cache_key)
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

    log.info(f"Built cached ZIP for ROM {hl(str(rom_id))}: {hl(target.name)}")
    return target


def get_zip_redirect_path(rom_id: int, cache_key: str) -> Path:
    """Return the nginx-internal URL path for the cached ZIP."""
    return Path(f"/cache/zips/{rom_id}/{cache_key}.zip")


def cleanup_stale_zips(max_age_hours: int = 48) -> int:
    """Remove cached ZIPs older than max_age_hours. Returns count deleted."""
    cache_root = Path(ZIP_CACHE_PATH)
    if not cache_root.exists():
        return 0

    cutoff = time.time() - (max_age_hours * SECONDS_PER_HOUR)
    deleted = 0

    for rom_dir in cache_root.iterdir():
        if not rom_dir.is_dir():
            continue
        for zip_file in rom_dir.glob("*.zip"):
            if zip_file.stat().st_mtime < cutoff:
                zip_file.unlink()
                deleted += 1
        if rom_dir.exists() and not any(rom_dir.iterdir()):
            rom_dir.rmdir()

    return deleted
