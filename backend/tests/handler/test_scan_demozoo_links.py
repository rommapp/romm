"""How a scan follows Demozoo's links to Pouët and CSDb, and merges their summaries."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from handler.scan.merge import follow_demozoo_link, splice_scene_summaries
from handler.scan.sources import MetadataSource

LINKED_SOURCES = [
    pytest.param(MetadataSource.POUET, "pouet_id", id="pouet"),
    pytest.param(MetadataSource.CSDB, "csdb_id", id="csdb"),
]


def _handler_roms(
    source: MetadataSource, id_field: str, own: Any = None, linked: Any = None
) -> dict[MetadataSource, Any]:
    return {
        MetadataSource.DEMOZOO: {
            "demozoo_id": 1,
            "demozoo_metadata": {id_field: linked} if linked else {},
        },
        source: {id_field: own},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(("source", "id_field"), LINKED_SOURCES)
async def test_follows_the_linked_id(source: MetadataSource, id_field: str):
    handler_roms = _handler_roms(source, id_field, linked="42")
    get_rom_by_id = AsyncMock(return_value={id_field: 42, "name": "Linked"})

    await follow_demozoo_link(source, handler_roms, get_rom_by_id, [source])

    get_rom_by_id.assert_awaited_once_with(42)
    assert handler_roms[source] == {id_field: 42, "name": "Linked"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("source", "id_field"), LINKED_SOURCES)
async def test_keeps_a_match_the_scan_found_itself(
    source: MetadataSource, id_field: str
):
    handler_roms = _handler_roms(source, id_field, own=7, linked="42")
    get_rom_by_id = AsyncMock()

    await follow_demozoo_link(source, handler_roms, get_rom_by_id, [source])

    get_rom_by_id.assert_not_awaited()
    assert handler_roms[source] == {id_field: 7}


@pytest.mark.asyncio
@pytest.mark.parametrize(("source", "id_field"), LINKED_SOURCES)
async def test_a_failed_or_empty_follow_keeps_the_miss(
    source: MetadataSource, id_field: str
):
    for get_rom_by_id in (
        AsyncMock(side_effect=RuntimeError("down")),
        AsyncMock(return_value={id_field: None}),
    ):
        handler_roms = _handler_roms(source, id_field, linked="42")

        await follow_demozoo_link(source, handler_roms, get_rom_by_id, [source])

        assert handler_roms[source] == {id_field: None}


def test_splices_pouet_votes_links_and_the_csdb_page_into_demozoos_summary():
    handler_roms: dict[MetadataSource, Any] = {
        MetadataSource.DEMOZOO: {
            "demozoo_id": 1,
            "summary": "Party 1st",
            "demozoo_metadata": {"download_urls": ["https://a"]},
        },
        MetadataSource.POUET: {
            "pouet_id": 2,
            "summary": "Short",
            "pouet_metadata": {
                "vote_avg": 0.9,
                "download_urls": ["https://a", "https://b"],
                "youtube_video_id": "yt",
            },
        },
        MetadataSource.CSDB: {
            "csdb_id": 3,
            "csdb_metadata": {"csdb_url": "https://csdb/3"},
        },
    }

    splice_scene_summaries(handler_roms)

    demozoo = handler_roms[MetadataSource.DEMOZOO]
    assert demozoo["summary"].startswith("Party 1st")
    assert "Pouët" in demozoo["summary"]
    assert demozoo["summary"].endswith("https://csdb/3")
    assert handler_roms[MetadataSource.POUET]["summary"] == demozoo["summary"]
    assert demozoo["demozoo_metadata"]["download_urls"] == ["https://a", "https://b"]
    assert demozoo["demozoo_metadata"]["youtube_video_id"] == "yt"
