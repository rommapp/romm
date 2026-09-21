from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from handler.filesystem.base_handler import (
    normalize_language,
    normalize_provider_languages,
    normalize_provider_regions,
)
from handler.metadata.hasheous_handler import (
    HasheousHandler,
    _country_name,
    _tags_from_signatures,
    extract_metadata_from_igdb_rom,
)

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        httpx.HTTPStatusError(
            "boom",
            request=httpx.Request("POST", "https://hasheous.org/api"),
            response=httpx.Response(
                500, request=httpx.Request("POST", "https://hasheous.org/api")
            ),
        ),
        httpx.TimeoutException("too slow"),
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


def _regions(signatures: dict) -> list[str]:
    return _tags_from_signatures(
        signatures, "country", _country_name, normalize_provider_regions
    )


def _languages(signatures: dict) -> list[str]:
    return _tags_from_signatures(
        signatures, "language", normalize_language, normalize_provider_languages
    )


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
    def test_a_shape_hasheous_did_not_promise_reports_nothing(self, signatures: dict):
        # A raise here would abort the scan of the rom, not just its tags.
        assert _regions(signatures) == []
