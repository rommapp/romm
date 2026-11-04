from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.factories import STEAM_ID

from adapters.services.steam import SteamOpenIDService

CLAIMED_ID = f"https://steamcommunity.com/openid/id/{STEAM_ID}"
RETURN_TO = "https://romm.example/api/users/1/steam/callback?state=abc"


def _response(body: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.text = AsyncMock(return_value=body)
    return response


@pytest.fixture
def session():
    mock_session = AsyncMock()
    with patch("adapters.services.steam.ctx_aiohttp_session") as mock_ctx:
        mock_ctx.get.return_value = mock_session
        yield mock_session


def test_the_login_url_asks_steam_to_pick_the_identity():
    url = SteamOpenIDService().login_url(
        return_to=RETURN_TO, realm="https://romm.example"
    )

    assert url.startswith("https://steamcommunity.com/openid/login?")
    assert "openid.mode=checkid_setup" in url
    assert "identifier_select" in url


async def test_an_assertion_steam_signs_yields_its_steam_id(session: AsyncMock):
    session.post.return_value = _response("ns:http://specs.openid.net/auth/2.0\nis_valid:true\n")

    steam_id = await SteamOpenIDService().verify(
        {"openid.mode": "id_res", "openid.claimed_id": CLAIMED_ID}
    )

    assert steam_id == STEAM_ID
    # Steam is asked to check its own signature, never taken at its word.
    assert session.post.await_args.kwargs["data"]["openid.mode"] == (
        "check_authentication"
    )


async def test_an_assertion_steam_rejects_yields_nothing(session: AsyncMock):
    session.post.return_value = _response("is_valid:false\n")

    assert (
        await SteamOpenIDService().verify(
            {"openid.mode": "id_res", "openid.claimed_id": CLAIMED_ID}
        )
        is None
    )


@pytest.mark.parametrize(
    "claimed_id",
    [
        "https://evil.example/openid/id/76561197960287930",
        "https://steamcommunity.com/openid/id/gabe",
        "https://steamcommunity.com/openid/id/123",
        "",
    ],
)
async def test_a_claimed_id_that_is_not_steams_yields_nothing(
    claimed_id: str, session: AsyncMock
):
    session.post.return_value = _response("is_valid:true\n")

    assert (
        await SteamOpenIDService().verify(
            {"openid.mode": "id_res", "openid.claimed_id": claimed_id}
        )
        is None
    )


async def test_a_query_without_openid_params_is_not_sent_to_steam(session: AsyncMock):
    assert await SteamOpenIDService().verify({"state": "abc"}) is None

    session.post.assert_not_awaited()


async def test_a_steam_that_cannot_be_reached_yields_nothing(session: AsyncMock):
    session.post.side_effect = TimeoutError()

    assert (
        await SteamOpenIDService().verify(
            {"openid.mode": "id_res", "openid.claimed_id": CLAIMED_ID}
        )
        is None
    )
