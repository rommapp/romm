"""Tests for md5-gated resource downloads (issue #4002).

ScreenScraper serves its media from fixed endpoints, so a changed artwork never
changes the URL. The only signal that a stored file went stale is the md5
ScreenScraper reports for that media entry, compared against the local copy.
"""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from handler.filesystem.resources_handler import FSResourcesHandler


class _StreamedResponse:
    """Minimal stand-in for an httpx streaming response serving fixed bytes."""

    def __init__(self, payload: bytes):
        self.status_code = 200
        self.headers = {"content-type": "image/png"}
        self._payload = payload

    async def aiter_raw(self):
        yield self._payload


class _StreamContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *_args):
        return False


class _HttpxClient:
    def __init__(self, response):
        self._response = response
        self.calls = 0

    def stream(self, *_args, **_kwargs):
        self.calls += 1
        return _StreamContext(self._response)


@pytest.fixture
def handler(tmp_path):
    handler = FSResourcesHandler()
    handler.base_path = tmp_path
    return handler


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


class TestFileMd5:
    async def test_hashes_a_stored_file(self, handler, tmp_path):
        digest = _write(tmp_path / "roms/1/1/logo/logo.png", b"artwork")

        assert await handler.file_md5("roms/1/1/logo/logo.png") == digest

    async def test_missing_file_has_no_hash(self, handler):
        assert await handler.file_md5("roms/1/1/logo/logo.png") is None

    async def test_traversal_path_has_no_hash(self, handler):
        assert await handler.file_md5("../../etc/passwd") is None

    async def test_matches_is_case_insensitive(self, handler, tmp_path):
        digest = _write(tmp_path / "roms/1/1/logo/logo.png", b"artwork")

        assert await handler.file_matches_md5("roms/1/1/logo/logo.png", digest.upper())

    async def test_does_not_match_different_content(self, handler, tmp_path):
        _write(tmp_path / "roms/1/1/logo/logo.png", b"old artwork")
        other = hashlib.md5(b"new artwork", usedforsecurity=False).hexdigest()

        assert not await handler.file_matches_md5("roms/1/1/logo/logo.png", other)

    async def test_no_expected_hash_never_matches(self, handler, tmp_path):
        _write(tmp_path / "roms/1/1/logo/logo.png", b"artwork")

        assert not await handler.file_matches_md5("roms/1/1/logo/logo.png", None)


class TestDownloadedCoverPath:
    """The hash check has to read the original bytes, not a converted sibling."""

    def test_points_at_the_unconverted_download(self, handler):
        rom = SimpleNamespace(fs_resources_path="roms/1/42")

        assert handler.get_downloaded_cover_path(rom) == "roms/1/42/cover/big.png"

    async def test_hash_still_matches_once_a_webp_sibling_exists(
        self, handler, tmp_path
    ):
        rom = SimpleNamespace(fs_resources_path="roms/1/42")
        digest = _write(tmp_path / "roms/1/42/cover/big.png", b"cover bytes")
        _write(tmp_path / "roms/1/42/cover/big.webp", b"a re-encoded copy")

        path = handler.get_downloaded_cover_path(rom)

        assert await handler.file_matches_md5(path, digest)


class TestStoreMediaFileMd5Gate:
    """`store_media_file` must refetch a file ScreenScraper reports as changed."""

    REL = "roms/1/1/logo/logo.png"

    async def _store(self, handler, payload: bytes, expected_md5: str | None):
        client = _HttpxClient(_StreamedResponse(payload))
        with (
            patch("handler.filesystem.resources_handler.ctx_httpx_client") as ctx,
            patch.object(
                handler, "_discard_if_chroma_key", AsyncMock(return_value=False)
            ),
        ):
            ctx.get.return_value = client
            await handler.store_media_file(
                "http://example.com/logo.png", self.REL, expected_md5=expected_md5
            )
        return client

    async def test_existing_file_is_replaced_when_the_hash_differs(
        self, handler, tmp_path
    ):
        _write(tmp_path / self.REL, b"old artwork")
        new_payload = b"new artwork"
        new_md5 = hashlib.md5(new_payload, usedforsecurity=False).hexdigest()

        client = await self._store(handler, new_payload, new_md5)

        assert client.calls == 1
        assert (tmp_path / self.REL).read_bytes() == new_payload

    async def test_existing_file_is_kept_when_the_hash_matches(self, handler, tmp_path):
        digest = _write(tmp_path / self.REL, b"current artwork")

        client = await self._store(handler, b"never used", digest)

        assert client.calls == 0
        assert (tmp_path / self.REL).read_bytes() == b"current artwork"

    async def test_existing_file_is_kept_without_an_expected_hash(
        self, handler, tmp_path
    ):
        """Providers that publish no hash keep the pre-#4002 behaviour."""
        _write(tmp_path / self.REL, b"current artwork")

        client = await self._store(handler, b"never used", None)

        assert client.calls == 0
        assert (tmp_path / self.REL).read_bytes() == b"current artwork"

    async def test_missing_file_is_downloaded(self, handler, tmp_path):
        payload = b"fresh artwork"
        digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()

        client = await self._store(handler, payload, digest)

        assert client.calls == 1
        assert (tmp_path / self.REL).read_bytes() == payload
