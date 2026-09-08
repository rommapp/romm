"""What one unreachable provider costs a metadata search.

The providers are gathered together, so an error from any one of them used to
take the whole dialog down with it.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.moby_handler import MobyGamesRom
from handler.metadata.ss_handler import SSRom

DOWN = HTTPException(status_code=503, detail="provider is down")

# Every provider the search gathers, and a name match to hand back for each.
_BY_NAME = {
    "meta_igdb_handler": [IGDBRom(igdb_id=1, name="From IGDB")],
    "meta_moby_handler": [MobyGamesRom(moby_id=2, name="From MobyGames")],
    "meta_ss_handler": [SSRom(ss_id=3, name="From ScreenScraper")],
    "meta_flashpoint_handler": [],
    "meta_launchbox_handler": [],
    "meta_demozoo_handler": [],
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
