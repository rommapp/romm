"""Opaque per-user storage for the Cloud Sync categories no ROM owns: config/,
thumbnails/ and system/."""

import asyncio
import fcntl
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from config import ASSETS_BASE_PATH
from utils.filesystem import TEMP_FILE_PREFIX, iter_files, link_or_copy_file

from .base_handler import FSHandler

_BACKUP_LOCK_NAME = ".romm_backup.lock"


@dataclass(frozen=True)
class BlobFile:
    """A file under a blob prefix, with the stat fields its hash cache key uses."""

    relative_path: str
    size: int
    mtime: float


def _walk_files(root: Path) -> list[BlobFile]:
    """Every file under `root`, without descending into symlinked directories."""
    files: list[BlobFile] = []
    for directory, name in iter_files(str(root), recursive=True):
        # A write interrupted by a crash leaves its temp file behind.
        if name.startswith(TEMP_FILE_PREFIX):
            continue
        path = directory / name
        try:
            file_stat = path.stat()
        except OSError:
            continue
        if stat.S_ISREG(file_stat.st_mode):
            files.append(
                BlobFile(
                    path.relative_to(root).as_posix(),
                    file_stat.st_size,
                    file_stat.st_mtime,
                )
            )

    return files


@contextmanager
def _folder_lock(folder: Path) -> Iterator[None]:
    """Hold an exclusive lock on `folder` across threads and worker processes."""
    # A regular file: NFS grants an exclusive flock() only on a file open for writing.
    fd = os.open(folder / _BACKUP_LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _publish_backup(
    source: Path, target: Path, overwrite: bool, keep: int
) -> bool | None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with _folder_lock(target.parent):
        replaced = target.exists()
        if replaced and not overwrite:
            raise FileExistsError(target)
        # Assets are only ever replaced whole, so a hardlink keeps the old bytes.
        try:
            link_or_copy_file(source, target)
        except FileNotFoundError:
            return None
        if keep:
            older = sorted(
                (
                    file
                    for file in target.parent.iterdir()
                    if file != target and not file.name.startswith(".")
                ),
                key=lambda file: (file.stat().st_mtime_ns, file.name),
                reverse=True,
            )
            for file in older[keep - 1 :]:
                file.unlink(missing_ok=True)
    return replaced


class FSRetroArchSyncHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=ASSETS_BASE_PATH)

    async def publish_backup(
        self, source: Path, destination: str, *, overwrite: bool, keep: int
    ) -> bool | None:
        """Link or copy `source` to `destination`, keeping the `keep` newest siblings.

        Returns:
            Whether an existing backup was replaced, or None if `source` is gone.
        """
        target = self.validate_path(destination)
        # Spares the thread pool from threads blocked on the folder lock.
        lock = await self._get_file_lock(str(target.parent))
        async with lock:
            return await asyncio.to_thread(
                _publish_backup, source, target, overwrite, keep
            )

    async def list_blob_files(self, prefix: str) -> list[BlobFile]:
        """Every file under `prefix` (relative to the blob root), relative to `prefix` itself."""
        try:
            root = self.validate_path(prefix)
        except ValueError:
            return []

        return await asyncio.to_thread(_walk_files, root)
