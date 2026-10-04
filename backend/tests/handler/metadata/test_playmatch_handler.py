import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, cast
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx2
import pytest
import pytest_asyncio
from fastapi import HTTPException, status

from handler.metadata import playmatch_handler
from handler.metadata.playmatch_handler import PlaymatchHandler
from models.rom import Rom, RomFile
from utils import get_version
from utils.context import ctx_httpx_client


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
    mock_response.raise_for_status.side_effect = httpx2.HTTPStatusError(
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


async def _captured_lookup_payload(
    handler: PlaymatchHandler, files
) -> dict[str, Any] | None:
    with (
        patch.object(handler, "is_enabled", return_value=True),
        patch.object(handler, "_request", new_callable=AsyncMock) as mock_request,
    ):
        mock_request.return_value = {}
        await handler.lookup_rom(files)

    if not mock_request.await_args_list:
        return None
    return cast(dict[str, Any] | None, mock_request.await_args_list[-1].args[1])


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


def _unhashed_file(rom: Rom, file_path: str, file_name: str) -> RomFile:
    file = RomFile(file_path=file_path, file_name=file_name, file_size_bytes=1024)
    file.rom = rom
    file.__dict__["is_top_level"] = True
    return file


async def test_lookup_rom_skips_an_unhashed_folder_member():
    """Wii U content files share generic names across titles, so asking by name
    and size alone matches every title to the same unrelated game."""
    rom = Rom(fs_path="wiiu", fs_name="Adventure Island [0005000010134100]")
    member = _unhashed_file(rom, rom.full_path, "00000005.app")

    assert await _captured_lookup_payload(PlaymatchHandler(), [member]) is None


async def test_lookup_rom_asks_about_an_unhashed_single_file_by_name():
    rom = Rom(fs_path="switch", fs_name="Game [0100000000010000].nsp")
    single = _unhashed_file(rom, "switch", rom.fs_name)

    payload = await _captured_lookup_payload(PlaymatchHandler(), [single])

    assert payload is not None
    assert payload["fileName"] == rom.fs_name


async def _captured_suggestion_payload(rom: Rom) -> dict[str, Any] | None:
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
    return cast(dict[str, Any] | None, mock_client.post.await_args.kwargs["json"])


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


class PlaymatchStub:
    """Answers Playmatch requests through a real httpx2 client, scripting each reply."""

    def __init__(self) -> None:
        self.replies: list[httpx2.Response | Exception] = []
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest_asyncio.fixture
async def playmatch(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[PlaymatchHandler, PlaymatchStub]]:
    monkeypatch.setattr(playmatch_handler, "PLAYMATCH_API_ENABLED", True)
    monkeypatch.setattr(playmatch_handler._rate_limiter, "acquire", AsyncMock())
    # Swap only this module's reference, so httpx2 keeps its real sleep.
    monkeypatch.setattr(
        "handler.metadata.playmatch_handler.asyncio",
        MagicMock(wraps=asyncio, sleep=AsyncMock()),
    )
    stub = PlaymatchStub()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(stub))
    token = ctx_httpx_client.set(client)
    try:
        yield PlaymatchHandler(), stub
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def _json(status_code: int, body: object) -> httpx2.Response:
    return httpx2.Response(status_code, json=body)


class TestRequest:
    async def test_drops_empty_parameters_and_sends_a_romm_user_agent(
        self, playmatch: tuple[PlaymatchHandler, PlaymatchStub]
    ):
        handler, stub = playmatch
        stub.replies = [_json(200, {"gameMatchType": "MD5"})]

        result = await handler._request(
            handler.identify_url, {"fileName": "a.sfc", "md5": "", "sha1": None}
        )

        assert result == {"gameMatchType": "MD5"}
        [request] = stub.requests
        assert dict(request.url.params) == {"fileName": "a.sfc"}
        assert request.headers["user-agent"] == f"RomM/{get_version()}"

    async def test_a_rate_limited_request_backs_off_and_retries(
        self, playmatch: tuple[PlaymatchHandler, PlaymatchStub]
    ):
        handler, stub = playmatch
        stub.replies = [_json(429, {}), _json(200, {"ok": True})]

        assert await handler._request(handler.identify_url, {}) == {"ok": True}
        assert len(stub.requests) == 2

    @pytest.mark.parametrize(
        "replies",
        [
            [_json(429, {}), _json(429, {})],
            [_json(500, {})],
            [httpx2.ConnectError("refused")],
            [httpx2.ReadTimeout("slow")],
        ],
        ids=["rate_limited_twice", "server_error", "unreachable", "timed_out"],
    )
    async def test_a_failed_request_is_unavailable(
        self,
        playmatch: tuple[PlaymatchHandler, PlaymatchStub],
        replies: list[httpx2.Response | Exception],
    ):
        handler, stub = playmatch
        stub.replies = list(replies)

        with pytest.raises(HTTPException) as exc:
            await handler._request(handler.identify_url, {})

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.parametrize(
        "reply",
        [httpx2.Response(200, content=b"<html>"), _json(200, ["not", "an", "object"])],
        ids=["not_json", "not_an_object"],
    )
    async def test_an_unreadable_reply_is_empty(
        self,
        playmatch: tuple[PlaymatchHandler, PlaymatchStub],
        reply: httpx2.Response,
        lenient: MagicMock,
    ):
        handler, stub = playmatch
        stub.replies = [reply]

        assert await handler._request(handler.identify_url, {}) == {}


def _match(*metadata: object) -> httpx2.Response:
    return _json(200, {"gameMatchType": "MD5", "externalMetadata": list(metadata)})


def _game_file() -> RomFile:
    return _rom_file(file_name="game.sfc", file_size_bytes=100, md5_hash="abc")


class TestLookupRom:
    async def test_maps_each_provider_the_scan_uses(
        self, playmatch: tuple[PlaymatchHandler, PlaymatchStub]
    ):
        handler, stub = playmatch
        stub.replies = [
            _match(
                {"providerName": "IGDB", "providerId": "1"},
                {"providerName": "MobyGames", "providerId": 2},
                {"providerName": "SCREENSCRAPER", "providerId": "3"},
                {"providerName": "LAUNCHBOX", "providerId": "4"},
                {"providerName": "STEAMGRIDDB", "providerId": "5"},
                # Suggestion-only tags and broken entries are skipped.
                {"providerName": "RETRO_ACHIEVEMENTS", "providerId": "6"},
                {"providerName": "NEW_PROVIDER", "providerId": "7"},
                {"providerName": "IGDB", "providerId": "not-a-number"},
                {"providerName": "", "providerId": "8"},
                {"providerName": "MOBYGAMES"},
                {"providerName": 9, "providerId": "9"},
                "not-an-object",
            )
        ]

        result = await handler.lookup_rom([_game_file()])

        assert {k: v for k, v in result.items() if v is not None} == {
            "igdb_id": 1,
            "moby_id": 2,
            "ss_id": 3,
            "launchbox_id": 4,
            "sgdb_id": 5,
        }
        [request] = stub.requests
        assert dict(request.url.params) == {
            "fileName": "game.sfc",
            "fileSize": "100",
            "md5": "abc",
        }

    @pytest.mark.parametrize(
        "reply",
        [
            _json(
                200,
                {
                    "gameMatchType": "NoMatch",
                    "externalMetadata": [{"providerName": "IGDB", "providerId": "1"}],
                },
            ),
            _json(200, {"gameMatchType": "MD5", "externalMetadata": []}),
            _json(200, {"gameMatchType": "MD5"}),
            _json(200, {"gameMatchType": "MD5", "externalMetadata": None}),
            _json(200, {"gameMatchType": "MD5", "externalMetadata": {"IGDB": 1}}),
            _json(500, {}),
        ],
        ids=[
            "no_match",
            "no_metadata",
            "metadata_absent",
            "metadata_null",
            "metadata_not_a_list",
            "error",
        ],
    )
    async def test_an_empty_or_failed_lookup_is_no_match(
        self, playmatch: tuple[PlaymatchHandler, PlaymatchStub], reply: httpx2.Response
    ):
        handler, stub = playmatch
        stub.replies = [reply]

        result = await handler.lookup_rom([_game_file()])

        assert set(result.values()) == {None}

    async def test_disabled_asks_nothing(
        self,
        playmatch: tuple[PlaymatchHandler, PlaymatchStub],
        monkeypatch: pytest.MonkeyPatch,
    ):
        handler, stub = playmatch
        monkeypatch.setattr(playmatch_handler, "PLAYMATCH_API_ENABLED", False)

        result = await handler.lookup_rom([_game_file()])

        assert set(result.values()) == {None}
        assert stub.requests == []


class TestSuggestion:
    def _rom(self, **ids: object) -> Rom:
        rom = Rom(**ids)
        rom.files = [_game_file()]
        return rom

    async def test_posts_every_tracked_provider_id(
        self, playmatch: tuple[PlaymatchHandler, PlaymatchStub]
    ):
        handler, stub = playmatch
        stub.replies = [_json(201, {})]

        await handler.submit_manual_match_suggestion(
            self._rom(igdb_id=1, ra_id=6, flashpoint_id="fp-uuid")
        )

        [request] = stub.requests
        assert request.method == "POST"
        assert str(request.url) == handler.suggestion_url
        assert json.loads(request.content)["mappings"] == [
            {"provider": "IGDB", "providerId": "1"},
            {"provider": "RETRO_ACHIEVEMENTS", "providerId": "6"},
            {"provider": "FLASHPOINT", "providerId": "fp-uuid"},
        ]

    async def test_a_rom_without_ids_posts_nothing(
        self, playmatch: tuple[PlaymatchHandler, PlaymatchStub]
    ):
        handler, stub = playmatch

        await handler.submit_manual_match_suggestion(self._rom())

        assert stub.requests == []

    async def test_disabled_posts_nothing(
        self,
        playmatch: tuple[PlaymatchHandler, PlaymatchStub],
        monkeypatch: pytest.MonkeyPatch,
    ):
        handler, stub = playmatch
        monkeypatch.setattr(playmatch_handler, "PLAYMATCH_API_ENABLED", False)

        await handler.submit_manual_match_suggestion(self._rom(igdb_id=1))

        assert stub.requests == []

    async def test_a_failed_post_is_ignored(
        self, playmatch: tuple[PlaymatchHandler, PlaymatchStub]
    ):
        handler, stub = playmatch
        stub.replies = [_json(500, {})]

        await handler.submit_manual_match_suggestion(self._rom(igdb_id=1))

        assert len(stub.requests) == 1


@pytest.mark.parametrize(
    ("fields", "manual"),
    [
        ({"igdb_id", "name"}, True),
        ({"gamelist_id"}, True),
        ({"name", "summary"}, False),
    ],
)
def test_a_form_with_a_provider_id_is_a_manual_match(fields: set[str], manual: bool):
    assert PlaymatchHandler.is_manual_match(fields) is manual
