import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx

from handler.metadata.playmatch_handler import PlaymatchHandler
from models.rom import Rom, RomFile
from utils import get_version


@patch("handler.metadata.playmatch_handler.ctx_httpx_client")
async def test_heartbeat_accepts_plain_text_health_response(mock_ctx_httpx_client):
    # /health returns a 200 with the plain-text body "Healthy", not JSON.
    handler = PlaymatchHandler()
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.text = "Healthy"
    mock_response.json.side_effect = json.JSONDecodeError(
        "Expecting value", "Healthy", 0
    )
    mock_client.get.return_value = mock_response
    mock_ctx_httpx_client.get.return_value = mock_client

    with (
        patch.object(handler, "is_enabled", return_value=True),
        patch(
            "handler.metadata.playmatch_handler._rate_limiter.acquire",
            new_callable=AsyncMock,
        ),
    ):
        assert await handler.heartbeat() is True

    mock_client.get.assert_awaited_once_with(
        handler.healthcheck_url,
        headers={"user-agent": f"RomM/{get_version()}"},
        timeout=60,
    )
    mock_response.raise_for_status.assert_called_once()


@patch("handler.metadata.playmatch_handler.ctx_httpx_client")
async def test_heartbeat_returns_false_on_http_error(mock_ctx_httpx_client):
    handler = PlaymatchHandler()
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=MagicMock()
    )
    mock_client.get.return_value = mock_response
    mock_ctx_httpx_client.get.return_value = mock_client

    with (
        patch.object(handler, "is_enabled", return_value=True),
        patch(
            "handler.metadata.playmatch_handler._rate_limiter.acquire",
            new_callable=AsyncMock,
        ),
    ):
        assert await handler.heartbeat() is False


async def test_heartbeat_returns_false_when_disabled():
    handler = PlaymatchHandler()
    with patch.object(handler, "is_enabled", return_value=False):
        assert await handler.heartbeat() is False


def _rom_file(*, is_top_level: bool = True, **kwargs) -> RomFile:
    """Build a RomFile whose `is_top_level` cached_property is pre-seeded, so it
    reaches lookup_rom's filtering without a persisted rom."""
    file = RomFile(file_path="psx/Game", **kwargs)
    file.__dict__["is_top_level"] = is_top_level
    return file


async def _captured_lookup_payload(handler: PlaymatchHandler, files) -> dict | None:
    with (
        patch.object(handler, "is_enabled", return_value=True),
        patch.object(handler, "_request", new_callable=AsyncMock) as mock_request,
    ):
        mock_request.return_value = {}
        await handler.lookup_rom(files)

    if not mock_request.await_args_list:
        return None
    return mock_request.await_args_list[-1].args[1]


async def test_lookup_rom_identifies_an_archive_by_its_largest_member():
    """Playmatch indexes a multi-file archive by the ROM inside it, so the
    archive's composite hash must not be what we ask about. The file name and
    size stay those of the archive on disk."""
    archive = _rom_file(
        file_name="set.zip",
        file_size_bytes=300,
        crc_hash="compositecrc",
        md5_hash="compositemd5",
        sha1_hash="compositesha1",
        archive_members=[
            {
                "name": "readme.txt",
                "size": 10,
                "crc_hash": "readmecrc",
                "md5_hash": "readmemd5",
                "sha1_hash": "readmesha1",
            },
            {
                "name": "game.rom",
                "size": 2048,
                "crc_hash": "gamecrc",
                "md5_hash": "gamemd5",
                "sha1_hash": "gamesha1",
            },
        ],
    )

    payload = await _captured_lookup_payload(PlaymatchHandler(), [archive])

    assert payload == {
        "fileName": "set.zip",
        "fileSize": 300,
        "md5": "gamemd5",
        "sha1": "gamesha1",
        "crc": "gamecrc",
    }


def _multi_disc_files(disc_two_size: int = 200) -> list[RomFile]:
    """A folder ROM the way the scanner emits it: a small playlist next to the
    discs that actually carry the game."""
    return [
        _rom_file(file_name="game.m3u", file_size_bytes=20, md5_hash="playlistmd5"),
        _rom_file(
            file_name="disc1.chd", file_size_bytes=300, chd_sha1_hash="disconesha1"
        ),
        _rom_file(
            file_name="disc2.chd",
            file_size_bytes=disc_two_size,
            chd_sha1_hash="disctwosha1",
        ),
    ]


async def test_lookup_rom_asks_about_a_disc_not_the_playlist():
    """The playlist has no game data in it, so identifying a multi-disc ROM by
    it can only ever miss."""
    payload = await _captured_lookup_payload(PlaymatchHandler(), _multi_disc_files())

    assert payload == {
        "fileName": "disc1.chd",
        "fileSize": 300,
        "md5": None,
        "sha1": "disconesha1",
        "crc": None,
    }


async def test_lookup_rom_payload_does_not_depend_on_file_order():
    """The scanner walks the filesystem unsorted and the files relationship has
    no order_by, so anything that leans on list order asks about a different
    file on a different machine."""
    handler = PlaymatchHandler()
    # Equally sized discs, so only the tie-break can settle which one wins.
    files = _multi_disc_files(disc_two_size=300)

    payloads = [
        await _captured_lookup_payload(handler, list(order))
        for order in (files, reversed(files), files[1:] + files[:1])
    ]

    assert payloads[0] is not None
    assert payloads[0] == payloads[1] == payloads[2]
    assert payloads[0]["fileName"] == "disc1.chd"


async def test_lookup_rom_ignores_files_nested_inside_the_rom():
    """Hasheous and ScreenScraper both filter on is_top_level; a bundled extra
    or translation patch is not what the ROM should be identified by."""
    files = [
        _rom_file(file_name="game.iso", file_size_bytes=100, md5_hash="gamemd5"),
        _rom_file(
            file_name="bonus.iso",
            file_size_bytes=9000,
            md5_hash="bonusmd5",
            is_top_level=False,
        ),
    ]

    payload = await _captured_lookup_payload(PlaymatchHandler(), files)

    assert payload is not None
    assert payload["fileName"] == "game.iso"


async def test_lookup_rom_skips_the_request_when_no_file_qualifies():
    """No eligible file must not blow up on an empty max()."""
    files = [
        _rom_file(file_name="empty.iso", file_size_bytes=0, md5_hash="emptymd5"),
        _rom_file(
            file_name="nested.iso",
            file_size_bytes=100,
            md5_hash="nestedmd5",
            is_top_level=False,
        ),
    ]

    assert await _captured_lookup_payload(PlaymatchHandler(), files) is None
    assert await _captured_lookup_payload(PlaymatchHandler(), []) is None


async def _captured_suggestion_payload(rom: Rom) -> dict | None:
    handler = PlaymatchHandler()
    mock_client = AsyncMock()
    mock_client.post.return_value = MagicMock()
    with (
        patch.object(handler, "is_enabled", return_value=True),
        patch(
            "handler.metadata.playmatch_handler.ctx_httpx_client"
        ) as mock_ctx_httpx_client,
        patch(
            "handler.metadata.playmatch_handler._rate_limiter.acquire",
            new_callable=AsyncMock,
        ),
    ):
        mock_ctx_httpx_client.get.return_value = mock_client
        await handler.submit_manual_match_suggestion(rom)

    if not mock_client.post.await_args_list:
        return None
    return mock_client.post.await_args.kwargs["json"]


async def test_suggestion_contributes_the_selected_files_hashes():
    """A suggestion writes a hash-to-game mapping into a public index, so it
    must carry the same digests a lookup would be answered by."""
    rom = Rom(igdb_id=1234)
    rom.files = _multi_disc_files() + [
        _rom_file(
            file_name="extras.zip",
            file_size_bytes=50,
            md5_hash="compositemd5",
            sha1_hash="compositesha1",
        )
    ]

    payload = await _captured_suggestion_payload(rom)

    assert payload == {
        "md5": None,
        "sha1": "disconesha1",
        "sha256": None,
        "fileName": "disc1.chd",
        "fileSize": 300,
        "mappings": ANY,
    }


async def test_suggestion_is_skipped_when_no_file_qualifies():
    """Falling back to the ROM-level hash would contribute a composite spanning
    every file, which is not a digest of anything Playmatch indexes."""
    rom = Rom(igdb_id=1234, fs_name="game.zip", fs_size_bytes=100)
    rom.md5_hash = "compositemd5"
    rom.sha1_hash = "compositesha1"
    rom.files = []

    assert await _captured_suggestion_payload(rom) is None
