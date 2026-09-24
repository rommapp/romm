"""Opaque per-user storage for the Cloud Sync categories no ROM owns: config/,
thumbnails/ and system/."""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from config import SYNC_RETROARCH_BASE_PATH

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
    pending = [""]
    while pending:
        relative_dir = pending.pop()
        try:
            with os.scandir(root / relative_dir) as entries:
                for entry in entries:
                    relative = (
                        f"{relative_dir}/{entry.name}" if relative_dir else entry.name
                    )
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(relative)
                        elif entry.is_file():
                            stat = entry.stat()
                            files.append(
                                BlobFile(relative, stat.st_size, stat.st_mtime)
                            )
                    except OSError:
                        continue
        except OSError:
            continue

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
