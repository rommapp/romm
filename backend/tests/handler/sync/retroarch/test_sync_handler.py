import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from handler.filesystem.retroarch_sync_handler import BlobFile, FSRetroArchSyncHandler
from handler.redis_handler import async_cache, sync_cache
from handler.sync.retroarch.sync_handler import HASH_CACHE_TTL_SECONDS, cached_hashes


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    sync_cache.flushall()
    yield
    sync_cache.flushall()


class TestCachedMd5s:
    async def test_misses_are_written_back_with_the_ttl(self):
        await cached_hashes([("miss", mock.AsyncMock(return_value="fresh-md5"))])

        assert await async_cache.get("miss") == b"fresh-md5"
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
