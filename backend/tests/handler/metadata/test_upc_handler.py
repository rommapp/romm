from collections.abc import AsyncIterator

import httpx2
import pytest
import pytest_asyncio

from handler.metadata import upc_handler
from handler.metadata.upc_handler import UPCHandler
from utils import get_version
from utils.context import ctx_httpx_client


class UPCStub:
    """Answers UPC lookups through a real httpx2 client, scripting each reply."""

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
async def upc(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[UPCHandler, UPCStub]]:
    monkeypatch.setattr(upc_handler, "UPC_LOOKUP_ENABLED", True)
    monkeypatch.setattr(upc_handler, "UPC_LOOKUP_URL", "https://upc.test/lookup")
    monkeypatch.setattr(upc_handler, "UPC_LOOKUP_API_KEY", "")
    stub = UPCStub()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(stub))
    token = ctx_httpx_client.set(client)
    try:
        yield UPCHandler(), stub
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def _items(*titles: object) -> httpx2.Response:
    return httpx2.Response(200, json={"items": [{"title": t} for t in titles]})


class TestResolve:
    async def test_asks_for_the_trimmed_code_as_romm(
        self, upc: tuple[UPCHandler, UPCStub]
    ):
        handler, stub = upc
        stub.replies = [_items("Chrono Trigger")]

        assert await handler.resolve_upc_to_title(" 0123456789 ") == "Chrono Trigger"

        [request] = stub.requests
        assert str(request.url) == "https://upc.test/lookup?upc=0123456789"
        assert request.headers["User-Agent"] == f"RomM/{get_version()}"
        assert "user_key" not in request.headers

    async def test_sends_the_api_key_when_set(
        self, upc: tuple[UPCHandler, UPCStub], monkeypatch: pytest.MonkeyPatch
    ):
        handler, stub = upc
        monkeypatch.setattr(upc_handler, "UPC_LOOKUP_API_KEY", "secret")
        stub.replies = [_items("Chrono Trigger")]

        await handler.resolve_upc_to_title("0123456789")

        assert stub.requests[0].headers["user_key"] == "secret"

    async def test_takes_the_first_title_long_enough_to_be_a_name(
        self, upc: tuple[UPCHandler, UPCStub]
    ):
        handler, stub = upc
        stub.replies = [_items(None, "", " X ", "Earthbound")]

        assert await handler.resolve_upc_to_title("1") == "Earthbound"

    async def test_strips_retail_noise_from_the_title(
        self, upc: tuple[UPCHandler, UPCStub]
    ):
        handler, stub = upc
        stub.replies = [_items("Sonic Mania - Nintendo Switch")]

        assert await handler.resolve_upc_to_title("1") == "Sonic Mania"

    @pytest.mark.parametrize(
        "reply",
        [
            httpx2.Response(200, json={"items": []}),
            httpx2.Response(200, json={}),
            httpx2.Response(200, json={"items": None}),
            httpx2.Response(404, json={"items": [{"title": "Chrono Trigger"}]}),
            httpx2.Response(200, content=b"<html>"),
            httpx2.ConnectError("down"),
        ],
        ids=["no_items", "items_absent", "items_null", "error", "not_json", "down"],
    )
    async def test_an_unresolved_code_has_no_title(
        self, upc: tuple[UPCHandler, UPCStub], reply: httpx2.Response | Exception
    ):
        handler, stub = upc
        stub.replies = [reply]

        assert await handler.resolve_upc_to_title("1") is None

    @pytest.mark.parametrize(
        "body",
        [
            [{"title": "Chrono Trigger"}],
            {"items": {"title": "Chrono Trigger"}},
            {"items": ["Chrono Trigger"]},
            {"items": [{"title": 1234}]},
        ],
        ids=["list_reply", "items_object", "item_not_object", "title_not_text"],
    )
    async def test_a_reply_of_the_wrong_shape_has_no_title(
        self, upc: tuple[UPCHandler, UPCStub], body: object
    ):
        handler, stub = upc
        stub.replies = [httpx2.Response(200, json=body)]

        assert await handler.resolve_upc_to_title("1") is None

    async def test_a_blank_code_asks_nothing(self, upc: tuple[UPCHandler, UPCStub]):
        handler, stub = upc

        assert await handler.resolve_upc_to_title("   ") is None
        assert stub.requests == []

    async def test_disabled_asks_nothing(
        self, upc: tuple[UPCHandler, UPCStub], monkeypatch: pytest.MonkeyPatch
    ):
        handler, stub = upc
        monkeypatch.setattr(upc_handler, "UPC_LOOKUP_ENABLED", False)

        assert not handler.is_enabled()
        assert await handler.resolve_upc_to_title("0123456789") is None
        assert stub.requests == []


@pytest.mark.parametrize(
    ("title", "cleaned"),
    [
        ("Sonic Mania - Nintendo Switch", "Sonic Mania"),
        ("Halo Infinite (Xbox Series X)", "Halo Infinite"),
        ("Gran Turismo 7 PlayStation 5", "Gran Turismo 7"),
        ("Doom Eternal - PC Video Game", "Doom Eternal"),
        ("Zelda Brand New Sealed", "Zelda"),
        # Noise words only count as whole words.
        ("NPC Wars", "NPC Wars"),
        ("Opal Quest", "Opal Quest"),
        ("Unsealed Fate", "Unsealed Fate"),
        ("Palworld", "Palworld"),
        # A title that is nothing but noise is kept rather than emptied.
        ("PC", "PC"),
    ],
)
def test_clean_title(title: str, cleaned: str):
    assert UPCHandler()._clean_title(title) == cleaned
