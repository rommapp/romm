"""Tests for the Pouët handler (filename tags + fetch by ID)."""

from unittest.mock import AsyncMock, patch

import pytest

from handler.metadata.pouet_handler import (
    PouetHandler,
    extract_pouet_id_from_filename,
    pouet_id_from_location,
    production_to_rom,
)


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
