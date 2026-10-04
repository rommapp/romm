"""Tests for the Pouët handler (filename tags + fetch by ID)."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
import pytest_asyncio
from fastapi import HTTPException, status

from handler.metadata import base_handler, pouet_handler
from handler.metadata.pouet_handler import (
    POUET_API_PROD,
    PouetHandler,
    extract_pouet_id_from_filename,
    pouet_id_from_location,
    production_to_rom,
)
from utils import get_version
from utils.context import ctx_httpx_client


def test_extract_pouet_id_from_filename():
    assert extract_pouet_id_from_filename("State of the Art (pouet-99).lha") == 99
    assert extract_pouet_id_from_filename("Foo (demozoo-2)(Pouet-99).lha") == 99
    assert extract_pouet_id_from_filename("untagged.lha") is None


def test_pouet_id_from_location():
    assert (
        pouet_id_from_location("https://www.pouet.net/prod.php?which=106640") == 106640
    )
    assert pouet_id_from_location("/prod.php?which=1221") == 1221
    assert pouet_id_from_location("https://www.pouet.net/search.php?what=x") is None


def test_production_to_rom_maps_votes():
    rom = production_to_rom(
        {
            "id": 99,
            "name": "State of the Art",
            "types": ["demo"],
            "groups": [{"name": "Spaceballs"}],
            "screenshot": "https://content.pouet.net/s.jpg",
            "voteavg": "0.863",
            "rank": "1",
            "demozoo": "2",
            "download": "https://files.scene.org/view/sota.lha",
        }
    )
    assert rom["pouet_id"] == 99
    assert rom["name"] == "State of the Art"
    assert rom["pouet_metadata"]["vote_avg"] == pytest.approx(0.863)
    assert rom["pouet_metadata"]["demozoo_id"] == 2
    assert rom["pouet_metadata"]["download_urls"] == [
        "https://files.scene.org/view/sota.lha"
    ]
    assert "Spaceballs" in (rom.get("summary") or "")
    assert "Pouët 0.863" in (rom.get("summary") or "")
    assert "#1" in (rom.get("summary") or "")
    assert "https://www.pouet.net/prod.php?which=99" in (rom.get("summary") or "")
    assert "https://demozoo.org/productions/2/" in (rom.get("summary") or "")
    assert rom["pouet_metadata"]["genres"] == ["Demo"]


def test_production_to_rom_extra_links_and_invitation():
    rom = production_to_rom(
        {
            "id": 55146,
            "name": "Haujobb BBQ 2010",
            "type": "64k,invitation",
            "types": ["64k", "invitation"],
            "groups": [{"name": "Haujobb"}],
            "invitationyear": "2010",
            "download": "https://files.scene.org/view/bbq.zip",
            "downloadLinks": [
                {
                    "type": "soundtrack",
                    "link": "https://files.scene.org/view/bbq.xm",
                },
                {
                    "type": "youtube",
                    "link": "https://www.youtube.com/watch?v=-3fybsqD6OM",
                },
            ],
        }
    )
    meta = rom["pouet_metadata"]
    assert "64K Intro" in meta["genres"]
    assert "Invitation" in meta["genres"]
    assert meta["invitation"] is None
    assert "Invitation" in meta["genres"]
    assert meta["youtube_video_id"] == "-3fybsqD6OM"
    assert "https://files.scene.org/view/bbq.xm" in meta["soundtrack_urls"]
    assert "https://files.scene.org/view/bbq.xm" in meta["download_urls"]


@pytest.mark.asyncio
async def test_get_rom_without_tag_tries_exact_title():
    handler = PouetHandler()
    with (
        patch.object(PouetHandler, "is_enabled", return_value=True),
        patch.object(
            PouetHandler,
            "resolve_exact_title",
            new_callable=AsyncMock,
            return_value=None,
        ) as search,
        patch.object(PouetHandler, "_request", new_callable=AsyncMock) as req,
    ):
        result = await handler.get_rom("State of the Art.lha", "amiga")
    search.assert_awaited_once()
    req.assert_not_called()
    assert result["pouet_id"] is None


@pytest.mark.asyncio
async def test_get_rom_exact_title_302_fetches_by_id():
    handler = PouetHandler()
    payload = {"success": True, "prod": {"id": 106640, "name": "Gomikun Densetsu"}}
    with (
        patch.object(PouetHandler, "is_enabled", return_value=True),
        patch.object(
            PouetHandler,
            "resolve_exact_title",
            new_callable=AsyncMock,
            return_value=106640,
        ),
        patch.object(
            PouetHandler, "_request", new_callable=AsyncMock, return_value=payload
        ) as req,
    ):
        result = await handler.get_rom("Gomikun Densetsu.zip", "nes")
    assert "id=106640" in req.await_args_list[0].args[0]
    assert result["pouet_id"] == 106640
    assert result["name"] == "Gomikun Densetsu"


@pytest.mark.asyncio
async def test_get_rom_uses_filename_tag():
    handler = PouetHandler()
    payload = {"success": True, "prod": {"id": 99, "name": "State of the Art"}}
    with (
        patch.object(PouetHandler, "is_enabled", return_value=True),
        patch.object(
            PouetHandler, "_request", new_callable=AsyncMock, return_value=payload
        ) as req,
    ):
        result = await handler.get_rom("State of the Art (pouet-99).lha", "amiga")
    req.assert_awaited_once()
    assert "id=99" in req.await_args_list[0].args[0]
    assert result["pouet_id"] == 99
    assert result["name"] == "State of the Art"


@pytest.mark.asyncio
async def test_get_rom_by_id_propagates_an_unreachable_pouet():
    """A dead connection has to stay distinguishable from a missing production."""
    handler = PouetHandler()
    with (
        patch.object(PouetHandler, "is_enabled", return_value=True),
        patch.object(
            PouetHandler,
            "_request",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="down"),
        ),
        pytest.raises(HTTPException),
    ):
        await handler.get_rom_by_id(99)


class PouetStub:
    """Answers Pouët requests through a real httpx2 client, scripting each reply."""

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
async def pouet(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[PouetHandler, PouetStub]]:
    monkeypatch.setattr(pouet_handler, "POUET_API_ENABLED", True)
    monkeypatch.setattr(pouet_handler._rate_limiter, "acquire", AsyncMock())
    stub = PouetStub()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(stub))
    token = ctx_httpx_client.set(client)
    try:
        yield PouetHandler(), stub
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def _prod(**fields: object) -> httpx2.Response:
    return httpx2.Response(
        200, json={"success": True, "prod": {"id": 99, "name": "SotA", **fields}}
    )


class TestRequest:
    async def test_asks_for_json_with_a_romm_user_agent(
        self, pouet: tuple[PouetHandler, PouetStub]
    ):
        handler, stub = pouet
        stub.replies = [httpx2.Response(200, json={"success": True})]

        assert await handler._request(f"{POUET_API_PROD}?id=99") == {"success": True}

        [request] = stub.requests
        assert request.headers["Accept"] == "application/json"
        assert request.headers["User-Agent"] == f"RomM/{get_version()}"

    @pytest.mark.parametrize(
        "reply",
        [
            httpx2.Response(500),
            httpx2.ConnectError("refused"),
            httpx2.ReadTimeout("slow"),
            httpx2.ConnectTimeout("slow"),
            httpx2.RemoteProtocolError("dropped"),
        ],
        ids=["server_error", "unreachable", "timed_out", "connect_timeout", "dropped"],
    )
    async def test_a_failed_request_is_unavailable(
        self, pouet: tuple[PouetHandler, PouetStub], reply: httpx2.Response | Exception
    ):
        handler, stub = pouet
        stub.replies = [reply]

        with pytest.raises(HTTPException) as exc:
            await handler._request(f"{POUET_API_PROD}?id=99")

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.parametrize(
        "body",
        [b"<html>", b"[1, 2]", b"x" * 65],
        ids=["not_json", "not_an_object", "over_the_cap"],
    )
    async def test_an_unreadable_reply_is_empty(
        self,
        pouet: tuple[PouetHandler, PouetStub],
        monkeypatch: pytest.MonkeyPatch,
        body: bytes,
    ):
        handler, stub = pouet
        monkeypatch.setattr(base_handler, "MAX_RESPONSE_BYTES", 64)
        stub.replies = [httpx2.Response(200, content=body)]

        assert await handler._request(f"{POUET_API_PROD}?id=99") == {}


class TestHeartbeat:
    @pytest.mark.parametrize(
        ("reply", "healthy"),
        [
            (httpx2.Response(200, json={"success": True}), True),
            (httpx2.Response(200, json={"success": False}), False),
            (httpx2.ConnectError("refused"), False),
        ],
        ids=["success", "refused", "unreachable"],
    )
    async def test_reports_whether_pouet_answers(
        self,
        pouet: tuple[PouetHandler, PouetStub],
        reply: httpx2.Response | Exception,
        healthy: bool,
    ):
        handler, stub = pouet
        stub.replies = [reply]

        assert await handler.heartbeat() is healthy

    async def test_disabled_asks_nothing(
        self, pouet: tuple[PouetHandler, PouetStub], monkeypatch: pytest.MonkeyPatch
    ):
        handler, stub = pouet
        monkeypatch.setattr(pouet_handler, "POUET_API_ENABLED", False)

        assert await handler.heartbeat() is False
        assert await handler.get_rom_by_id(99) == {"pouet_id": None}
        assert await handler.get_rom("SotA (pouet-99).lha", "amiga") == {
            "pouet_id": None
        }
        assert stub.requests == []


class TestGetRomById:
    async def test_maps_the_production(self, pouet: tuple[PouetHandler, PouetStub]):
        handler, stub = pouet
        stub.replies = [_prod()]

        result = await handler.get_rom_by_id(99)

        assert (result["pouet_id"], result["name"]) == (99, "SotA")
        assert str(stub.requests[0].url) == f"{POUET_API_PROD}?id=99"

    @pytest.mark.parametrize(
        "body",
        [
            {"success": False, "prod": {"id": 99}},
            {"success": True},
            {"success": True, "prod": "99"},
            {"success": True, "prod": {"name": "No id"}},
        ],
        ids=["refused", "no_prod", "prod_not_an_object", "prod_without_id"],
    )
    async def test_an_unknown_production_is_no_match(
        self, pouet: tuple[PouetHandler, PouetStub], body: dict[str, object]
    ):
        handler, stub = pouet
        stub.replies = [httpx2.Response(200, json=body)]

        assert await handler.get_rom_by_id(99) == {"pouet_id": None}

    async def test_no_id_asks_nothing(self, pouet: tuple[PouetHandler, PouetStub]):
        handler, stub = pouet

        assert await handler.get_rom_by_id(0) == {"pouet_id": None}
        assert stub.requests == []


class TestResolveExactTitle:
    @pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
    async def test_a_redirect_names_the_production(
        self, pouet: tuple[PouetHandler, PouetStub], code: int
    ):
        handler, stub = pouet
        stub.replies = [
            httpx2.Response(code, headers={"Location": "prod.php?which=1221"})
        ]

        assert await handler.resolve_exact_title(" Second Reality ") == 1221

        [request] = stub.requests
        assert dict(request.url.params) == {"what": "Second Reality", "type": "prod"}

    @pytest.mark.parametrize(
        "reply",
        [
            httpx2.Response(200, text="<html>several results</html>"),
            httpx2.Response(302, headers={"Location": "search.php?what=x"}),
            httpx2.Response(302),
        ],
        ids=["ambiguous", "redirect_elsewhere", "redirect_without_location"],
    )
    async def test_no_unique_production_is_none(
        self, pouet: tuple[PouetHandler, PouetStub], reply: httpx2.Response
    ):
        handler, stub = pouet
        stub.replies = [reply]

        assert await handler.resolve_exact_title("Second Reality") is None

    @pytest.mark.parametrize("title", ["", "ab", "  a  "])
    async def test_a_short_title_asks_nothing(
        self, pouet: tuple[PouetHandler, PouetStub], title: str
    ):
        handler, stub = pouet

        assert await handler.resolve_exact_title(title) is None
        assert stub.requests == []

    @pytest.mark.parametrize(
        "error",
        [httpx2.ConnectError("refused"), httpx2.ReadTimeout("slow")],
        ids=["unreachable", "timed_out"],
    )
    async def test_a_failed_search_is_unavailable(
        self, pouet: tuple[PouetHandler, PouetStub], error: Exception
    ):
        handler, stub = pouet
        stub.replies = [error]

        with pytest.raises(HTTPException) as exc:
            await handler.resolve_exact_title("Second Reality")

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestGetRom:
    async def test_an_unknown_tag_falls_back_to_the_title(
        self, pouet: tuple[PouetHandler, PouetStub]
    ):
        handler, stub = pouet
        stub.replies = [
            httpx2.Response(200, json={"success": False}),
            httpx2.Response(302, headers={"Location": "prod.php?which=99"}),
            _prod(),
        ]

        result = await handler.get_rom("SotA (pouet-5).lha", "amiga")

        assert result["pouet_id"] == 99
        assert dict(stub.requests[1].url.params) == {"what": "SotA", "type": "prod"}

    async def test_an_unmatched_title_is_no_match(
        self, pouet: tuple[PouetHandler, PouetStub]
    ):
        handler, stub = pouet
        stub.replies = [httpx2.Response(200, text="<html>")]

        assert await handler.get_rom("SotA.lha", "amiga") == {"pouet_id": None}
        assert len(stub.requests) == 1


class TestProductionToRom:
    def test_lists_party_placings_credits_and_platforms(self):
        rom = production_to_rom(
            {
                "id": 7,
                "name": "Second Reality",
                "type": "demo",
                "releaseDate": "1993-10-09",
                "groups": [{"name": "Future Crew"}, {"name": ""}, "bad"],
                "platforms": {"1": {"name": "MS-Dos"}, "2": {}, "3": "bad"},
                "party": {"name": "Assembly 1993"},
                "placings": [
                    "bad",
                    {
                        "party": {"name": "Assembly 1993"},
                        "year": "1993",
                        "compo_name": "PC Demo",
                        "ranking": "1",
                    },
                    {"party": {"name": "Assembly"}, "year": "1993", "ranking": "1"},
                    {"compo_name": "Oldskool"},
                    {"ranking": "4"},
                    {"party": {"name": "The Party"}, "ranking": "9"},
                ],
                "credits": [
                    {"user": {"nickname": "Purple Motion"}, "role": "music"},
                    {"user": {"nickname": "Psi"}, "role": "code"},
                    {"user": "bad", "role": "code"},
                    {"user": {}, "role": "graphics"},
                    "bad",
                ],
                "invitation": {"name": "Assembly"},
                "invitationyear": "1994",
                "csdb": "123",
                "zxdemo": "45",
                "popularity": "88.5",
                "cdc": "12",
            }
        )

        meta = rom["pouet_metadata"]
        assert meta["groups"] == ["Future Crew"]
        assert meta["platforms"] == ["MS-Dos"]
        assert meta["party"] == "Assembly 1993 / PC Demo #1"
        assert meta["credits"] == [
            {"name": "Purple Motion", "role": "Music"},
            {"name": "Psi", "role": "Code"},
        ]
        assert meta["invitation"] == "Invitation for Assembly (1994)"
        assert meta["pouet_popularity"] == pytest.approx(88.5)
        assert meta["pouet_cdc"] == 12
        assert meta["download_urls"] == [
            "https://csdb.dk/release/?id=123",
            "https://zxdemo.org/prod.php?id=45",
        ]
        # Three placing lines at most: a placing with no party takes the
        # production's, and a year already in the party name isn't repeated.
        assert (rom.get("summary") or "").split(" · ")[:4] == [
            "Demo by Future Crew (1993)",
            "Assembly 1993 / PC Demo #1",
            "Assembly 1993 #1",
            "Assembly 1993 / Oldskool",
        ]
        assert "#4" not in (rom.get("summary") or "")
        assert "The Party" not in (rom.get("summary") or "")

    def test_party_fields_without_placings_make_one_line(self):
        rom = production_to_rom(
            {
                "id": 7,
                "name": "Intro",
                "party": {"name": "Revision"},
                "party_year": "2024",
                "party_compo_name": "PC 4K",
                "party_place": "2",
            }
        )

        assert rom["pouet_metadata"]["party"] == "Revision 2024 / PC 4K #2"

    def test_a_placing_supplies_the_missing_party(self):
        rom = production_to_rom(
            {"id": 7, "name": "Intro", "placings": [{"party": {"name": "Evoke"}}]}
        )

        assert rom["pouet_metadata"]["party"] == "Evoke"

    def test_bare_party_fields_still_make_a_line(self):
        rom = production_to_rom(
            {"id": 7, "name": "Intro", "party_compo_name": "Wild", "party_place": "3"}
        )

        assert rom["pouet_metadata"]["party"] == "Wild #3"

    @pytest.mark.parametrize(
        ("type_field", "types"),
        [
            ("4k, procedural graphics", ["4K Intro", "Graphics"]),
            ("demo,,demo", ["Demo"]),
            ("music video", ["Music Video"]),
        ],
    )
    def test_types_are_labelled_once(self, type_field: str, types: list[str]):
        rom = production_to_rom({"id": 7, "name": "X", "type": type_field})

        assert rom["pouet_metadata"]["types"] == types

    def test_the_screenshot_is_the_cover_and_bad_links_are_dropped(self):
        rom = production_to_rom(
            {
                "id": 7,
                "name": "X",
                "screenshot": "https://content.pouet.net/x.png",
                "download": "https://youtu.be/dQw4w9WgXcQ",
                "downloadLinks": [{"link": ""}, "bad", {"link": "ftp://old/x.zip"}],
                "voteavg": "not-a-number",
            }
        )

        assert rom["url_cover"] == "https://content.pouet.net/x.png"
        assert rom["url_screenshots"] == ["https://content.pouet.net/x.png"]
        meta = rom["pouet_metadata"]
        assert meta["download_urls"] == ["https://youtu.be/dQw4w9WgXcQ"]
        assert meta["youtube_video_id"] == "dQw4w9WgXcQ"
        assert meta["vote_avg"] is None

    @pytest.mark.parametrize("demozoo", [None, "", "0", 0, "abc"])
    def test_no_demozoo_id_is_none(self, demozoo: object):
        rom = production_to_rom({"id": 7, "name": "X", "demozoo": demozoo})

        assert rom["pouet_metadata"]["demozoo_id"] is None


@pytest.mark.parametrize(
    ("location", "pouet_id"),
    [
        ("", None),
        ("prod.php?WHICH=12", 12),
        ("prod.php?which=", None),
        ("prod.php?id=3&which=abc", None),
    ],
)
def test_reads_the_production_from_a_redirect(location: str, pouet_id: int | None):
    assert pouet_id_from_location(location) == pouet_id
