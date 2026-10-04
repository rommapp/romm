import hashlib
import shutil
import zipfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncssh
import pytest
from anyio import Path as AnyioPath
from tests._zipfile_shim import reload_zipfile

from handler.filesystem.assets_handler import hash_save_file
from handler.sync import ssh_handler
from handler.sync.ssh_handler import SSHSyncHandler, get_ssh_sync_handler


class _FakeSFTP:
    def __init__(self, source: Path):
        self._source = source

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, remote_path: str, local_path: str) -> None:
        shutil.copyfile(self._source, local_path)


class TestDownloadSave:
    @pytest.fixture
    def remote_zip(self, tmp_path: Path) -> Path:
        path = tmp_path / "remote.zip"
        reload_zipfile()
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("card/save.bin", b"identical save contents" * 64)
        return path

    @pytest.mark.asyncio
    async def test_a_zipped_save_is_hashed_like_the_server_save(
        self, tmp_path: Path, remote_zip: Path
    ):
        remote_bytes = await AnyioPath(remote_zip).read_bytes()
        conn = MagicMock()
        conn.start_sftp_client.return_value = _FakeSFTP(remote_zip)

        handler = SSHSyncHandler.__new__(SSHSyncHandler)
        local_path, content_hash = await handler.download_save(
            conn, "/saves/remote.zip", str(tmp_path / "local.zip")
        )

        assert await AnyioPath(local_path).read_bytes() == remote_bytes
        assert content_hash == hash_save_file(remote_zip)
        assert (
            content_hash != hashlib.md5(remote_bytes, usedforsecurity=False).hexdigest()
        )


@pytest.fixture
def keys_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "keys"
    monkeypatch.setattr(ssh_handler, "SYNC_SSH_KEYS_PATH", str(path))
    return path


@pytest.fixture
def known_hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "known_hosts"
    path.write_text("deck.local ssh-ed25519 AAAA\n")
    monkeypatch.setattr(ssh_handler, "SYNC_SSH_KNOWN_HOSTS_PATH", str(path))
    return path


@pytest.fixture
def handler(keys_dir: Path) -> SSHSyncHandler:
    return SSHSyncHandler()


@pytest.fixture
def ssh_connect(mocker):
    return mocker.patch.object(asyncssh, "connect", AsyncMock(return_value=MagicMock()))


def _connect_kwargs(ssh_connect: AsyncMock) -> Mapping[str, Any]:
    call = ssh_connect.await_args
    assert call is not None
    return call.kwargs


class TestInit:
    def test_creates_the_keys_directory(self, keys_dir: Path):
        SSHSyncHandler()

        assert keys_dir.is_dir()

    def test_an_unwritable_keys_directory_is_a_clear_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("")
        monkeypatch.setattr(ssh_handler, "SYNC_SSH_KEYS_PATH", str(blocker / "keys"))

        with pytest.raises(RuntimeError, match="not writable"):
            SSHSyncHandler()


class TestConnect:
    async def test_uses_the_key_named_after_the_device(
        self, handler: SSHSyncHandler, keys_dir: Path, known_hosts: Path, ssh_connect
    ):
        (keys_dir / "deck-1.pem").write_text("key")

        await handler.connect(
            {"ssh_host": "deck.local", "ssh_password": "unused"}, device_id="deck-1"
        )

        ssh_connect.assert_awaited_once_with(
            host="deck.local",
            port=22,
            username="root",
            known_hosts=str(known_hosts),
            client_keys=[str(keys_dir / "deck-1.pem")],
        )

    async def test_an_explicit_key_path_wins_over_the_device_key(
        self, handler: SSHSyncHandler, keys_dir: Path, known_hosts: Path, ssh_connect
    ):
        (keys_dir / "deck-1.pem").write_text("key")
        (keys_dir / "shared.pem").write_text("key")

        await handler.connect(
            {
                "ssh_host": "deck.local",
                "ssh_port": 2222,
                "ssh_username": "deck",
                "ssh_key_path": str(keys_dir / "shared.pem"),
            },
            device_id="deck-1",
        )

        kwargs = _connect_kwargs(ssh_connect)
        assert (kwargs["port"], kwargs["username"]) == (2222, "deck")
        assert kwargs["client_keys"] == [str(keys_dir / "shared.pem")]

    async def test_a_missing_explicit_key_falls_back_to_the_device_key(
        self, handler: SSHSyncHandler, keys_dir: Path, known_hosts: Path, ssh_connect
    ):
        (keys_dir / "deck-1.pem").write_text("key")

        await handler.connect(
            {"ssh_host": "deck.local", "ssh_key_path": str(keys_dir / "gone.pem")},
            device_id="deck-1",
        )

        kwargs = _connect_kwargs(ssh_connect)
        assert kwargs["client_keys"] == [str(keys_dir / "deck-1.pem")]

    async def test_falls_back_to_a_password_without_a_key(
        self, handler: SSHSyncHandler, known_hosts: Path, ssh_connect
    ):
        await handler.connect(
            {"ssh_host": "deck.local", "ssh_password": "hunter2"}, device_id="deck-1"
        )

        kwargs = _connect_kwargs(ssh_connect)
        assert kwargs["password"] == "hunter2"
        assert "client_keys" not in kwargs

    async def test_refuses_without_any_credentials(
        self, handler: SSHSyncHandler, known_hosts: Path, ssh_connect
    ):
        with pytest.raises(ValueError, match="No SSH authentication method"):
            await handler.connect({"ssh_host": "deck.local"}, device_id="deck-1")

        ssh_connect.assert_not_awaited()

    async def test_refuses_without_a_known_hosts_file(
        self,
        handler: SSHSyncHandler,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        ssh_connect,
    ):
        monkeypatch.setattr(
            ssh_handler, "SYNC_SSH_KNOWN_HOSTS_PATH", str(tmp_path / "missing")
        )

        with pytest.raises(FileNotFoundError, match="known_hosts"):
            await handler.connect(
                {"ssh_host": "deck.local", "ssh_password": "hunter2"},
                device_id="deck-1",
            )

        ssh_connect.assert_not_awaited()


REGULAR = asyncssh.constants.FILEXFER_TYPE_REGULAR
DIRECTORY = asyncssh.constants.FILEXFER_TYPE_DIRECTORY


class _ListingSFTP:
    def __init__(
        self,
        tree: dict[str, dict[str, asyncssh.SFTPAttrs | Exception]],
    ):
        self._tree = tree
        self.mkdirs: list[str] = []
        self.puts: list[tuple[str, str]] = []
        self.mkdir_error: Exception | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def listdir(self, path: str) -> list[str]:
        if path not in self._tree:
            raise asyncssh.SFTPNoSuchFile(f"{path} not found")
        return list(self._tree[path])

    async def stat(self, path: str) -> asyncssh.SFTPAttrs:
        directory, _, name = path.rpartition("/")
        entry = self._tree[directory][name]
        if isinstance(entry, Exception):
            raise entry
        return entry

    async def mkdir(self, path: str) -> None:
        self.mkdirs.append(path)
        if self.mkdir_error:
            raise self.mkdir_error

    async def put(self, local_path: str, remote_path: str) -> None:
        self.puts.append((local_path, remote_path))


def _conn(sftp: _ListingSFTP) -> MagicMock:
    conn = MagicMock()
    conn.start_sftp_client.return_value = sftp
    return conn


def _file(size: int, mtime: int) -> asyncssh.SFTPAttrs:
    return asyncssh.SFTPAttrs(type=REGULAR, size=size, mtime=mtime)


class TestListRemoteSaves:
    async def test_lists_regular_files_with_their_platform(
        self, handler: SSHSyncHandler
    ):
        sftp = _ListingSFTP(
            {
                "/saves/gba": {
                    "zelda.srm": _file(512, 1_700_000_000),
                    "states": asyncssh.SFTPAttrs(type=DIRECTORY),
                }
            }
        )

        [save] = await handler.list_remote_saves(
            _conn(sftp), [{"platform_slug": "gba", "path": "/saves/gba"}]
        )

        assert (save.path, save.file_name, save.platform_slug) == (
            "/saves/gba/zelda.srm",
            "zelda.srm",
            "gba",
        )
        assert save.file_size == 512
        assert save.mtime == datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)

    async def test_filters_by_extension(self, handler: SSHSyncHandler):
        sftp = _ListingSFTP(
            {"/saves/snes": {"mario.srm": _file(1, 1), "mario.png": _file(1, 1)}}
        )

        saves = await handler.list_remote_saves(
            _conn(sftp),
            [{"platform_slug": "snes", "path": "/saves/snes", "extension": ".srm"}],
        )

        assert [save.file_name for save in saves] == ["mario.srm"]

    async def test_a_missing_directory_skips_only_that_platform(
        self, handler: SSHSyncHandler
    ):
        sftp = _ListingSFTP({"/saves/gba": {"zelda.srm": _file(1, 1)}})

        saves = await handler.list_remote_saves(
            _conn(sftp),
            [
                {"platform_slug": "snes", "path": "/saves/snes"},
                {"platform_slug": "gba", "path": "/saves/gba"},
            ],
        )

        assert [save.platform_slug for save in saves] == ["gba"]

    async def test_a_file_that_cannot_be_read_is_skipped(self, handler: SSHSyncHandler):
        sftp = _ListingSFTP(
            {
                "/saves/gba": {
                    "locked.srm": asyncssh.SFTPError(3, "permission denied"),
                    "zelda.srm": _file(1, 1),
                }
            }
        )

        saves = await handler.list_remote_saves(
            _conn(sftp), [{"platform_slug": "gba", "path": "/saves/gba"}]
        )

        assert [save.file_name for save in saves] == ["zelda.srm"]


class TestUploadSave:
    async def test_creates_the_directory_and_uploads(self, handler: SSHSyncHandler):
        sftp = _ListingSFTP({})

        await handler.upload_save(_conn(sftp), "/tmp/local.srm", "/saves/gba/a.srm")

        assert sftp.mkdirs == ["/saves/gba"]
        assert sftp.puts == [("/tmp/local.srm", "/saves/gba/a.srm")]

    async def test_an_existing_directory_does_not_stop_the_upload(
        self, handler: SSHSyncHandler
    ):
        sftp = _ListingSFTP({})
        sftp.mkdir_error = asyncssh.SFTPFailure("already exists")

        await handler.upload_save(_conn(sftp), "/tmp/local.srm", "/saves/gba/a.srm")

        assert sftp.puts == [("/tmp/local.srm", "/saves/gba/a.srm")]


def test_the_handler_is_created_once(keys_dir: Path):
    get_ssh_sync_handler.cache_clear()
    try:
        assert get_ssh_sync_handler() is get_ssh_sync_handler()
    finally:
        get_ssh_sync_handler.cache_clear()
