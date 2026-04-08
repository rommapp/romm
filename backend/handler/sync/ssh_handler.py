"""SSH/SFTP handler for Push-Pull sync mode.

Provides methods to connect to remote devices via SSH, list remote save files,
and perform bidirectional file transfers using SFTP.

SSH keys are expected to be pre-mounted on the server (e.g. via Docker volume)
at the path configured by SYNC_SSH_KEYS_PATH. Keys are looked up by device_id
({SYNC_SSH_KEYS_PATH}/{device_id}.pem) or via an explicit ssh_key_path in the
device's sync_config.
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
from anyio import Path as AnyioPath
from anyio import open_file

from config import SYNC_SSH_KEYS_PATH, SYNC_SSH_KNOWN_HOSTS_PATH
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
    """Handles SSH/SFTP operations for push-pull sync mode.

    SSH keys are expected to be pre-mounted on the server filesystem at
    SYNC_SSH_KEYS_PATH. The handler looks up keys by device_id convention
    ({keys_path}/{device_id}.pem) or uses an explicit path from sync_config.
    """

    def __init__(self) -> None:
        self.keys_path = Path(SYNC_SSH_KEYS_PATH)
        self.keys_path.mkdir(parents=True, exist_ok=True)

    def _resolve_key_path(self, device_id: str, sync_config: dict) -> str | None:
        """Resolve the SSH key path for a device.

        Checks, in order:
        1. Explicit ssh_key_path in sync_config
        2. Convention-based path: {SYNC_SSH_KEYS_PATH}/{device_id}.pem
        """
        explicit = sync_config.get("ssh_key_path")
        if explicit and os.path.isfile(explicit):
            return explicit

        convention_path = self.keys_path / f"{device_id}.pem"
        if convention_path.is_file():
            return str(convention_path)

        return None

    async def connect(
        self, sync_config: dict, device_id: str | None = None
    ) -> asyncssh.SSHClientConnection:
        """Establish an SSH connection using device sync_config.

        SSH keys should be pre-mounted on the server. The handler resolves
        the key by checking sync_config.ssh_key_path first, then falls back
        to the convention-based path {SYNC_SSH_KEYS_PATH}/{device_id}.pem.

        sync_config should contain:
            - ssh_host: hostname or IP
            - ssh_port: port (default 22)
            - ssh_username: username
            - ssh_key_path: explicit path to private key (optional)
            - ssh_password: password (optional, fallback if no key found)
        """
        host = sync_config["ssh_host"]
        port = sync_config.get("ssh_port", 22)
        username = sync_config.get("ssh_username", "root")

        if not AnyioPath(SYNC_SSH_KNOWN_HOSTS_PATH).is_file():
            raise FileNotFoundError(
                f"SSH known_hosts file not found at {SYNC_SSH_KNOWN_HOSTS_PATH}. "
                "Mount a known_hosts file or set SYNC_SSH_KNOWN_HOSTS_PATH."
            )

        connect_kwargs: dict[str, Any] = {
            "host": host,
            "port": port,
            "username": username,
            "known_hosts": SYNC_SSH_KNOWN_HOSTS_PATH,
        }

        # Resolve key path (explicit or convention-based)
        key_path = self._resolve_key_path(device_id or "", sync_config)
        if key_path:
            connect_kwargs["client_keys"] = [key_path]
        elif sync_config.get("ssh_password"):
            connect_kwargs["password"] = sync_config["ssh_password"]
        else:
            raise ValueError(
                f"No SSH authentication method available for {host}. "
                f"Mount a key at {self.keys_path}/{{device_id}}.pem or "
                "provide ssh_key_path/ssh_password in sync_config."
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
        async with await open_file(local_path, "rb") as f:
            while chunk := await f.read(8192):
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
            remote_dir = str(Path(remote_path).parent)
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
