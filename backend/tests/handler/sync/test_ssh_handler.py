import hashlib
import shutil
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from anyio import Path as AnyioPath
from tests._zipfile_shim import reload_zipfile

from handler.filesystem.assets_handler import hash_save_file
from handler.sync.ssh_handler import SSHSyncHandler


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
