import hashlib
import os
from pathlib import Path

from config import SYNC_BASE_PATH
from logger.logger import log

from .base_handler import FSHandler


class FSSyncHandler(FSHandler):
    """Filesystem handler for sync folder operations (File Transfer mode)."""

    def __init__(self) -> None:
        super().__init__(base_path=SYNC_BASE_PATH)

    def build_incoming_path(
        self, device_id: str, platform_slug: str | None = None
    ) -> str:
        parts = [device_id, "incoming"]
        if platform_slug:
            parts.append(platform_slug)
        return os.path.join(*parts)

    def build_outgoing_path(
        self, device_id: str, platform_slug: str | None = None
    ) -> str:
        parts = [device_id, "outgoing"]
        if platform_slug:
            parts.append(platform_slug)
        return os.path.join(*parts)

    def build_conflicts_path(
        self, device_id: str, platform_slug: str | None = None
    ) -> str:
        parts = [device_id, "conflicts"]
        if platform_slug:
            parts.append(platform_slug)
        return os.path.join(*parts)

    def ensure_device_directories(self, device_id: str) -> None:
        incoming = self.base_path / self.build_incoming_path(device_id)
        outgoing = self.base_path / self.build_outgoing_path(device_id)

        incoming.mkdir(parents=True, exist_ok=True)
        outgoing.mkdir(parents=True, exist_ok=True)

        log.info(f"Ensured sync directories for device {device_id}")

    def list_incoming_files(self, device_id: str) -> list[dict]:
        """List all files in a device's incoming directory.

        Returns list of dicts with keys: platform_slug, file_name, full_path, file_size, mtime
        """
        incoming_dir = self.base_path / self.build_incoming_path(device_id)
        if not incoming_dir.exists():
            return []

        results = []
        for platform_dir in incoming_dir.iterdir():
            if not platform_dir.is_dir():
                continue
            platform_slug = platform_dir.name
            for file_path in platform_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                stat = file_path.stat()
                results.append(
                    {
                        "platform_slug": platform_slug,
                        "file_name": file_path.name,
                        "full_path": str(file_path),
                        "relative_path": str(file_path.relative_to(incoming_dir)),
                        "file_size": stat.st_size,
                        "mtime": stat.st_mtime,
                    }
                )

        return results

    def compute_file_hash(self, file_path: str) -> str:
        """Compute MD5 hash of a file synchronously (for watcher context)."""
        hash_obj = hashlib.md5(usedforsecurity=False)
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    def write_outgoing_file(
        self, device_id: str, platform_slug: str, file_name: str, data: bytes
    ) -> str:
        """Write a file to a device's outgoing directory."""
        outgoing_dir = self.base_path / self.build_outgoing_path(
            device_id, platform_slug
        )
        outgoing_dir.mkdir(parents=True, exist_ok=True)
        file_path = outgoing_dir / file_name
        file_path.write_bytes(data)
        return str(file_path)

    def remove_incoming_file(self, full_path: str) -> None:
        """Remove a processed file from the incoming directory."""
        path = Path(full_path)
        if path.exists() and path.is_file():
            # Validate the file is within our base path
            try:
                path.resolve().relative_to(self.base_path.resolve())
            except ValueError as e:
                raise ValueError(
                    f"Path {full_path} is outside the sync base directory"
                ) from e
            path.unlink()
