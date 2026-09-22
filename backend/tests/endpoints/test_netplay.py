"""The netplay room listing must not reveal rooms for a hidden rom."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from endpoints import netplay as netplay_endpoints
from handler.auth import oauth_handler
from handler.auth.constants import Scope
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity


def _auth(user, scopes=None):
    # Re-reads the user's current (projected) scopes each call.
    token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(scopes if scopes is not None else user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    return {"Authorization": f"Bearer {token}"}


def _hide(entity, entity_id, user_id):
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


def _room(rom_id: int) -> dict:
    return {
        "owner": "sid",
        "players": {
            "p": {
                "socketId": "sid",
                "player_name": "Player p",
                "userid": None,
                "playerId": "p",
            }
        },
        "peers": [],
        "room_name": "Room",
        "game_id": str(rom_id),
        "domain": None,
        "password": None,
        "max_players": 4,
    }


@pytest.fixture
def rooms(mocker):
    return mocker.patch.object(
        netplay_endpoints.netplay_handler, "get_all", AsyncMock(return_value={})
    )


def test_listing_shows_rooms_for_a_visible_rom(client, viewer_user, rom, rooms):
    rooms.return_value = {"room-1": _room(rom.id)}

    resp = client.get(f"/api/netplay/list?game_id={rom.id}", headers=_auth(viewer_user))

    assert resp.status_code == 200
    assert "room-1" in resp.json()


def test_listing_hides_rooms_for_a_hidden_rom(client, viewer_user, rom, rooms):
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    rooms.return_value = {"room-1": _room(rom.id)}

    resp = client.get(f"/api/netplay/list?game_id={rom.id}", headers=_auth(viewer_user))

    assert resp.status_code == 200
    assert resp.json() == {}
    rooms.assert_not_awaited()


def test_listing_of_a_missing_rom_is_empty(client, viewer_user, rooms):
    resp = client.get("/api/netplay/list?game_id=999999", headers=_auth(viewer_user))

    assert resp.status_code == 200
    assert resp.json() == {}


def test_listing_needs_the_rom_read_scope(client, viewer_user, rooms):
    """The listing answers about a rom, so asset access alone is not enough."""
    headers = _auth(viewer_user, scopes=[Scope.ASSETS_READ])

    resp = client.get("/api/netplay/list?game_id=1", headers=headers)

    assert resp.status_code == 403
    rooms.assert_not_awaited()
