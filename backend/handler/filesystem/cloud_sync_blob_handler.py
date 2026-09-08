"""Local disk storage for the RetroArch Cloud Sync categories RomM has no
concept of at all: config/, thumbnails/, system/. These are unrelated to any
ROM in the library — the client just wants an opaque per-user bucket to keep
its own files in sync across devices — so they're stored as plain files,
namespaced by user, rather than going through the asset/ROM machinery.
"""

import hashlib

from config import CLOUD_SYNC_BLOB_BASE_PATH

from .base_handler import FSHandler


class FSCloudSyncBlobHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=CLOUD_SYNC_BLOB_BASE_PATH)

    async def compute_file_md5(self, file_path: str) -> str | None:
        """MD5 of the bytes on disk, `None` if the file can't be read."""
        try:
            hash_obj = hashlib.md5(usedforsecurity=False)
            async with await self.stream_file(file_path=file_path) as f:
                while chunk := await f.read(8192):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except OSError:
            return None

    async def list_blob_paths(self, prefix: str) -> list[str]:
        """Posix paths of every file under `prefix`, relative to `prefix`
        itself. `prefix` is itself relative to the blob root (e.g.
        `users/<folder>/thumbnails`); the caller re-attaches whatever prefix
        the manifest or on-disk path needs.
        """
        try:
            root = self.validate_path(prefix)
        except ValueError:
            return []

        if not root.is_dir():
            return []

        return [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
