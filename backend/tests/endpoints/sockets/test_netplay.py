"""Authorization for the netplay socket namespace."""

from unittest.mock import AsyncMock, Mock

import pytest

from endpoints.sockets import netplay as netplay_module
from endpoints.sockets.netplay import (
    AUTH_USER_SESSION_KEY,
    connect,
    join_room,
    open_room,
    webrtc_signal,
)
from handler.auth.constants import Scope

ROM_ID = 42
PLATFORM_ID = 7
VISIBLE_ROM = Mock(id=ROM_ID, platform_id=PLATFORM_ID)


def _user(*scopes: Scope) -> Mock:
    user = Mock()
    user.id = 1
    user.enabled = True
    user.oauth_scopes = list(scopes)
    return user


def _room(**overrides) -> dict:
    room: dict = {
        "owner": "sid-owner",
        "players": {
            "owner": {
                "socketId": "sid-owner",
                "player_name": "Owner",
                "userid": "owner",
                "playerId": "owner",
            }
        },
        "peers": [],
        "room_name": "Room",
        "game_id": str(ROM_ID),
        "domain": None,
        "password": None,
        "max_players": 4,
    }
    room.update(overrides)
    return room


@pytest.fixture
def server(mocker):
    """The netplay socket server, with the session store stubbed per socket."""
    sessions: dict[str, dict] = {}

    async def get_session(sid: str) -> dict:
        if sid not in sessions:
            raise KeyError(sid)
        return sessions[sid]

    async def save_session(sid: str, session: dict) -> None:
        sessions[sid] = session

    socket_server = netplay_module.netplay_socket_handler.socket_server
    mocker.patch.object(
        socket_server, "get_session", AsyncMock(side_effect=get_session)
    )
    mocker.patch.object(
        socket_server, "save_session", AsyncMock(side_effect=save_session)
    )
    enter_room = mocker.patch.object(socket_server, "enter_room", AsyncMock())
    emit = mocker.patch.object(socket_server, "emit", AsyncMock())
    return Mock(sessions=sessions, enter_room=enter_room, emit=emit)


@pytest.fixture
def rooms(mocker):
    """The room store, plus the ROM and permission lookups the gate uses."""
    store: dict[str, dict] = {}
    handler = mocker.patch.object(netplay_module, "netplay_handler")

    async def get(session_id: str):
        return store.get(session_id)

    async def set_(session_id: str, room: dict) -> None:
        store[session_id] = room

    handler.get = AsyncMock(side_effect=get)
    handler.set = AsyncMock(side_effect=set_)
    handler.delete = AsyncMock()

    mocker.patch.object(
        netplay_module.db_rom_handler, "get_rom_visibility", return_value=VISIBLE_ROM
    )
    permissions = mocker.patch.object(netplay_module, "resolve_permissions")
    permissions.return_value.can_see_rom = Mock(return_value=True)
    return Mock(store=store, handler=handler, permissions=permissions)


def _open(sid: str, *, game_id: str | None = str(ROM_ID)) -> dict:
    extra: dict = {"sessionid": "room-1", "userid": "me"}
    if game_id is not None:
        extra["game_id"] = game_id
    return {"extra": extra}


def _join(sid: str, **extra_overrides) -> dict:
    extra = {"sessionid": "room-1", "userid": "me"}
    extra.update(extra_overrides)
    return {"extra": extra}


class TestOpenRoomAuthorization:
    async def test_rejects_unauthenticated(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        result = await open_room("sid", _open("sid"))

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()
        server.enter_room.assert_not_awaited()

    async def test_rejects_missing_roms_read(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ASSETS_READ)),
        )

        result = await open_room("sid", _open("sid"))

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_rejects_hidden_rom(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )
        rooms.permissions.return_value.can_see_rom = Mock(return_value=False)

        result = await open_room("sid", _open("sid"))

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_rejects_unknown_rom(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )
        mocker.patch.object(
            netplay_module.db_rom_handler, "get_rom_visibility", return_value=None
        )

        result = await open_room("sid", _open("sid"))

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_rejects_missing_game_id(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        result = await open_room("sid", _open("sid", game_id=None))

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_allows_visible_rom(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        assert await open_room("sid", _open("sid")) is None

        assert "room-1" in rooms.store
        server.enter_room.assert_awaited_once_with("sid", "room-1")
        server.emit.assert_awaited_once()

    async def test_keeps_the_connect_identity_in_the_room_session(
        self, mocker, server, rooms
    ):
        """The room keys and the connect-time identity share one session dict."""
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )
        server.sessions["sid"] = {AUTH_USER_SESSION_KEY: 1}

        await open_room("sid", _open("sid"))

        assert server.sessions["sid"][AUTH_USER_SESSION_KEY] == 1
        assert server.sessions["sid"]["session_id"] == "room-1"


class TestJoinRoomAuthorization:
    async def test_rejects_guest_without_a_password(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        result = await join_room("sid", _join("sid"))

        assert "Not authorized" in result
        server.enter_room.assert_not_awaited()

    async def test_rejects_guest_with_the_wrong_password(self, mocker, server, rooms):
        rooms.store["room-1"] = _room(password="s3cret")
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        result = await join_room("sid", _join("sid", room_password="guess"))

        assert result == "Incorrect password"
        server.enter_room.assert_not_awaited()

    async def test_allows_guest_with_the_correct_password(self, mocker, server, rooms):
        rooms.store["room-1"] = _room(password="s3cret")
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        assert await join_room("sid", _join("sid", room_password="s3cret")) is not None

        server.enter_room.assert_awaited_once_with("sid", "room-1")

    async def test_rejects_user_who_cannot_see_the_rom(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        rooms.permissions.return_value.can_see_rom = Mock(return_value=False)
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        result = await join_room("sid", _join("sid"))

        assert "Not authorized" in result
        server.enter_room.assert_not_awaited()

    async def test_allows_a_password_invite_for_a_hidden_rom(
        self, mocker, server, rooms
    ):
        """The room password is the owner's invite and stands in for the ROM gate."""
        rooms.store["room-1"] = _room(password="s3cret")
        rooms.permissions.return_value.can_see_rom = Mock(return_value=False)
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user()),
        )

        assert await join_room("sid", _join("sid", room_password="s3cret")) is not None

        server.enter_room.assert_awaited_once_with("sid", "room-1")

    async def test_allows_user_who_can_see_the_rom(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        joined = await join_room("sid", _join("sid"))

        assert joined is not None
        server.enter_room.assert_awaited_once_with("sid", "room-1")


class TestWebRtcSignalRelay:
    async def test_drops_a_signal_to_a_non_peer(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        server.sessions["sid"] = {"session_id": "room-1"}

        await webrtc_signal("sid", {"target": "sid-stranger", "offer": {"sdp": "x"}})

        server.emit.assert_not_awaited()

    async def test_relays_a_signal_to_a_peer(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        rooms.store["room-1"]["players"]["guest"] = {
            "socketId": "sid-peer",
            "player_name": "Guest",
            "userid": None,
            "playerId": "guest",
        }
        server.sessions["sid"] = {"session_id": "room-1"}

        await webrtc_signal("sid", {"target": "sid-peer", "offer": {"sdp": "x"}})

        server.emit.assert_awaited_once()
        assert server.emit.await_args.kwargs["to"] == "sid-peer"

    async def test_drops_a_signal_from_a_socket_with_no_room(
        self, mocker, server, rooms
    ):
        rooms.store["room-1"] = _room()

        await webrtc_signal("sid", {"target": "sid-owner", "offer": {"sdp": "x"}})

        server.emit.assert_not_awaited()


class TestEventWiring:
    """The gates only hold if they are attached to the netplay server, not `/ws`."""

    def test_handlers_are_registered_on_the_netplay_server(self):
        handlers = netplay_module.netplay_socket_handler.socket_server.handlers["/"]

        assert handlers["connect"] is connect
        for event in ("open-room", "join-room", "webrtc-signal"):
            assert event in handlers


class TestConnectIdentity:
    async def test_stores_identity_for_an_authenticated_session(self, mocker, server):
        mocker.patch.object(
            netplay_module,
            "get_session_from_environ",
            AsyncMock(return_value={"iss": "romm:auth", "sub": "sam"}),
        )
        user = _user(Scope.ROMS_READ)
        mocker.patch.object(
            netplay_module.db_user_handler, "get_user_by_username", return_value=user
        )

        await connect("sid", {})

        assert server.sessions["sid"][AUTH_USER_SESSION_KEY] == user.id

    async def test_leaves_an_anonymous_socket_unidentified(self, mocker, server):
        mocker.patch.object(
            netplay_module,
            "get_session_from_environ",
            AsyncMock(return_value={}),
        )

        await connect("sid", {})

        assert AUTH_USER_SESSION_KEY not in server.sessions.get("sid", {})

    async def test_never_refuses_the_connection(self, mocker, server):
        mocker.patch.object(
            netplay_module,
            "get_session_from_environ",
            AsyncMock(side_effect=RuntimeError("redis down")),
        )

        assert await connect("sid", {}) is None
