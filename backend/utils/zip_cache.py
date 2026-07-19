from __future__ import annotations

import dataclasses
import functools
import hashlib
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from config import LIBRARY_BASE_PATH, ZIP_CACHE_PATH
from logger.formatter import highlight as hl
from logger.logger import log

if TYPE_CHECKING:
    from models.rom import RomFile

CACHE_KEY_LENGTH = 16
SECONDS_PER_HOUR = 3600
LARGE_ZIP_THRESHOLD_BYTES = 8 * 1024 * 1024 * 1024  # 8 GB
DEFAULT_TTL_HOURS = 48
LARGE_ZIP_TTL_HOURS = 12
BULK_CACHE_MAX_ROMS = 100
BULK_NAMESPACE_PREFIX = "bulk"


@dataclasses.dataclass(frozen=True)
class ZipFileEntry:
    """Thread-safe snapshot of a RomFile's download-relevant data."""

    download_name: str
    full_path: str
    file_size_bytes: int
    updated_at_epoch: float

    @classmethod
    def from_rom_file(cls, file: RomFile, hidden_folder: bool) -> ZipFileEntry:
        return cls(
            download_name=file.file_name_for_download(hidden_folder),
            full_path=file.full_path,
            file_size_bytes=file.file_size_bytes,
            updated_at_epoch=file.updated_at.timestamp(),
        )


def get_cache_key(
    namespace: str,
    entries: list[ZipFileEntry],
    hidden_folder: bool = False,
) -> str:
    """Deterministic cache key derived from content state."""
    parts = [
        namespace,
        str(hidden_folder),
        str(max((e.updated_at_epoch for e in entries), default=0.0)),
    ]
    for e in sorted(entries, key=lambda x: x.download_name):
        parts.append(f"{e.download_name}:{e.file_size_bytes}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:CACHE_KEY_LENGTH]


def get_bulk_namespace(rom_ids: list[int]) -> str:
    """Deterministic namespace for bulk downloads, hashed to avoid ENAMETOOLONG."""
    id_str = "-".join(str(i) for i in sorted(rom_ids))
    id_hash = hashlib.sha256(id_str.encode()).hexdigest()[:CACHE_KEY_LENGTH]
    return f"{BULK_NAMESPACE_PREFIX}-{id_hash}"


def _cache_dir(namespace: str) -> Path:
    return Path(ZIP_CACHE_PATH) / namespace


def _cache_file(namespace: str, cache_key: str) -> Path:
    return _cache_dir(namespace) / f"{cache_key}.zip"


def get_cached_zip(namespace: str, cache_key: str) -> Path | None:
    """Return the cached ZIP path if it exists on disk, else None."""
    path = _cache_file(namespace, cache_key)
    return path if path.exists() else None


def _ensure_zipfile_writable() -> None:
    """Restore ``zipfile._get_compressor`` to a writable signature.

    ``zipfile_inflate64`` (imported in ``handler/filesystem/roms_handler.py``
    to support Enhanced Deflate) replaces ``zipfile._get_compressor`` with a
    wrapper that only accepts ``compress_type``. CPython 3.13 calls it with
    ``(compress_type, compresslevel)``, so ``ZipFile.write()``/``writestr()``
    raise ``TypeError``. Wrap it once with a signature-compatible shim that
    drops the extra arg, matching inflate64's own behavior (it already ignores
    ``compresslevel``). Idempotent and safe to call from any thread.
    """
    current = zipfile._get_compressor  # type: ignore[attr-defined]
    if getattr(current, "_romm_compresslevel_safe", False):
        return

    # Probe with two args: the stdlib accepts them, inflate64's wrapper does not.
    try:
        current(zipfile.ZIP_STORED, None)
        return
    except TypeError:
        pass

    @functools.wraps(current)
    def _get_compressor(compress_type, compresslevel=None):
        return current(compress_type)

    _get_compressor._romm_compresslevel_safe = True  # type: ignore[attr-defined]
    zipfile._get_compressor = _get_compressor  # type: ignore[attr-defined,assignment]


def build_cached_zip(
    namespace: str,
    entries: list[ZipFileEntry],
    m3u_content: bytes | None,
    m3u_filename: str | None,
    cache_key: str,
) -> Path:
    """Build a ZIP_STORED archive on disk and return its path.

    Writes to a temp file in the same directory, then atomically renames to
    the final path to prevent serving partial files.
    """
    target = _cache_file(namespace, cache_key)
    if target.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        os.close(fd)
        _ensure_zipfile_writable()
        with zipfile.ZipFile(tmp_path, "w") as zf:
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


async def resolve_cached_zip(
    namespace: str,
    entries: list[ZipFileEntry],
    *,
    hidden_folder: bool = False,
    m3u_content: bytes | None = None,
    m3u_filename: str | None = None,
    log_label: str,
) -> Path | None:
    """Return the nginx redirect path for a cached ZIP, building it on demand.

    Returns ``None`` when there is nothing to cache or the build fails, letting
    the caller fall back to mod_zip streaming. A full disk simply surfaces as a
    build failure here, so no separate space check is needed.
    """
    if not entries:
        return None

    cache_key = get_cache_key(namespace, entries, hidden_folder)
    if get_cached_zip(namespace, cache_key):
        return get_zip_redirect_path(namespace, cache_key)

    try:
        await anyio.to_thread.run_sync(
            functools.partial(
                build_cached_zip,
                namespace=namespace,
                entries=entries,
                m3u_content=m3u_content,
                m3u_filename=m3u_filename,
                cache_key=cache_key,
            )
        )
    except Exception as e:
        log.warning(
            f"Failed to build cached ZIP for {log_label}, falling back to streaming: {e}"
        )
        return None

    return get_zip_redirect_path(namespace, cache_key)


def get_ttl_hours(size_bytes: int) -> int:
    """Return the appropriate TTL based on ZIP size."""
    if size_bytes > LARGE_ZIP_THRESHOLD_BYTES:
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
    deleted = 0

    for ns_dir in cache_root.iterdir():
        if not ns_dir.is_dir():
            continue
        for zip_file in ns_dir.glob("*.zip"):
            stat = zip_file.stat()
            cutoff = now - (get_ttl_hours(stat.st_size) * SECONDS_PER_HOUR)
            if stat.st_mtime < cutoff:
                zip_file.unlink()
                deleted += 1
        if ns_dir.exists() and not any(ns_dir.iterdir()):
            ns_dir.rmdir()

    return deleted
