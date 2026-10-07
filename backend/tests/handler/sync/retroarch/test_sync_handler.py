import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest

from handler.database import db_save_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.retroarch_sync_handler import BlobFile, FSRetroArchSyncHandler
from handler.redis_handler import async_cache, sync_cache
from handler.sync.retroarch.sync_handler import (
    HASH_CACHE_TTL_SECONDS,
    build_manifest,
    cached_hashes,
    list_manifest_paths,
    user_blob_path,
)
from models.user import User


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    sync_cache.flushall()
    yield
    sync_cache.flushall()


class TestCachedMd5s:
    async def test_misses_are_written_back_with_the_ttl(self):
        await cached_hashes([("miss", mock.AsyncMock(return_value="fresh-md5"))])

        # The test fake stores bytes, where production decodes to str.
        assert cast(object, await async_cache.get("miss")) == b"fresh-md5"
        ttl = await async_cache.ttl("miss")
        assert 0 < ttl <= HASH_CACHE_TTL_SECONDS

    async def test_mixes_hits_and_misses_in_order(self):
        await async_cache.set("b", "cached-b")
        jobs = [
            ("a", mock.AsyncMock(return_value="fresh-a")),
            ("b", mock.AsyncMock(return_value="fresh-b")),
            ("c", mock.AsyncMock(return_value=None)),
        ]

        assert await cached_hashes(jobs) == ["fresh-a", "cached-b", None]
        jobs[1][1].assert_not_awaited()

    async def test_unreadable_files_are_not_cached(self):
        await cached_hashes([("gone", mock.AsyncMock(return_value=None))])

        assert await async_cache.exists("gone") == 0

    async def test_reads_the_cache_in_one_round_trip(self):
        jobs = [(f"key{i}", mock.AsyncMock(return_value=f"md5-{i}")) for i in range(5)]
        with mock.patch.object(async_cache, "mget", wraps=async_cache.mget) as mget:
            await cached_hashes(jobs)

        mget.assert_called_once()


class TestManifestQueriesOffEventLoop:
    @pytest.fixture
    def query_threads(self) -> Iterator[list[int]]:
        threads: list[int] = []
        get_saves = db_save_handler.get_saves

        def recording_get_saves(*args: Any, **kwargs: Any) -> Any:
            threads.append(threading.get_ident())
            return get_saves(*args, **kwargs)

        with mock.patch.object(db_save_handler, "get_saves", recording_get_saves):
            yield threads

    async def test_build_manifest(self, admin_user: User, query_threads: list[int]):
        await build_manifest(admin_user, lambda _rom: True)

        assert query_threads and threading.get_ident() not in query_threads

    async def test_list_manifest_paths(
        self, admin_user: User, query_threads: list[int]
    ):
        await list_manifest_paths(admin_user, lambda _rom: True, "saves")

        assert query_threads and threading.get_ident() not in query_threads


class TestBlobStorageLocation:
    def test_blobs_live_in_the_users_assets_folder(self, admin_user: User):
        # The assets root is a documented volume; anything outside it is lost on container recreate.
        assert FSRetroArchSyncHandler().base_path == fs_asset_handler.base_path
        assert user_blob_path(admin_user, "config/retroarch.cfg") == (
            f"{fs_asset_handler.user_folder_path(admin_user)}/retroarch/config/retroarch.cfg"
        )


@pytest.fixture
def blob_handler(tmp_path: Path) -> FSRetroArchSyncHandler:
    handler = FSRetroArchSyncHandler()
    handler.base_path = tmp_path.resolve()
    return handler


class TestListBlobFiles:
    async def test_lists_nested_files_with_their_stats(
        self, blob_handler: FSRetroArchSyncHandler, tmp_path: Path
    ):
        (tmp_path / "config" / "cores" / "Snes9x").mkdir(parents=True)
        (tmp_path / "config" / "retroarch.cfg").write_bytes(b"cfg")
        nested = tmp_path / "config" / "cores" / "Snes9x" / "Snes9x.opt"
        nested.write_bytes(b"options")

        files = await blob_handler.list_blob_files("config")

        assert sorted(files, key=lambda f: f.relative_path) == [
            BlobFile("cores/Snes9x/Snes9x.opt", 7, nested.stat().st_mtime),
            BlobFile(
                "retroarch.cfg",
                3,
                (tmp_path / "config" / "retroarch.cfg").stat().st_mtime,
            ),
        ]

    async def test_does_not_descend_into_symlinked_directories(
        self, blob_handler: FSRetroArchSyncHandler, tmp_path: Path
    ):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret").write_bytes(b"secret")
        (tmp_path / "config").mkdir()
        os.symlink(outside, tmp_path / "config" / "linked")

        assert await blob_handler.list_blob_files("config") == []

    async def test_missing_prefix_is_empty(self, blob_handler: FSRetroArchSyncHandler):
        assert await blob_handler.list_blob_files("config") == []

    async def test_traversing_prefix_is_empty(
        self, blob_handler: FSRetroArchSyncHandler
    ):
        assert await blob_handler.list_blob_files("../config") == []
