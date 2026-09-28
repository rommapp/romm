"""Tests for the Demozoo handler (filename tags + fetch by ID)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from handler.metadata.demozoo_handler import (
    DemozooHandler,
    demozoo_id_from_url,
    extract_demozoo_id_from_filename,
    http_url,
    production_to_rom,
    scene_notes_from_production,
    scene_notes_from_tags,
    splice_csdb_url,
    splice_pouet_vote,
)


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
