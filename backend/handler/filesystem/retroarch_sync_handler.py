"""Opaque per-user storage for the Cloud Sync categories no ROM owns: config/,
thumbnails/ and system/."""

import asyncio
import stat
from dataclasses import dataclass
from pathlib import Path

from config import SYNC_RETROARCH_BASE_PATH
from utils.filesystem import iter_files

from .base_handler import FSHandler


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


class FSRetroArchSyncHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=SYNC_RETROARCH_BASE_PATH)

    async def list_blob_files(self, prefix: str) -> list[BlobFile]:
        """Every file under `prefix` (relative to the blob root), relative to `prefix` itself."""
        try:
            root = self.validate_path(prefix)
        except ValueError:
            return []

        return await asyncio.to_thread(_walk_files, root)
