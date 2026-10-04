from typing import Any
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from fastapi import HTTPException

from handler.filesystem.base_handler import provider_language_name
from handler.metadata.base_handler import unavailable
from handler.metadata.hasheous_handler import (
    HasheousHandler,
    HasheousRom,
    _country_name,
    _tags_from_signatures,
    extract_metadata_from_igdb_rom,
)
from models.rom import RomFile

# The proxy keys expanded collections by id and returns `company` as a bare id,
# unlike IGDB's own list-of-objects shape.
PROXY_ROM = {
    "involved_companies": {
        "148214": {"id": 148214, "company": 70, "developer": True, "publisher": False},
        "225579": {"id": 225579, "company": 812, "developer": False, "publisher": True},
    },
}

IGDB_ROM = {
    "involved_companies": [
        {"company": {"name": "Retro Studios"}, "developer": True, "publisher": False},
        {"company": {"name": "Nintendo"}, "developer": False, "publisher": True},
    ],
}


def test_reads_the_proxys_dict_shaped_involvements():
    metadata = extract_metadata_from_igdb_rom(PROXY_ROM)

    assert metadata["companies"] == []
    assert metadata["publishers"] == []
    assert metadata["developers"] == []


def test_reads_igdbs_list_shaped_involvements():
    metadata = extract_metadata_from_igdb_rom(IGDB_ROM)

    assert metadata["publishers"] == ["Nintendo"]
    assert metadata["developers"] == ["Retro Studios"]


def test_involvements_are_optional():
    metadata = extract_metadata_from_igdb_rom({})

    assert metadata["publishers"] == []
    assert metadata["developers"] == []


def test_alternative_names_hold_every_title_the_proxy_returns():
    # Shaped as the proxy answers for IGDB game 427; a localization may have no name.
    metadata = extract_metadata_from_igdb_rom(
        {
            "name": "Final Fantasy VII",
            "alternative_names": {
                "52451": {"id": 52451, "name": "FFVII"},
                "2950": {"id": 2950, "name": "Финальная Фантазия 7"},
            },
            "game_localizations": {
                "2948": {"id": 2948, "name": "파이널 판타지 VII", "region": 2},
                "545": {"id": 545, "region": 4},
                "20": {"id": 20, "name": "FFVII", "region": 3},
            },
        }
    )

    assert metadata["alternative_names"] == [
        "Final Fantasy VII",
        "FFVII",
        "Финальная Фантазия 7",
        "파이널 판타지 VII",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        httpx2.HTTPStatusError(
            "boom",
            request=httpx2.Request("POST", "https://hasheous.org/api"),
            response=httpx2.Response(
                500, request=httpx2.Request("POST", "https://hasheous.org/api")
            ),
        ),
        httpx2.TimeoutException("too slow"),
    ],
    ids=["server_error", "timeout"],
)
async def test_request_propagates_an_unreachable_hasheous(failure: Exception):
    """A failed request has to stay distinguishable from a game Hasheous lacks."""
    handler = HasheousHandler()
    client = AsyncMock()
    client.request = AsyncMock(side_effect=failure)

    with (
        patch("handler.metadata.hasheous_handler.ctx_httpx_client") as ctx,
        pytest.raises(HTTPException),
    ):
        ctx.get.return_value = client
        await handler._request("https://hasheous.org/api")


# Shaped after a real /Lookup/ByHash answer: every signature source reports the
# matched dump under `rom`, with the game it belongs to beside it.
SIGNATURES = {
    "TOSEC": [
        {
            "game": {"country": {"EU": "Europe", "US": "United States"}},
            "rom": {"country": {"EU": "Europe"}, "language": {}},
        }
    ],
    "NoIntros": [
        {
            "game": {"country": {"EU": "Europe", "JP": "Japan", "US": "United States"}},
            "rom": {
                "country": {"US": "United States"},
                "language": {"en": "English"},
            },
        }
    ],
}


def _regions(signatures: dict[str, Any]) -> list[str]:
    return _tags_from_signatures(signatures, "country", _country_name)


def _languages(signatures: dict[str, Any]) -> list[str]:
    return _tags_from_signatures(signatures, "language", provider_language_name)


class TestTagsFromSignatures:
    """Region and language data for the dump a hash matched."""

    def test_prefers_the_curated_dump_over_the_other_sources(self):
        # TOSEC says Europe for the same hash; No-Intro wins.
        assert _regions(SIGNATURES) == ["USA"]

    def test_reads_the_language_of_the_matched_dump(self):
        assert _languages(SIGNATURES) == ["English"]

    def test_falls_through_to_a_source_that_has_the_field(self):
        signatures = {"TOSEC": SIGNATURES["TOSEC"], "NoIntros": [{"rom": {}}]}

        assert _regions(signatures) == ["Europe"]

    def test_resolves_a_code_romm_knows_rather_than_its_printed_name(self):
        signatures = {"NoIntros": [{"rom": {"country": {"wor": "", "JP": "Japan"}}}]}

        assert _regions(signatures) == ["World", "Japan"]

    def test_a_code_that_means_another_place_to_romm_uses_the_printed_name(self):
        # "CH" is Switzerland to Hasheous and China to a No-Intro filename.
        assert _regions(
            {"NoIntros": [{"rom": {"country": {"CH": "Switzerland"}}}]}
        ) == ["Switzerland"]

    def test_keeps_the_printed_name_of_a_code_romm_does_not_know(self):
        signatures = {"NoIntros": [{"rom": {"country": {"PL": "Poland"}}}]}

        assert _regions(signatures) == ["Poland"]

    def test_canonicalizes_the_printed_name_it_falls_back_to(self):
        signatures = {"NoIntros": [{"rom": {"country": {"XX": "japan"}}}]}

        assert _regions(signatures) == ["Japan"]

    def test_drops_a_bucket_that_names_no_region(self):
        # "ss" is a ScreenScraper bucket, and it comes with no display name.
        signatures = {
            "NoIntros": [{"rom": {"country": {"ss": "", "US": "United States"}}}]
        }

        assert _regions(signatures) == ["USA"]

    def test_a_game_only_match_reports_nothing(self):
        signatures = {"NoIntros": [{"game": {"country": {"US": "United States"}}}]}

        assert _regions(signatures) == []

    def test_no_signatures_report_nothing(self):
        assert _regions({}) == []

    @pytest.mark.parametrize(
        "signatures",
        [
            pytest.param({"NoIntros": {}}, id="source-is-not-a-list"),
            pytest.param({"NoIntros": ["TOSEC"]}, id="entry-is-not-an-object"),
            pytest.param({"NoIntros": [{"rom": []}]}, id="rom-is-an-empty-collection"),
            pytest.param(
                {"NoIntros": [{"rom": {"country": []}}]}, id="field-is-a-list"
            ),
            pytest.param(
                {"NoIntros": [{"rom": {"country": {"ZZ": None}}}]}, id="null-name"
            ),
        ],
    )
    def test_a_shape_hasheous_did_not_promise_reports_nothing(
        self, signatures: dict[str, Any]
    ):
        # A raise here would abort the scan of the rom, not just its tags.
        assert _regions(signatures) == []


# Trimmed from Hasheous' answer for "Final Fantasy VII (USA) (Disc 1).chd".
FF7_MATCH = {
    "id": 262307,
    "name": "Final Fantasy VII",
    "metadata": [
        {"source": "IGDB", "immutableId": "427"},
        {"source": "TheGamesDb", "immutableId": "525"},
        {"source": "RetroAchievements", "immutableId": "11242"},
    ],
    "signatures": {"MAMERedump": [{"rom": {"country": {"US": "United States"}}}]},
}


def _rom_file(sha1: str, size: int, extension: str = "chd") -> RomFile:
    file = RomFile(
        file_name=f"{sha1}.{extension}",
        file_path="psx/Game",
        file_size_bytes=size,
        sha1_hash=sha1,
    )
    # Pre-seeded so the file passes the top-level filter without a persisted rom.
    file.__dict__["is_top_level"] = True
    return file


class TestLookupRom:
    async def _lookup(
        self, files: list[RomFile], request: AsyncMock
    ) -> tuple[HasheousRom, bool]:
        handler = HasheousHandler()
        with (
            patch.object(HasheousHandler, "is_enabled", return_value=True),
            patch.object(handler, "_request", request),
        ):
            return await handler.lookup_rom("psx", files)

    @staticmethod
    def _sent(request: AsyncMock) -> list[list[dict[str, str]]]:
        return [call.kwargs["data"] for call in request.call_args_list]

    @pytest.mark.asyncio
    async def test_reads_the_ids_hasheous_maps_the_game_to(self):
        rom, conclusive = await self._lookup(
            [_rom_file("disc1", 700)], AsyncMock(return_value=FF7_MATCH)
        )

        assert conclusive
        assert rom["hasheous_id"] == 262307
        assert (rom["igdb_id"], rom["tgdb_id"]) == (427, 525)
        assert "ra_id" not in rom
        assert rom["hasheous_metadata"]["mame_redump_match"]

    @pytest.mark.asyncio
    async def test_leaves_the_playlist_out_of_the_lookup(self):
        request = AsyncMock(return_value=FF7_MATCH)
        await self._lookup(
            [_rom_file("playlist", 120, "m3u"), _rom_file("disc1", 700)], request
        )

        assert self._sent(request) == [[{"shA1": "disc1"}]]

    @pytest.mark.asyncio
    async def test_retries_each_file_alone_when_the_batch_misses(self):
        # One unknown hash in the batch is enough for Hasheous to miss it.
        request = AsyncMock(side_effect=[{}, FF7_MATCH, FF7_MATCH, {}])
        rom, conclusive = await self._lookup(
            [
                _rom_file("disc1", 700),
                _rom_file("disc2", 600),
                _rom_file("readme", 10, "txt"),
            ],
            request,
        )

        assert conclusive
        assert rom["hasheous_id"] == 262307
        assert self._sent(request) == [
            [{"shA1": "disc1"}, {"shA1": "disc2"}, {"shA1": "readme"}],
            [{"shA1": "disc1"}],
            [{"shA1": "disc2"}],
            [{"shA1": "readme"}],
        ]

    @pytest.mark.asyncio
    async def test_files_matching_different_games_match_neither(self):
        other_game = {**FF7_MATCH, "id": 1, "name": "Tobal No. 1"}
        request = AsyncMock(side_effect=[{}, FF7_MATCH, other_game, FF7_MATCH])
        rom, conclusive = await self._lookup(
            [
                _rom_file("disc1", 700),
                _rom_file("demo", 600),
                _rom_file("disc2", 500),
            ],
            request,
        )

        assert not conclusive
        assert rom["hasheous_id"] is None
        assert request.await_count == 3

    @pytest.mark.asyncio
    async def test_a_file_no_database_knows_is_a_conclusive_miss(self):
        request = AsyncMock(return_value={})
        rom, conclusive = await self._lookup(
            [_rom_file("disc1", 700), _rom_file("disc2", 600)], request
        )

        assert conclusive
        assert rom["hasheous_id"] is None
        assert request.await_count == 3

    @pytest.mark.asyncio
    async def test_a_failed_retry_is_inconclusive(self):
        request = AsyncMock(side_effect=[{}, unavailable("Hasheous")])
        rom, conclusive = await self._lookup(
            [_rom_file("disc1", 700), _rom_file("disc2", 600)], request
        )

        assert not conclusive
        assert rom["hasheous_id"] is None
