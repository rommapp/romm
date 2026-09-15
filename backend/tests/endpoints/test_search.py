"""What one unreachable provider costs a metadata search.

The providers are gathered together, so an error from any one of them used to
take the whole dialog down with it.
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from exceptions.endpoint_exceptions import SGDBInvalidAPIKeyException
from handler.metadata.base_handler import CoverResource, CoverResult
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.moby_handler import MobyGamesRom
from handler.metadata.ss_handler import SSRom
from handler.metadata.steam_handler import SteamRom
from handler.scan_handler import MetadataSource

DOWN = HTTPException(status_code=503, detail="provider is down")

# Every provider the search gathers, and a name match to hand back for each.
_BY_NAME = {
    "meta_igdb_handler": [IGDBRom(igdb_id=1, name="From IGDB")],
    "meta_moby_handler": [MobyGamesRom(moby_id=2, name="From MobyGames")],
    "meta_ss_handler": [SSRom(ss_id=3, name="From ScreenScraper")],
    "meta_flashpoint_handler": [],
    "meta_launchbox_handler": [],
    "meta_demozoo_handler": [],
    "meta_steam_handler": [
        SteamRom(steam_id=4, name="From Steam", url_cover="https://cdn/4.jpg")
    ],
}


def _search(client, access_token, rom, failing: str | None):
    """Search by name with every provider enabled, failing the named one."""
    patches = [
        patch(
            f"endpoints.search.{handler}.get_matched_roms_by_name",
            new=AsyncMock(
                side_effect=DOWN if handler == failing else None,
                return_value=matches,
            ),
        )
        for handler, matches in _BY_NAME.items()
    ]
    with patch("endpoints.search.meta_igdb_handler.is_enabled", return_value=True):
        for p in patches:
            p.start()
        try:
            return client.get(
                f"/api/search/roms?rom_id={rom.id}&search_term=Sonic&search_by=name",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        finally:
            for p in patches:
                p.stop()


def test_a_failing_provider_costs_only_its_own_matches(client, access_token, rom):
    response = _search(client, access_token, rom, failing="meta_igdb_handler")

    assert response.status_code == status.HTTP_200_OK
    names = {match["name"] for match in response.json()}
    assert "From IGDB" not in names
    assert {"From MobyGames", "From ScreenScraper"} <= names


@pytest.mark.parametrize("failing", sorted(_BY_NAME))
def test_no_single_provider_can_take_the_search_down(
    client, access_token, rom, failing
):
    response = _search(client, access_token, rom, failing=failing)

    assert response.status_code == status.HTTP_200_OK


def test_steam_matches_carry_their_id_and_cover(client, access_token, rom):
    """Steam joins the picker, so a PC library can be matched to the store."""
    response = _search(client, access_token, rom, failing=None)

    assert response.status_code == status.HTTP_200_OK
    steam_match = next(
        match for match in response.json() if match["name"] == "From Steam"
    )
    assert steam_match["steam_id"] == 4
    assert steam_match["steam_url_cover"] == "https://cdn/4.jpg"


def test_a_failing_provider_costs_only_its_own_match_when_searching_by_id(
    client, access_token, rom
):
    with (
        patch("endpoints.search.meta_igdb_handler.is_enabled", return_value=True),
        patch(
            "endpoints.search.meta_igdb_handler.get_matched_rom_by_id",
            new=AsyncMock(side_effect=DOWN),
        ),
        patch(
            "endpoints.search.meta_ss_handler.get_matched_rom_by_id",
            new=AsyncMock(return_value=SSRom(ss_id=3, name="From ScreenScraper")),
        ),
        patch(
            "endpoints.search.meta_moby_handler.get_matched_rom_by_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "endpoints.search.meta_launchbox_handler.get_matched_rom_by_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "endpoints.search.meta_demozoo_handler.get_rom_by_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "endpoints.search.meta_steam_handler.get_matched_rom_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = client.get(
            f"/api/search/roms?rom_id={rom.id}&search_term=3&search_by=id",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert [match["name"] for match in response.json()] == ["From ScreenScraper"]


def test_a_non_numeric_id_is_still_a_client_error(client, access_token, rom):
    """return_exceptions must not swallow the ValueError from int(search_term):
    the gather never starts, so the endpoint still reports the bad input."""
    response = client.get(
        f"/api/search/roms?rom_id={rom.id}&search_term=not-a-number&search_by=id",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def _cover(name: str, url: str) -> CoverResult:
    return CoverResult(
        name=name,
        resources=[
            CoverResource(
                thumb=url,
                url=url,
                type="static",
                width=600,
                height=900,
                style="",
                author="",
                score=0,
                nsfw=False,
                humor=False,
                epilepsy=False,
            )
        ],
    )


def _search_covers(
    client, access_token, *, sgdb, steam, cover_priority=None, sgdb_enabled=True
):
    """Search covers with the providers answering as given: a result list,
    or an exception (instance or class) the handler raises."""
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "endpoints.search.meta_sgdb_handler.is_enabled",
                return_value=sgdb_enabled,
            )
        )
        stack.enter_context(
            patch("endpoints.search.meta_steam_handler.is_enabled", return_value=True)
        )
        for handler, answer in (("sgdb", sgdb), ("steam", steam)):
            raises = isinstance(answer, Exception) or isinstance(answer, type)
            stack.enter_context(
                patch(
                    f"endpoints.search.meta_{handler}_handler.get_details",
                    new=AsyncMock(
                        side_effect=answer if raises else None,
                        return_value=answer,
                    ),
                )
            )
        if cover_priority:
            stack.enter_context(
                patch(
                    "endpoints.search.get_priority_ordered_metadata_sources",
                    return_value=cover_priority,
                )
            )
        return client.get(
            "/api/search/cover?search_term=Blur",
            headers={"Authorization": f"Bearer {access_token}"},
        )


def test_cover_search_merges_every_provider_tagged_by_source(client, access_token):
    response = _search_covers(
        client,
        access_token,
        sgdb=[_cover("Blur", "https://sgdb/1.png")],
        steam=[_cover("Blur", "https://steam/1.jpg")],
    )

    assert response.status_code == status.HTTP_200_OK
    assert [(c["provider"], c["resources"][0]["url"]) for c in response.json()] == [
        ("sgdb", "https://sgdb/1.png"),
        ("steam", "https://steam/1.jpg"),
    ]


def test_cover_search_follows_the_configured_cover_priority(client, access_token):
    response = _search_covers(
        client,
        access_token,
        sgdb=[_cover("Blur", "https://sgdb/1.png")],
        steam=[_cover("Blur", "https://steam/1.jpg")],
        cover_priority=[MetadataSource.STEAM, MetadataSource.SGDB],
    )

    assert [c["provider"] for c in response.json()] == ["steam", "sgdb"]


def test_a_failing_cover_provider_costs_only_its_own_covers(client, access_token):
    response = _search_covers(
        client, access_token, sgdb=DOWN, steam=[_cover("Blur", "https://steam/1.jpg")]
    )

    assert response.status_code == status.HTTP_200_OK
    assert [c["provider"] for c in response.json()] == ["steam"]


def test_an_invalid_sgdb_key_is_still_reported(client, access_token):
    """The adapter raises the class itself, whose constructor surfaces the 401."""
    response = _search_covers(
        client, access_token, sgdb=SGDBInvalidAPIKeyException, steam=[]
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_steam_alone_keeps_the_cover_search_open(client, access_token):
    response = _search_covers(
        client,
        access_token,
        sgdb=[],
        steam=[_cover("Blur", "https://steam/1.jpg")],
        sgdb_enabled=False,
    )

    assert response.status_code == status.HTTP_200_OK
    assert [c["provider"] for c in response.json()] == ["steam"]


def test_cover_search_needs_one_cover_provider(client, access_token):
    with (
        patch("endpoints.search.meta_sgdb_handler.is_enabled", return_value=False),
        patch("endpoints.search.meta_steam_handler.is_enabled", return_value=False),
    ):
        response = client.get(
            "/api/search/cover?search_term=Blur",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
