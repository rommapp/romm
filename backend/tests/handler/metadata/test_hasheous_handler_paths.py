"""Hasheous paths the main suite leaves out, driven through a real httpx2 client:
the request's error mapping, the heartbeat, the IGDB proxy, and matches whose
shape Hasheous did not promise."""

from collections.abc import AsyncIterator
from typing import Any

import httpx2
import pytest
import pytest_asyncio
from fastapi import HTTPException, status

from handler.metadata import hasheous_handler
from handler.metadata.hasheous_handler import HasheousHandler, HasheousRom
from models.rom import RomFile
from utils import get_version
from utils.context import ctx_httpx_client


class HasheousStub:
    """Answers Hasheous requests, scripting each reply."""

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
async def hasheous(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[HasheousHandler, HasheousStub]]:
    monkeypatch.setattr(hasheous_handler, "HASHEOUS_API_ENABLED", True)
    stub = HasheousStub()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(stub))
    token = ctx_httpx_client.set(client)
    try:
        yield HasheousHandler(), stub
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def _json(body: object, status_code: int = 200) -> httpx2.Response:
    return httpx2.Response(status_code, json=body)


def _rom_file(sha1: str = "disc1") -> RomFile:
    file = RomFile(
        file_name=f"{sha1}.chd",
        file_path="psx/Game",
        file_size_bytes=700,
        sha1_hash=sha1,
    )
    # Pre-seeded so the file passes the top-level filter without a persisted rom.
    file.__dict__["is_top_level"] = True
    return file


class TestRequest:
    async def test_posts_the_hashes_with_the_client_key(
        self, hasheous: tuple[HasheousHandler, HasheousStub]
    ):
        handler, stub = hasheous
        stub.replies = [_json({"id": 1})]

        assert await handler._request(
            handler.games_endpoint, params={"a": "b"}, data=[{"shA1": "x"}]
        ) == {"id": 1}

        [request] = stub.requests
        assert request.method == "POST"
        assert request.url.params["a"] == "b"
        assert request.content == b'[{"shA1":"x"}]'
        assert request.headers["X-Client-API-Key"] == handler.app_api_key
        assert request.headers["User-Agent"] == f"RomM/{get_version()}"

    async def test_a_get_sends_no_body(
        self, hasheous: tuple[HasheousHandler, HasheousStub]
    ):
        handler, stub = hasheous
        stub.replies = [_json({"id": 1})]

        await handler._request(handler.proxy_igdb_game_endpoint, method="get")

        assert (stub.requests[0].method, stub.requests[0].content) == ("GET", b"")

    async def test_an_unsupported_method_is_refused(
        self, hasheous: tuple[HasheousHandler, HasheousStub]
    ):
        handler, stub = hasheous

        with pytest.raises(ValueError):
            await handler._request(handler.games_endpoint, method="PUT")

        assert stub.requests == []

    @pytest.mark.parametrize(
        "reply",
        [_json({}, status_code=404), httpx2.Response(200, content=b"<html>")],
        ids=["not_found", "not_json"],
    )
    async def test_an_empty_answer_is_empty(
        self, hasheous: tuple[HasheousHandler, HasheousStub], reply: httpx2.Response
    ):
        handler, stub = hasheous
        stub.replies = [reply]

        assert await handler._request(handler.games_endpoint) == {}

    @pytest.mark.parametrize(
        "reply",
        [
            _json({}, status_code=500),
            httpx2.ConnectError("refused"),
            httpx2.ReadTimeout("slow"),
            httpx2.RemoteProtocolError("dropped"),
        ],
        ids=["server_error", "refused", "timeout", "dropped"],
    )
    async def test_a_failed_request_is_unavailable(
        self,
        hasheous: tuple[HasheousHandler, HasheousStub],
        reply: httpx2.Response | Exception,
    ):
        handler, stub = hasheous
        stub.replies = [reply]

        with pytest.raises(HTTPException) as exc:
            await handler._request(handler.games_endpoint)

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestHeartbeat:
    @pytest.mark.parametrize(
        ("reply", "healthy"),
        [
            (httpx2.Response(200, text="Healthy"), True),
            (httpx2.Response(503), False),
            (httpx2.ConnectError("down"), False),
        ],
        ids=["healthy", "unhealthy", "down"],
    )
    async def test_reports_whether_hasheous_answers(
        self,
        hasheous: tuple[HasheousHandler, HasheousStub],
        reply: httpx2.Response | Exception,
        healthy: bool,
    ):
        handler, stub = hasheous
        stub.replies = [reply]

        assert await handler.heartbeat() is healthy
        assert stub.requests[0].url.path.endswith("/HealthCheck")

    async def test_disabled_answers_nothing(
        self,
        hasheous: tuple[HasheousHandler, HasheousStub],
        monkeypatch: pytest.MonkeyPatch,
    ):
        handler, stub = hasheous
        monkeypatch.setattr(hasheous_handler, "HASHEOUS_API_ENABLED", False)
        rom = HasheousRom(hasheous_id=1, igdb_id=427, tgdb_id=None)

        assert await handler.heartbeat() is False
        assert await handler.lookup_rom("psx", [_rom_file()]) == (
            {"hasheous_id": None, "igdb_id": None, "tgdb_id": None},
            False,
        )
        assert await handler.get_igdb_game(rom) is rom
        assert stub.requests == []


IGDB_GAME = {
    "slug": "final-fantasy-vii",
    "name": "Final Fantasy VII",
    "summary": "A mercenary joins a rebellion.",
    "cover": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/co1.jpg"},
    "screenshots": {
        "7": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/sc7.jpg"}
    },
}


class TestIgdbGame:
    async def test_fills_the_rom_from_the_proxy(
        self, hasheous: tuple[HasheousHandler, HasheousStub]
    ):
        handler, stub = hasheous
        stub.replies = [_json(IGDB_GAME)]
        rom = HasheousRom(hasheous_id=1, igdb_id=427, tgdb_id=None, name="FF7")

        filled = await handler.get_igdb_game(rom)

        assert (filled.get("name"), filled.get("slug"), filled.get("summary")) == (
            "Final Fantasy VII",
            "final-fantasy-vii",
            "A mercenary joins a rebellion.",
        )
        assert filled.get("url_cover") == (
            "https://images.igdb.com/igdb/image/upload/t_1080p/co1.jpg"
        )
        assert filled.get("url_screenshots") == [
            "https://images.igdb.com/igdb/image/upload/t_720p/sc7.jpg"
        ]
        assert stub.requests[0].url.params["Id"] == "427"

    async def test_keeps_the_rom_without_an_igdb_id_or_a_game(
        self, hasheous: tuple[HasheousHandler, HasheousStub]
    ):
        handler, stub = hasheous
        stub.replies = [_json({}, status_code=404)]
        without_id = HasheousRom(hasheous_id=1, igdb_id=None, tgdb_id=None)
        unknown = HasheousRom(hasheous_id=1, igdb_id=999, tgdb_id=None)

        assert await handler.get_igdb_game(without_id) is without_id
        assert await handler.get_igdb_game(unknown) is unknown
        assert len(stub.requests) == 1


def _match(**fields: Any) -> dict[str, Any]:
    return {"id": 262307, "name": "Final Fantasy VII", **fields}


class TestLookupShapes:
    async def test_an_igdb_slug_and_a_logo_are_read(
        self, hasheous: tuple[HasheousHandler, HasheousStub]
    ):
        handler, stub = hasheous
        stub.replies = [
            _json(
                _match(
                    metadata=[{"source": "IGDB", "immutableId": "final-fantasy-vii"}],
                    attributes=[
                        {"attributeName": "Description", "link": "/d"},
                        {"attributeName": "Logo", "link": "/images/ff7.png"},
                    ],
                )
            )
        ]

        rom, conclusive = await handler.lookup_rom("psx", [_rom_file()])

        assert conclusive
        assert rom["igdb_id"] is None
        assert rom.get("url_cover") == f"{handler.BASE_ORIGIN}/images/ff7.png"

    @pytest.mark.parametrize(
        "fields",
        [
            {"metadata": [{"source": "IGDB"}, {"immutableId": "427"}, "IGDB"]},
            {"metadata": [{"source": "TheGamesDb", "immutableId": "tgdb-slug"}]},
            {"metadata": None, "attributes": None, "signatures": None},
            {"attributes": [{"link": "/x"}, {"attributeName": "Logo"}, "Logo"]},
        ],
        ids=["metadata_missing_keys", "tgdb_not_a_number", "nulls", "attributes"],
    )
    async def test_a_shape_hasheous_did_not_promise_still_matches(
        self,
        hasheous: tuple[HasheousHandler, HasheousStub],
        fields: dict[str, Any],
    ):
        handler, stub = hasheous
        stub.replies = [_json(_match(**fields))]

        rom, conclusive = await handler.lookup_rom("psx", [_rom_file()])

        assert conclusive
        assert rom["hasheous_id"] == 262307
        assert (rom["igdb_id"], rom["tgdb_id"]) == (None, None)


def test_an_invalid_base_url_leaves_cover_links_relative(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(hasheous_handler, "HASHEOUS_API_URL", "http://[bad")

    assert HasheousHandler().BASE_ORIGIN == ""


def test_an_unknown_platform_has_no_hasheous_id():
    assert HasheousHandler().get_platform("not-a-platform") == {
        "hasheous_id": None,
        "slug": "not-a-platform",
    }


def test_a_known_platform_carries_its_provider_ids():
    platform = HasheousHandler().get_platform("3do")

    assert (platform["hasheous_id"], platform.get("igdb_id")) == (161825, 50)


async def test_files_without_hashes_ask_nothing(
    hasheous: tuple[HasheousHandler, HasheousStub],
):
    handler, stub = hasheous
    unhashed = _rom_file("")

    assert await handler.lookup_rom("psx", [unhashed]) == (
        {"hasheous_id": None, "igdb_id": None, "tgdb_id": None},
        False,
    )
    assert stub.requests == []
