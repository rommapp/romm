"""Opaque per-user storage for the Cloud Sync categories no ROM owns: config/,
thumbnails/ and system/."""

from config import SYNC_RETROARCH_BASE_PATH

from .base_handler import FSHandler


class FSRetroArchSyncHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=SYNC_RETROARCH_BASE_PATH)

    async def list_blob_paths(self, prefix: str) -> list[str]:
        """Posix paths of every file under `prefix` (relative to the blob root),
        relative to `prefix` itself."""
        try:
            root = self.validate_path(prefix)
        except ValueError:
            return []

        if not root.is_dir():
            return []

        return [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
