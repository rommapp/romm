"""Tests for the Demozoo handler (filename tags + fetch by ID)."""

from collections.abc import AsyncIterator, Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
import pytest_asyncio
from fastapi import HTTPException, status

from handler.metadata import demozoo_handler
from handler.metadata.demozoo_handler import (
    DemozooHandler,
    _pouet_id_from_url,
    _youtube_id_from_url,
    build_scene_summary,
    demozoo_id_from_url,
    extract_demozoo_id_from_filename,
    format_credit_line,
    http_url,
    production_to_rom,
    scene_notes_from_production,
    scene_notes_from_tags,
    splice_csdb_url,
    splice_pouet_vote,
)
from utils import get_version
from utils.context import ctx_httpx_client


def test_extract_demozoo_id_from_filename():
    assert extract_demozoo_id_from_filename("Second Reality (demozoo-108).zip") == 108
    assert extract_demozoo_id_from_filename("Foo (Demozoo-2)(pouet-99).lha") == 2
    assert extract_demozoo_id_from_filename("untagged.zip") is None


def test_http_url_allows_only_http_schemes():
    assert http_url("https://demozoo.org/productions/108/")
    assert http_url("http://files.scene.org/get/foo.zip")
    assert http_url("javascript:alert(1)") is None
    assert http_url("file:///etc/passwd") is None
    assert http_url("/relative") is None
    assert http_url("") is None


def test_demozoo_id_from_url():
    assert demozoo_id_from_url("108") == 108
    assert demozoo_id_from_url("https://demozoo.org/productions/108/") == 108
    assert demozoo_id_from_url("https://www.demozoo.org/productions/108") == 108
    assert demozoo_id_from_url("https://demozoo.org/api/v1/productions/108/") == 108
    assert demozoo_id_from_url("https://www.pouet.net/prod.php?which=63") is None
    assert demozoo_id_from_url("") is None


def test_production_to_rom_maps_title_and_youtube():
    rom = production_to_rom(
        {
            "id": 108,
            "title": "Second Reality",
            "release_date": "1993-07-31",
            "types": [{"name": "Demo"}],
            "author_nicks": [
                {"name": "Future Crew", "releaser": {"is_group": True}},
            ],
            "screenshots": [{"standard_url": "https://media.demozoo.org/s.png"}],
            "download_links": [
                {
                    "link_class": "SceneOrgFile",
                    "url": "https://files.scene.org/view/foo.zip",
                },
            ],
            "external_links": [
                {
                    "link_class": "YoutubeVideo",
                    "url": "https://www.youtube.com/watch?v=ugPZnsRHUkc",
                },
                {
                    "link_class": "PouetProduction",
                    "url": "https://www.pouet.net/prod.php?which=63",
                },
                {
                    "link_class": "CsdbRelease",
                    "url": "https://csdb.dk/release/?id=75330",
                },
            ],
        }
    )
    assert rom["demozoo_id"] == 108
    assert rom["name"] == "Second Reality"
    assert rom["url_cover"] == "https://media.demozoo.org/s.png"
    assert rom["demozoo_metadata"]["youtube_video_id"] == "ugPZnsRHUkc"
    assert rom["demozoo_metadata"]["pouet_id"] == 63
    assert rom["demozoo_metadata"]["csdb_id"] == 75330
    assert rom["demozoo_metadata"]["download_urls"] == [
        "https://www.youtube.com/watch?v=ugPZnsRHUkc",
        "https://files.scene.org/view/foo.zip",
    ]
    assert "Future Crew" in (rom.get("summary") or "")
    summary = rom.get("summary") or ""
    assert "https://www.youtube.com/watch?v=ugPZnsRHUkc" in summary
    assert "https://demozoo.org/productions/108/" in summary
    assert "https://www.pouet.net/prod.php?which=63" in summary
    assert "https://csdb.dk/release/?id=75330" in summary


def test_production_to_rom_includes_party_and_placing():
    rom = production_to_rom(
        {
            "id": 393719,
            "title": "Gomikun Densetsu",
            "release_date": "2026-01-01",
            "types": [{"name": "Demo"}],
            "author_nicks": [{"name": "Bjorn", "releaser": {"is_group": False}}],
            "competition_placings": [
                {
                    "ranking": 6,
                    "competition": {
                        "name": "Oldschool Demo",
                        "party": {"id": 4242, "name": "Shadow Party 2026"},
                    },
                }
            ],
            "external_links": [
                {
                    "link_class": "YoutubeVideo",
                    "url": "https://www.youtube.com/watch?v=GH3acdwWi1E",
                },
                {
                    "link_class": "PouetProduction",
                    "url": "https://www.pouet.net/prod.php?which=106640",
                },
            ],
        }
    )
    assert rom["summary"] == (
        "Demo by Bjorn (2026) · Shadow Party 2026 / Oldschool Demo #6 · "
        "https://www.youtube.com/watch?v=GH3acdwWi1E · "
        "https://demozoo.org/productions/393719/ · "
        "https://www.pouet.net/prod.php?which=106640"
    )
    meta = rom["demozoo_metadata"]
    assert meta["party"] == "Shadow Party 2026"
    assert meta["party_id"] == 4242
    assert meta["party_line"] == "Shadow Party 2026 / Oldschool Demo #6"


def test_production_to_rom_credits_tags_and_wiki():
    rom = production_to_rom(
        {
            "id": 108,
            "title": "Second Reality",
            "types": [{"name": "Demo"}],
            "credits": [
                {
                    "nick": {"name": "Purple Motion"},
                    "category": "Music",
                },
                {
                    "nick": {"name": "Pixel"},
                    "category": "Graphics",
                },
            ],
            "tags": ["source-available", "hidden-part"],
            "external_links": [
                {
                    "link_class": "WikipediaPage",
                    "url": "https://en.wikipedia.org/wiki/Second_Reality",
                },
                {
                    "link_class": "GithubRepo",
                    "url": "https://github.com/mtuomi/SecondReality",
                },
            ],
        }
    )
    meta = rom["demozoo_metadata"]
    assert meta["collections"] == ["source-available", "hidden-part"]
    assert meta["credits"][0]["name"] == "Purple Motion"
    assert "Music: Purple Motion" in (rom.get("summary") or "")
    assert "https://en.wikipedia.org/wiki/Second_Reality" in meta["download_urls"]
    assert "https://github.com/mtuomi/SecondReality" in meta["download_urls"]


def test_splice_pouet_vote_inserts_before_urls():
    base = (
        "Demo by Bjorn (2026) · Shadow Party 2026 / Oldschool Demo #6 · "
        "https://demozoo.org/productions/393719/"
    )
    assert splice_pouet_vote(base, 0.7) == (
        "Demo by Bjorn (2026) · Shadow Party 2026 / Oldschool Demo #6 · "
        "Pouët 0.700 · https://demozoo.org/productions/393719/"
    )
    assert splice_pouet_vote(base, 0.7, 14, 7) == (
        "Demo by Bjorn (2026) · Shadow Party 2026 / Oldschool Demo #6 · "
        "Pouët 0.700 · #14 · CdC 7 · https://demozoo.org/productions/393719/"
    )
    assert "Pouët 0.700" in splice_pouet_vote(splice_pouet_vote(base, 0.7), 0.7)


def test_scene_notes_from_tags_no_sound():
    assert scene_notes_from_tags(["no-sound", "trainer"]) == ["no sound"]
    assert scene_notes_from_tags(["NO-SOUND", "no-sound"]) == ["no sound"]
    assert scene_notes_from_tags(["screenshots-needed"]) == []
    assert scene_notes_from_tags([]) == []
    assert scene_notes_from_tags(["hidden-part"]) == ["hidden part"]


def test_scene_notes_from_production_json_fields():
    assert scene_notes_from_production({"notes": "  "}, []) == []
    assert scene_notes_from_production({"notes": "Has a hidden scroller"}, []) == [
        "Has a hidden scroller"
    ]
    assert scene_notes_from_production({"hidden_parts": [{"name": "end"}]}, []) == [
        "hidden part"
    ]
    long_note = "x" * 120
    clipped = scene_notes_from_production({"notes": long_note}, [])
    assert len(clipped) == 1
    assert clipped[0].endswith("…")
    assert len(clipped[0]) == 80
    assert scene_notes_from_production(
        {"hidden_parts": [1], "notes": ""}, ["hidden-part"]
    ) == ["hidden part"]


def test_production_to_rom_includes_no_sound_note():
    rom = production_to_rom(
        {
            "id": 393484,
            "title": "Lada 2000",
            "types": [{"name": "Cracktro"}],
            "author_nicks": [{"name": "Skid Row", "releaser": {"is_group": True}}],
            "tags": ["no-sound"],
        }
    )
    assert "no sound" in (rom.get("summary") or "")
    assert rom["demozoo_metadata"]["tags"] == ["no-sound"]


def test_production_to_rom_includes_hidden_part_and_notes():
    rom = production_to_rom(
        {
            "id": 108,
            "title": "Second Reality",
            "types": [{"name": "Demo"}],
            "author_nicks": [{"name": "Future Crew", "releaser": {"is_group": True}}],
            "tags": ["hidden-part"],
            "notes": "Secret end part",
            "competition_placings": [
                {
                    "ranking": "1",
                    "competition": {
                        "name": "PC Demo",
                        "party": {"id": 101, "name": "Assembly 1993"},
                    },
                }
            ],
        }
    )
    summary = rom.get("summary") or ""
    assert "hidden part" in summary
    assert "Secret end part" in summary
    assert "Assembly 1993 / PC Demo #1" in summary
    meta = rom["demozoo_metadata"]
    assert meta["party"] == "Assembly 1993"
    assert meta["party_id"] == 101
    assert meta["party_line"] == "Assembly 1993 / PC Demo #1"


def test_splice_csdb_url_appends_once():
    base = "Cracktro by Fairlight (1993) · https://demozoo.org/productions/396054/"
    url = "https://csdb.dk/release/?id=75331"
    assert splice_csdb_url(base, url) == f"{base} · {url}"
    assert splice_csdb_url(f"{base} · {url}", url).count(url) == 1
    assert splice_csdb_url(base, None) == base


@pytest.mark.asyncio
async def test_get_rom_disabled_does_not_hit_api():
    """The source ships off, so a disabled handler must stay off the network."""
    handler = DemozooHandler()
    with (
        patch.object(DemozooHandler, "is_enabled", return_value=False),
        patch.object(DemozooHandler, "_request", new_callable=AsyncMock) as req,
    ):
        result = await handler.get_rom("Second Reality (demozoo-108).zip", "dos")
    req.assert_not_called()
    assert result["demozoo_id"] is None


@pytest.mark.asyncio
async def test_get_rom_title_search_applies_high_confidence():
    handler = DemozooHandler()
    hits = [{"id": 108, "title": "Second Reality"}]
    full = {"id": 108, "title": "Second Reality", "types": [{"name": "Demo"}]}
    with (
        patch.object(DemozooHandler, "is_enabled", return_value=True),
        patch.object(
            DemozooHandler,
            "search_productions",
            new_callable=AsyncMock,
            return_value=hits,
        ),
        patch.object(
            DemozooHandler,
            "get_rom_by_id",
            new_callable=AsyncMock,
            return_value=production_to_rom(full),
        ) as by_id,
    ):
        result = await handler.get_rom("Second Reality.zip", "dos")
    by_id.assert_awaited_once_with(108)
    assert result["demozoo_id"] == 108


@pytest.mark.asyncio
async def test_get_rom_uses_filename_tag():
    handler = DemozooHandler()
    payload = {"id": 108, "title": "Second Reality"}
    with (
        patch.object(DemozooHandler, "is_enabled", return_value=True),
        patch.object(
            DemozooHandler, "_request", new_callable=AsyncMock, return_value=payload
        ) as req,
    ):
        result = await handler.get_rom("Second Reality (demozoo-108).zip", "dos")
    req.assert_awaited_once()
    assert "productions/108/" in req.await_args_list[0].args[0]
    assert result["demozoo_id"] == 108
    assert result["name"] == "Second Reality"


@pytest.mark.parametrize(
    "raw_url",
    ["javascript:alert(1)", "https://demozoo.org/productions/108/", 108, None],
)
def test_production_to_rom_only_keeps_an_http_demozoo_url(raw_url):
    """A hostile record must not put a javascript: URL where an href could go."""
    rom = production_to_rom(
        {"id": 108, "title": "Second Reality", "demozoo_url": raw_url}
    )
    assert (
        rom["demozoo_metadata"]["demozoo_url"] == "https://demozoo.org/productions/108/"
    )


def test_youtube_id_must_be_ascii():
    """isalnum() accepts non-ASCII digits; a video id is ASCII only."""
    rom = production_to_rom(
        {
            "id": 108,
            "title": "Second Reality",
            "external_links": [
                {
                    "link_class": "YoutubeVideo",
                    "url": "https://www.youtube.com/watch?v=ugPZnsRH٣k٣",
                },
            ],
        }
    )
    assert rom["demozoo_metadata"]["youtube_video_id"] is None


@pytest.mark.asyncio
async def test_request_returns_empty_when_over_the_cap():
    handler = DemozooHandler()
    with patch.object(DemozooHandler, "_fetch_capped", AsyncMock(return_value=None)):
        assert await handler._request("https://demozoo.org/api/v1/x") == {}


@pytest.mark.asyncio
async def test_get_rom_by_id_propagates_an_unreachable_demozoo():
    """A dead connection has to stay distinguishable from a missing production."""
    handler = DemozooHandler()
    with (
        patch.object(DemozooHandler, "is_enabled", return_value=True),
        patch.object(
            DemozooHandler,
            "_request",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="down"),
        ),
        pytest.raises(HTTPException),
    ):
        await handler.get_rom_by_id(1234)


class DemozooStub:
    """Answers Demozoo requests through a real httpx2 client, scripting each reply."""

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
async def demozoo(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[DemozooHandler, DemozooStub]]:
    monkeypatch.setattr(demozoo_handler, "DEMOZOO_API_ENABLED", True)
    monkeypatch.setattr(demozoo_handler._rate_limiter, "acquire", AsyncMock())
    stub = DemozooStub()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(stub))
    token = ctx_httpx_client.set(client)
    try:
        yield DemozooHandler(), stub
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def _json(body: object, status_code: int = 200) -> httpx2.Response:
    return httpx2.Response(status_code, json=body)


SECOND_REALITY = {"id": 108, "title": "Second Reality"}


class TestRequest:
    async def test_asks_for_json_as_romm(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json(SECOND_REALITY)]

        assert await handler._request("https://demozoo.org/api/v1/x") == SECOND_REALITY

        [request] = stub.requests
        assert request.headers["User-Agent"] == f"RomM/{get_version()}"
        assert request.headers["Accept"] == "application/json"

    async def test_a_missing_production_is_empty(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json({}, status_code=404)]

        assert (
            await handler._request("https://demozoo.org/api/v1/x", missing_ok=True)
            == {}
        )

    @pytest.mark.parametrize(
        "reply",
        [httpx2.Response(200, content=b"<html>"), _json([SECOND_REALITY])],
        ids=["not_json", "not_an_object"],
    )
    async def test_an_empty_answer_is_empty(
        self, demozoo: tuple[DemozooHandler, DemozooStub], reply: httpx2.Response
    ):
        handler, stub = demozoo
        stub.replies = [reply]

        assert await handler._request("https://demozoo.org/api/v1/x") == {}

    @pytest.mark.parametrize(
        "reply",
        [
            _json({}, status_code=500),
            _json({}, status_code=429),
            _json({}, status_code=404),
            httpx2.ConnectError("refused"),
            httpx2.ConnectTimeout("slow"),
            httpx2.ReadTimeout("slow"),
            httpx2.RemoteProtocolError("dropped"),
        ],
        ids=[
            "server_error",
            "rate_limited",
            "route_gone",
            "refused",
            "connect_timeout",
            "read_timeout",
            "dropped",
        ],
    )
    async def test_a_failed_request_is_unavailable(
        self,
        demozoo: tuple[DemozooHandler, DemozooStub],
        reply: httpx2.Response | Exception,
    ):
        handler, stub = demozoo
        stub.replies = [reply]

        with pytest.raises(HTTPException) as exc:
            await handler._request("https://demozoo.org/api/v1/x")

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestHeartbeat:
    @pytest.mark.parametrize(
        ("reply", "healthy"),
        [
            (_json({"results": [SECOND_REALITY]}), True),
            (_json({"results": []}), False),
            (httpx2.ConnectError("down"), False),
        ],
        ids=["results", "empty", "down"],
    )
    async def test_reports_whether_demozoo_answers(
        self,
        demozoo: tuple[DemozooHandler, DemozooStub],
        reply: httpx2.Response | Exception,
        healthy: bool,
    ):
        handler, stub = demozoo
        stub.replies = [reply]

        assert await handler.heartbeat() is healthy

    async def test_disabled_is_unhealthy_without_asking(
        self,
        demozoo: tuple[DemozooHandler, DemozooStub],
        monkeypatch: pytest.MonkeyPatch,
    ):
        handler, stub = demozoo
        monkeypatch.setattr(demozoo_handler, "DEMOZOO_API_ENABLED", False)

        assert await handler.heartbeat() is False
        assert stub.requests == []


class TestGetRomById:
    async def test_fetches_the_production(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json(SECOND_REALITY)]

        rom = await handler.get_rom_by_id(108)

        assert (rom["demozoo_id"], rom.get("name")) == (108, "Second Reality")
        assert stub.requests[0].url.path == "/api/v1/productions/108/"

    @pytest.mark.parametrize(
        "reply",
        [_json({}, status_code=404), _json({"detail": "Not found."})],
        ids=["not_found", "no_id"],
    )
    async def test_a_missing_production_is_no_match(
        self, demozoo: tuple[DemozooHandler, DemozooStub], reply: httpx2.Response
    ):
        handler, stub = demozoo
        stub.replies = [reply]

        assert await handler.get_rom_by_id(999999) == {"demozoo_id": None}

    async def test_no_id_asks_nothing(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo

        assert await handler.get_rom_by_id(0) == {"demozoo_id": None}
        assert stub.requests == []


class TestGetRom:
    async def test_a_stale_tag_falls_back_to_the_title(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [
            _json({}, status_code=404),
            _json({"results": [SECOND_REALITY]}),
            _json(SECOND_REALITY),
        ]

        rom = await handler.get_rom("Second Reality (demozoo-5).zip", "dos")

        assert rom["demozoo_id"] == 108
        assert [r.url.path for r in stub.requests] == [
            "/api/v1/productions/5/",
            "/api/v1/productions/",
            "/api/v1/productions/108/",
        ]

    async def test_searches_the_title_on_the_platform(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json({"results": [SECOND_REALITY]}), _json(SECOND_REALITY)]

        await handler.get_rom("Second Reality.zip", "dos")

        assert dict(stub.requests[0].url.params) == {
            "title": "Second Reality",
            "platform": "4",
        }

    async def test_an_unknown_platform_searches_every_platform(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json({"results": []})]

        await handler.get_rom("Second Reality.zip", "not-a-platform")

        assert dict(stub.requests[0].url.params) == {"title": "Second Reality"}

    @pytest.mark.parametrize(
        "results",
        [[], [{"id": 9, "title": "Something Else Entirely"}]],
        ids=["no_hits", "no_close_title"],
    )
    async def test_no_good_title_match_is_no_match(
        self,
        demozoo: tuple[DemozooHandler, DemozooStub],
        results: list[dict[str, Any]],
    ):
        handler, stub = demozoo
        stub.replies = [_json({"results": results})]

        assert await handler.get_rom("Second Reality.zip", "dos") == {
            "demozoo_id": None
        }

    async def test_a_name_that_is_only_tags_asks_no_search(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json({}, status_code=404)]

        assert await handler.get_rom("(demozoo-5).zip", "dos") == {"demozoo_id": None}
        assert len(stub.requests) == 1


class TestSearch:
    async def test_a_search_route_that_is_gone_is_unavailable(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json({}, status_code=404)]

        with pytest.raises(HTTPException) as exc:
            await handler.get_rom("Second Reality.zip", "dos")

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_keeps_rows_with_an_id_up_to_the_limit(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        rows = [{"id": 1}, {"title": "no id"}, "not an object", {"id": 2}, {"id": 3}]
        stub.replies = [_json({"results": rows})]

        assert await handler.search_productions("x", limit=4) == [{"id": 1}, {"id": 2}]

    async def test_results_that_are_not_a_list_are_none(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json({"results": {"id": 1}})]

        assert await handler.search_productions("x") == []

    async def test_matched_roms_skip_unreadable_rows(
        self, demozoo: tuple[DemozooHandler, DemozooStub]
    ):
        handler, stub = demozoo
        stub.replies = [_json({"results": [SECOND_REALITY, {"id": "abc"}]})]

        roms = await handler.get_matched_roms_by_name("Second Reality", "dos")

        assert [r["demozoo_id"] for r in roms] == [108]
        assert dict(stub.requests[0].url.params)["platform"] == "4"

    async def test_matched_roms_need_a_term_and_the_source(
        self,
        demozoo: tuple[DemozooHandler, DemozooStub],
        monkeypatch: pytest.MonkeyPatch,
    ):
        handler, stub = demozoo
        assert await handler.get_matched_roms_by_name("", "dos") == []
        monkeypatch.setattr(demozoo_handler, "DEMOZOO_API_ENABLED", False)
        assert await handler.get_matched_roms_by_name("x", "dos") == []
        assert stub.requests == []


class TestProductionRows:
    def test_skips_rows_that_are_not_objects_or_have_no_name(self):
        rom = production_to_rom(
            {
                "id": 108,
                "author_nicks": ["Purple Motion", {"name": ""}, {"name": "Skaven"}],
                "competition_placings": ["first", {"competition": "Demo"}],
                "credits": [
                    "Purple Motion",
                    {"nick": "Skaven", "category": "Music"},
                    {"nick": {"name": "Psi"}, "category": "Code"},
                ],
                "external_links": ["link", {"link_class": "Website", "url": ""}],
                "screenshots": ["shot.png"],
                "download_links": ["file.zip"],
            }
        )
        meta = rom.get("demozoo_metadata") or {}

        assert meta.get("companies") == ["Skaven"]
        assert meta.get("credits") == [{"name": "Psi", "role": "Code"}]
        assert meta.get("party_line") is None
        assert meta.get("download_urls") == []
        assert rom.get("url_screenshots") == []

    def test_keeps_three_placings_and_the_first_party_id(self):
        placings = [
            {
                "ranking": n,
                "competition": {
                    "name": f"Comp {n}",
                    "party": {"name": "Assembly", "id": party_id},
                },
            }
            for n, party_id in ((1, "bad"), (2, 7), (3, 8), (4, 9))
        ]

        rom = production_to_rom({"id": 1, "competition_placings": placings})
        summary = rom.get("summary") or ""

        assert (rom.get("demozoo_metadata") or {}).get("party_id") == 7
        assert "Assembly / Comp 3 #3" in summary
        assert "Comp 4" not in summary

    def test_reads_the_invitation_and_csdb_link(self):
        rom = production_to_rom(
            {
                "id": 1,
                "invitation_parties": [
                    {"id": 3},
                    {"name": "Revision"},
                    {"name": "Assembly"},
                ],
                "external_links": [
                    {
                        "link_class": "CsdbRelease",
                        "url": "https://csdb.dk/release/?id=12345",
                    }
                ],
            }
        )
        meta = rom.get("demozoo_metadata") or {}

        assert meta.get("invitation") == "Invitation for Revision"
        assert meta.get("csdb_url") == "https://csdb.dk/release/?id=12345"
        assert meta.get("download_urls") == []


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/user/futurecrew", None),
        ("https://vimeo.com/123", None),
        ("", None),
    ],
)
def test_youtube_id_from_url(url: str, video_id: str | None):
    assert _youtube_id_from_url(url) == video_id


@pytest.mark.parametrize(
    ("url", "pouet_id"),
    [
        ("https://www.pouet.net/prod.php?which=63", 63),
        ("https://www.pouet.net/prod.php?which=63&howmany=5", 63),
        ("https://www.pouet.net/prod.php?which=abc", None),
        ("https://www.pouet.net/", None),
    ],
)
def test_pouet_id_from_url(url: str, pouet_id: int | None):
    assert _pouet_id_from_url(url) == pouet_id


def test_format_credit_line_groups_roles_and_caps_names():
    rows: list[Mapping[str, object]] = [
        {"name": "Purple Motion", "role": "Music"},
        {"name": "Skaven", "role": "Music"},
        {"name": "Skaven", "role": "Music"},
        {"name": ""},
        {"name": "Psi"},
        {"name": "Trug", "role": "Code"},
    ]

    assert format_credit_line(rows) == (
        "Music: Purple Motion, Skaven · Credits: Psi · Code: Trug"
    )
    assert format_credit_line(rows, limit=2) == "Music: Purple Motion, Skaven"
    assert format_credit_line(rows, limit=1) == "Music: Purple Motion"


def test_scene_summary_places_the_pouet_score_before_the_links():
    summary = build_scene_summary(
        types=["Demo"],
        who="Future Crew",
        year="1993",
        party_lines=["Assembly 1993 #1"],
        invitation="Invitation for Assembly",
        vote_avg=0.9,
        pouet_rank=3000,
        pouet_cdc=12,
        demozoo_url="https://demozoo.org/productions/108/",
    )

    assert summary == (
        "Demo by Future Crew (1993) · Assembly 1993 #1 · Invitation for Assembly"
        " · Pouët 0.900 · CdC 12 · https://demozoo.org/productions/108/"
    )


def test_splice_pouet_vote_without_a_score_keeps_the_summary():
    assert splice_pouet_vote("Demo · https://x", None) == "Demo · https://x"
