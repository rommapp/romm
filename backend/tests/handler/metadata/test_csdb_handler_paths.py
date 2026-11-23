"""CSDb paths the main suite leaves out, driven through a real httpx2 client."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import httpx2
import pytest
import pytest_asyncio
from fastapi import HTTPException, status

from handler.metadata import csdb_handler
from handler.metadata.csdb_handler import (
    CsdbHandler,
    csdb_id_from_url,
    production_from_xml,
)
from utils import get_version
from utils.context import ctx_httpx_client


class CsdbStub:
    """Answers CSDb webservice requests, scripting each reply."""

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
async def csdb(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[CsdbHandler, CsdbStub]]:
    monkeypatch.setattr(csdb_handler, "CSDB_API_ENABLED", True)
    monkeypatch.setattr(csdb_handler._rate_limiter, "acquire", AsyncMock())
    stub = CsdbStub()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(stub))
    token = ctx_httpx_client.set(client)
    try:
        yield CsdbHandler(), stub
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def _release(csdb_id: str = "75330", extra: str = "", year: str = "2012") -> str:
    return (
        f"<CSDbData><Release><ID>{csdb_id}</ID><Name>Working Stone</Name>"
        f"<Type>C64 Demo</Type><ReleaseYear>{year}</ReleaseYear>{extra}"
        "</Release></CSDbData>"
    )


def _xml(body: str, status_code: int = 200) -> httpx2.Response:
    return httpx2.Response(status_code, text=body)


class TestRequest:
    async def test_asks_for_xml_as_romm(self, csdb: tuple[CsdbHandler, CsdbStub]):
        handler, stub = csdb
        stub.replies = [_xml(_release())]

        assert await handler._request(csdb_handler.CSDB_WEBSERVICE) == _release()

        [request] = stub.requests
        assert request.headers["User-Agent"] == f"RomM/{get_version()}"
        assert request.headers["Accept"].startswith("application/xml")

    async def test_a_missing_release_is_empty(self, csdb: tuple[CsdbHandler, CsdbStub]):
        handler, stub = csdb
        stub.replies = [_xml("", status_code=404)]

        assert await handler._request(csdb_handler.CSDB_WEBSERVICE) == ""

    @pytest.mark.parametrize(
        "reply",
        [
            _xml("", status_code=500),
            httpx2.ConnectError("refused"),
            httpx2.ConnectTimeout("slow"),
            httpx2.ReadTimeout("slow"),
            httpx2.RemoteProtocolError("dropped"),
        ],
        ids=["server_error", "refused", "connect_timeout", "read_timeout", "dropped"],
    )
    async def test_a_failed_request_is_unavailable(
        self,
        csdb: tuple[CsdbHandler, CsdbStub],
        reply: httpx2.Response | Exception,
    ):
        handler, stub = csdb
        stub.replies = [reply]

        with pytest.raises(HTTPException) as exc:
            await handler._request(csdb_handler.CSDB_WEBSERVICE)

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestHeartbeat:
    @pytest.mark.parametrize(
        ("reply", "healthy"),
        [
            (_xml(_release()), True),
            (_xml(_release("1")), False),
            (_xml("<CSDbData/>"), False),
            (httpx2.ConnectError("down"), False),
        ],
        ids=["known_release", "another_release", "empty", "down"],
    )
    async def test_reports_whether_csdb_answers(
        self,
        csdb: tuple[CsdbHandler, CsdbStub],
        reply: httpx2.Response | Exception,
        healthy: bool,
    ):
        handler, stub = csdb
        stub.replies = [reply]

        assert await handler.heartbeat() is healthy

    async def test_disabled_asks_nothing(
        self, csdb: tuple[CsdbHandler, CsdbStub], monkeypatch: pytest.MonkeyPatch
    ):
        handler, stub = csdb
        monkeypatch.setattr(csdb_handler, "CSDB_API_ENABLED", False)

        assert await handler.heartbeat() is False
        assert await handler.get_rom_by_id(75330) == {"csdb_id": None}
        assert stub.requests == []


class TestGetRom:
    async def test_fetches_a_release_by_id(self, csdb: tuple[CsdbHandler, CsdbStub]):
        handler, stub = csdb
        stub.replies = [_xml(_release())]

        rom = await handler.get_rom_by_id(75330)

        assert rom["csdb_id"] == 75330
        assert dict(stub.requests[0].url.params) == {
            "type": "release",
            "id": "75330",
            "depth": "2",
        }

    async def test_a_tag_that_names_no_release_is_no_match(
        self, csdb: tuple[CsdbHandler, CsdbStub]
    ):
        handler, stub = csdb
        stub.replies = [_xml("", status_code=404)]

        assert await handler.get_rom("Gone (csdb-1).d64", "c64") == {"csdb_id": None}

    async def test_no_id_asks_nothing(self, csdb: tuple[CsdbHandler, CsdbStub]):
        handler, stub = csdb

        assert await handler.get_rom_by_id(0) == {"csdb_id": None}
        assert stub.requests == []


def test_reads_a_release_nested_deeper_and_its_credits():
    xml = (
        "<CSDbData><Wrapper>"
        + _release(
            extra=(
                "<Credits>"
                "<Credit><CreditType>Code</CreditType>"
                "<Handle><Handle>Pex</Handle></Handle></Credit>"
                "<Credit><CreditType>Music</CreditType></Credit>"
                "</Credits>"
            )
        )
        .removeprefix("<CSDbData>")
        .removesuffix("</CSDbData>")
        + "</Wrapper></CSDbData>"
    )

    rom = production_from_xml(xml)

    assert rom["csdb_id"] == 75330
    assert (rom.get("csdb_metadata") or {}).get("credits") == [
        {"name": "Pex", "role": "Code"}
    ]


def test_a_release_without_a_numeric_id_is_no_match():
    assert production_from_xml(_release("abc")) == {"csdb_id": None}


def test_a_year_that_is_not_a_year_has_no_date():
    rom = production_from_xml(_release(year="soon"))

    assert rom["csdb_id"] == 75330
    assert (rom.get("csdb_metadata") or {}).get("first_release_date") is None


@pytest.mark.parametrize(
    ("url", "csdb_id"),
    [
        ("https://csdb.dk/release/75330", 75330),
        ("https://csdb.dk/release/?id=abc", None),
        ("https://csdb.dk/group/?id=1", None),
        ("https://csdb.dk/scener/?id=1", None),
        ("", None),
    ],
)
def test_csdb_id_from_more_urls(url: str, csdb_id: int | None):
    assert csdb_id_from_url(url) == csdb_id
