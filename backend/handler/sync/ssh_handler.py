"""SSH/SFTP handler for Push-Pull sync mode.

Provides methods to connect to remote devices via SSH, list remote save files,
and perform bidirectional file transfers using SFTP.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncssh

from config import SYNC_SSH_KEYS_PATH
from logger.logger import log


@dataclass
class RemoteSaveInfo:
    """Information about a save file on a remote device."""

    path: str
    file_name: str
    platform_slug: str
    file_size: int
    mtime: datetime
    content_hash: str | None = None


class SSHSyncHandler:
    """Handles SSH/SFTP operations for push-pull sync mode."""

    def __init__(self) -> None:
        self.keys_path = Path(SYNC_SSH_KEYS_PATH)
        self.keys_path.mkdir(parents=True, exist_ok=True)

    def get_key_path(self, device_id: str) -> Path:
        """Get the SSH key path for a device."""
        return self.keys_path / f"{device_id}.pem"

    def has_key(self, device_id: str) -> bool:
        """Check if an SSH key exists for a device."""
        return self.get_key_path(device_id).is_file()

    def store_key(self, device_id: str, key_data: bytes) -> Path:
        """Store an SSH private key for a device."""
        key_path = self.get_key_path(device_id)
        key_path.write_bytes(key_data)
        key_path.chmod(0o600)
        log.info(f"Stored SSH key for device {device_id}")
        return key_path

    def remove_key(self, device_id: str) -> bool:
        """Remove an SSH private key for a device."""
        key_path = self.get_key_path(device_id)
        if key_path.is_file():
            key_path.unlink()
            log.info(f"Removed SSH key for device {device_id}")
            return True
        return False

    async def connect(self, sync_config: dict) -> asyncssh.SSHClientConnection:
        """Establish an SSH connection using device sync_config.

        sync_config should contain:
            - ssh_host: hostname or IP
            - ssh_port: port (default 22)
            - ssh_username: username
            - ssh_key_path: path to private key (or device_id to look up)
            - ssh_password: password (optional, alternative to key)
        """
        host = sync_config["ssh_host"]
        port = sync_config.get("ssh_port", 22)
        username = sync_config.get("ssh_username", "root")

        connect_kwargs: dict[str, Any] = {
            "host": host,
            "port": port,
            "username": username,
            "known_hosts": None,  # Accept all host keys (TODO: make configurable)
        }

        # Try key-based auth first
        key_path = sync_config.get("ssh_key_path")
        if key_path and os.path.isfile(key_path):
            connect_kwargs["client_keys"] = [key_path]
        elif sync_config.get("ssh_password"):
            connect_kwargs["password"] = sync_config["ssh_password"]
        else:
            raise ValueError(
                f"No SSH authentication method available for {host}. "
                "Provide ssh_key_path or ssh_password in sync_config."
            )

        log.info(f"Connecting to {username}@{host}:{port}")
        return await asyncssh.connect(**connect_kwargs)

    async def list_remote_saves(
        self,
        conn: asyncssh.SSHClientConnection,
        save_directories: list[dict],
    ) -> list[RemoteSaveInfo]:
        """List save files on a remote device.

        save_directories is a list of dicts with keys:
            - platform_slug: str
            - path: str (remote directory path)
            - extension: str (optional, file extension filter, e.g. ".srm")
        """
        results: list[RemoteSaveInfo] = []

        async with conn.start_sftp_client() as sftp:
            for dir_config in save_directories:
                platform_slug = dir_config["platform_slug"]
                remote_path = dir_config["path"]
                extension = dir_config.get("extension", "")

                try:
                    entries = await sftp.listdir(remote_path)
                except asyncssh.SFTPNoSuchFile:
                    log.warning(f"Remote directory not found: {remote_path}")
                    continue

                for entry in entries:
                    if extension and not entry.endswith(extension):
                        continue

                    full_remote_path = f"{remote_path}/{entry}"
                    try:
                        attrs = await sftp.stat(full_remote_path)
                        if not attrs.type == asyncssh.constants.FILEXFER_TYPE_REGULAR:
                            continue

                        mtime = datetime.fromtimestamp(
                            attrs.mtime or 0, tz=timezone.utc
                        )
                        results.append(
                            RemoteSaveInfo(
                                path=full_remote_path,
                                file_name=entry,
                                platform_slug=platform_slug,
                                file_size=attrs.size or 0,
                                mtime=mtime,
                            )
                        )
                    except asyncssh.SFTPError as e:
                        log.warning(f"Failed to stat {full_remote_path}: {e}")

        return results

    async def download_save(
        self,
        conn: asyncssh.SSHClientConnection,
        remote_path: str,
        local_path: str | None = None,
    ) -> tuple[str, str]:
        """Download a save file from a remote device.

        Returns (local_temp_path, content_hash).
        """
        if local_path is None:
            fd, local_path = tempfile.mkstemp(prefix="romm_sync_")
            os.close(fd)

        async with conn.start_sftp_client() as sftp:
            await sftp.get(remote_path, local_path)

        # Compute hash
        hash_obj = hashlib.md5(usedforsecurity=False)
        with open(local_path, "rb") as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)

        return local_path, hash_obj.hexdigest()

    async def upload_save(
        self,
        conn: asyncssh.SSHClientConnection,
        local_path: str,
        remote_path: str,
    ) -> None:
        """Upload a save file to a remote device."""
        async with conn.start_sftp_client() as sftp:
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            try:
                await sftp.mkdir(remote_dir)
            except asyncssh.SFTPError:
                pass  # Directory likely already exists

            await sftp.put(local_path, remote_path)
            log.info(f"Uploaded {local_path} -> {remote_path}")

    async def delete_remote_save(
        self,
        conn: asyncssh.SSHClientConnection,
        remote_path: str,
    ) -> None:
        """Delete a save file from a remote device."""
        async with conn.start_sftp_client() as sftp:
            await sftp.remove(remote_path)
            log.info(f"Deleted remote file: {remote_path}")


ssh_sync_handler = SSHSyncHandler()
