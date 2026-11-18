"""Opaque per-user storage for the Cloud Sync categories no ROM owns: config/,
thumbnails/ and system/."""

import asyncio
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from config import ASSETS_BASE_PATH, MAX_SAVES_PER_SLOT
from utils.filesystem import TEMP_FILE_PREFIX, iter_files

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


def _copy_backup(source: Path, target: Path, overwrite: bool) -> bool | None:
    try:
        source_file = source.open("rb")
    except FileNotFoundError:
        return None

    with source_file:
        target.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            dir=target.parent, prefix=TEMP_FILE_PREFIX, delete=False
        ) as staged:
            temp_path = Path(staged.name)
            try:
                shutil.copyfileobj(source_file, staged)
                staged.close()
                try:
                    os.link(temp_path, target)
                    replaced = False
                except FileExistsError:
                    if not overwrite:
                        raise
                    os.replace(temp_path, target)
                    replaced = True
                older = sorted(
                    (
                        file
                        for file in target.parent.iterdir()
                        if file != target
                        and re.fullmatch(r"[0-9]{6}-[0-9]{6}", file.name)
                    ),
                    key=lambda file: file.name,
                    reverse=True,
                )
                for file in older[max(1, MAX_SAVES_PER_SLOT) - 1 :]:
                    file.unlink(missing_ok=True)
                return replaced
            finally:
                temp_path.unlink(missing_ok=True)


class FSRetroArchSyncHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=ASSETS_BASE_PATH)

    async def copy_backup(
        self, source: Path, destination: str, *, overwrite: bool
    ) -> bool | None:
        """Return whether the backup was replaced, or None if the source is missing."""
        target = self.validate_path(destination)
        lock = await self._get_file_lock(str(target.parent))
        async with lock:
            return await asyncio.to_thread(_copy_backup, source, target, overwrite)

    async def list_blob_files(self, prefix: str) -> list[BlobFile]:
        """Every file under `prefix` (relative to the blob root), relative to `prefix` itself."""
        try:
            root = self.validate_path(prefix)
        except ValueError:
            return []

        return await asyncio.to_thread(_walk_files, root)
