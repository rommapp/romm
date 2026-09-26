"""Authorization for the netplay socket namespace."""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from endpoints.netplay import DEFAULT_MAX_PLAYERS
from endpoints.sockets import netplay as netplay_module
from endpoints.sockets.netplay import (
    AUTH_USER_SESSION_KEY,
    RoomData,
    RoomDataExtra,
    connect,
    data_message,
    disconnect,
    join_room,
    leave_room,
    open_room,
    webrtc_signal,
)
from handler.auth.constants import Scope
from handler.database import db_rom_handler, db_user_handler
from handler.netplay_handler import NetplayPlayerInfo, NetplayRoom
from handler.socket_handler import netplay_socket_handler

ROM_ID = 42
PLATFORM_ID = 7
VISIBLE_ROM = Mock(id=ROM_ID, platform_id=PLATFORM_ID)
ROOM_1 = netplay_module._socket_room("room-1")


def _user(*scopes: Scope) -> Mock:
    user = Mock()
    user.id = 1
    user.enabled = True
    user.oauth_scopes = list(scopes)
    return user


def _player(socket_id: str, name: str, player_id: str) -> NetplayPlayerInfo:
    return NetplayPlayerInfo(
        socketId=socket_id,
        player_name=name,
        userid=player_id,
        playerId=player_id,
    )


def _room(
    *,
    password: str | None = None,
    players: dict[str, NetplayPlayerInfo] | None = None,
) -> NetplayRoom:
    return NetplayRoom(
        owner="sid-owner",
        players=players
        or {
            "owner": _player("sid-owner", "Owner", "owner"),
            "me": _player("sid", "Me", "me"),
        },
        peers=[],
        room_name="Room",
        game_id=str(ROM_ID),
        domain=None,
        password=password,
        max_players=4,
    )


@pytest.fixture
def server(mocker) -> Mock:
    """The netplay socket server, with the session store stubbed per socket."""
    sessions: dict[str, dict[str, Any]] = {}

    async def get_session(sid: str) -> dict[str, Any]:
        if sid not in sessions:
            raise KeyError(sid)
        return sessions[sid]

    async def save_session(sid: str, session: dict[str, Any]) -> None:
        sessions[sid] = session

    socket_server = netplay_socket_handler.socket_server
    mocker.patch.object(
        socket_server, "get_session", AsyncMock(side_effect=get_session)
    )
    mocker.patch.object(
        socket_server, "save_session", AsyncMock(side_effect=save_session)
    )
    enter_room = mocker.patch.object(socket_server, "enter_room", AsyncMock())
    leave_room_event = mocker.patch.object(socket_server, "leave_room", AsyncMock())
    emit = mocker.patch.object(socket_server, "emit", AsyncMock())
    return Mock(
        sessions=sessions,
        enter_room=enter_room,
        leave_room=leave_room_event,
        emit=emit,
    )


@pytest.fixture
def rooms(mocker) -> Mock:
    """The room store, plus the ROM and permission lookups the gate uses."""
    store: dict[str, NetplayRoom] = {}
    handler = mocker.patch.object(netplay_module, "netplay_handler")

    async def get(session_id: str) -> NetplayRoom | None:
        return store.get(session_id)

    async def set_(session_id: str, room: NetplayRoom) -> None:
        store[session_id] = room

    handler.get = AsyncMock(side_effect=get)
    handler.set = AsyncMock(side_effect=set_)
    handler.delete = AsyncMock()

    mocker.patch.object(db_rom_handler, "get_rom_visibility", return_value=VISIBLE_ROM)
    permissions = mocker.patch.object(netplay_module, "resolve_permissions")
    permissions.return_value.can_see_rom = Mock(return_value=True)
    return Mock(store=store, handler=handler, permissions=permissions)


def _open(
    *,
    game_id: str | None = str(ROM_ID),
    session_id: str = "room-1",
    password: str | None = None,
) -> RoomData:
    extra = RoomDataExtra(sessionid=session_id, userid="me", playerId=None)
    if game_id is not None:
        extra["game_id"] = game_id
    data = RoomData(extra=extra)
    if password is not None:
        data["password"] = password
    return data


def _join(*, password: str | None = None, player_id: str = "guest") -> RoomData:
    extra = RoomDataExtra(sessionid="room-1", userid=player_id, playerId=None)
    data = RoomData(extra=extra)
    if password is not None:
        data["password"] = password
    return data


@pytest.fixture
def authorized(mocker) -> None:
    mocker.patch.object(
        netplay_module,
        "_authenticated_user",
        AsyncMock(return_value=_user(Scope.ROMS_READ)),
    )


class TestOpenRoomAuthorization:
    async def test_rejects_unauthenticated(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        result = await open_room("sid", _open())

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()
        server.enter_room.assert_not_awaited()

    async def test_rejects_missing_roms_read(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ASSETS_READ)),
        )

        result = await open_room("sid", _open())

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_rejects_a_user_disabled_after_connecting(
        self, mocker, server, rooms
    ):
        """The identity is reloaded per call, so a disable lands without a reconnect."""
        disabled = _user(Scope.ROMS_READ)
        disabled.enabled = False
        mocker.patch.object(db_user_handler, "get_user", return_value=disabled)
        server.sessions["sid"] = {AUTH_USER_SESSION_KEY: 1}

        result = await open_room("sid", _open())

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_rejects_hidden_rom(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )
        rooms.permissions.return_value.can_see_rom = Mock(return_value=False)

        result = await open_room("sid", _open())

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_rejects_unknown_rom(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )
        mocker.patch.object(db_rom_handler, "get_rom_visibility", return_value=None)

        result = await open_room("sid", _open())

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_rejects_missing_game_id(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        result = await open_room("sid", _open(game_id=None))

        assert "Not authorized" in result
        rooms.handler.set.assert_not_awaited()

    async def test_allows_visible_rom(self, mocker, server, rooms):
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        assert await open_room("sid", _open()) is None

        assert "room-1" in rooms.store
        server.enter_room.assert_awaited_once_with("sid", ROOM_1)
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

        await open_room("sid", _open())

        assert server.sessions["sid"][AUTH_USER_SESSION_KEY] == 1
        assert server.sessions["sid"]["session_id"] == "room-1"


class TestJoinRoomAuthorization:
    async def test_rejects_guest_without_a_password(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        result = await join_room("sid", _join())

        assert "Not authorized" in result
        server.enter_room.assert_not_awaited()

    async def test_rejects_guest_with_the_wrong_password(self, mocker, server, rooms):
        rooms.store["room-1"] = _room(password="s3cret")
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        result = await join_room("sid", _join(password="guess"))

        assert result == "Incorrect password"
        server.enter_room.assert_not_awaited()

    async def test_allows_guest_with_the_correct_password(self, mocker, server, rooms):
        rooms.store["room-1"] = _room(password="s3cret")
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        assert await join_room("sid", _join(password="s3cret")) is not None

        server.enter_room.assert_awaited_once_with("sid", ROOM_1)

    async def test_rejects_user_who_cannot_see_the_rom(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        rooms.permissions.return_value.can_see_rom = Mock(return_value=False)
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        result = await join_room("sid", _join())

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

        assert await join_room("sid", _join(password="s3cret")) is not None

        server.enter_room.assert_awaited_once_with("sid", ROOM_1)

    async def test_allows_user_who_can_see_the_rom(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        mocker.patch.object(
            netplay_module,
            "_authenticated_user",
            AsyncMock(return_value=_user(Scope.ROMS_READ)),
        )

        joined = await join_room("sid", _join())

        assert joined is not None
        server.enter_room.assert_awaited_once_with("sid", ROOM_1)


class TestWebRtcSignalRelay:
    async def test_drops_a_signal_to_a_non_peer(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        server.sessions["sid"] = {"session_id": "room-1"}

        await webrtc_signal("sid", {"target": "sid-stranger", "offer": {"sdp": "x"}})

        server.emit.assert_not_awaited()

    async def test_relays_a_signal_to_a_peer(self, mocker, server, rooms):
        rooms.store["room-1"] = _room()
        rooms.store["room-1"]["players"]["guest"] = NetplayPlayerInfo(
            socketId="sid-peer",
            player_name="Guest",
            userid=None,
            playerId="guest",
        )
        server.sessions["sid"] = {"session_id": "room-1"}

        await webrtc_signal("sid", {"target": "sid-peer", "offer": {"sdp": "x"}})

        server.emit.assert_awaited_once()
        await_args = server.emit.await_args
        assert await_args is not None
        assert await_args.kwargs["to"] == "sid-peer"

    async def test_drops_a_signal_from_a_socket_with_no_room(
        self, mocker, server, rooms
    ):
        rooms.store["room-1"] = _room()

        await webrtc_signal("sid", {"target": "sid-owner", "offer": {"sdp": "x"}})

        server.emit.assert_not_awaited()

    async def test_drops_a_signal_from_a_socket_that_is_not_a_player(
        self, mocker, server, rooms
    ):
        """A room id in the session is not enough; the sender must still be a player."""
        rooms.store["room-1"] = _room(
            players={"owner": _player("sid-owner", "Owner", "owner")}
        )
        server.sessions["sid"] = {"session_id": "room-1"}

        await webrtc_signal("sid", {"target": "sid-owner", "offer": {"sdp": "x"}})

        server.emit.assert_not_awaited()


class TestLeaveRoom:
    async def test_clears_the_room_session_keys(self, server, rooms):
        rooms.store["room-1"] = _room()
        server.sessions["sid"] = {"session_id": "room-1", "player_id": "me"}

        await leave_room("sid")

        assert "session_id" not in server.sessions["sid"]
        assert "player_id" not in server.sessions["sid"]

    async def test_stops_broadcasting_after_leaving(self, server, rooms):
        rooms.store["room-1"] = _room()
        server.sessions["sid"] = {"session_id": "room-1", "player_id": "me"}

        await leave_room("sid")
        server.emit.reset_mock()

        await data_message("sid", {"frame": 1})

        server.emit.assert_not_awaited()


class TestRoomPassword:
    """EmulatorJS sends the password beside ``extra``, not inside it."""

    async def test_open_room_stores_the_password(self, server, rooms, authorized):
        await open_room("sid", _open(password="s3cret"))

        assert rooms.store["room-1"]["password"] == "s3cret"

    async def test_join_accepts_the_password(self, mocker, server, rooms):
        rooms.store["room-1"] = _room(password="s3cret")
        mocker.patch.object(
            netplay_module, "_authenticated_user", AsyncMock(return_value=None)
        )

        assert await join_room("sid", _join(password="s3cret")) is not None

        server.enter_room.assert_awaited_once_with("sid", ROOM_1)

    async def test_join_without_the_password_is_refused_even_with_rom_access(
        self, server, rooms, authorized
    ):
        rooms.store["room-1"] = _room(password="s3cret")

        assert await join_room("sid", _join()) == "Incorrect password"

        server.enter_room.assert_not_awaited()


class TestRoomIsolation:
    async def test_a_room_id_cannot_name_another_sockets_own_room(
        self, server, rooms, authorized
    ):
        await open_room("sid", _open(session_id="sid-victim"))

        server.enter_room.assert_awaited_once_with(
            "sid", netplay_module._socket_room("sid-victim")
        )

    async def test_join_refuses_a_player_id_already_seated(
        self, server, rooms, authorized
    ):
        rooms.store["room-1"] = _room()

        assert await join_room("sid-2", _join(player_id="owner")) == (
            "Player already in room"
        )

        assert rooms.store["room-1"]["players"]["owner"]["socketId"] == "sid-owner"
        server.enter_room.assert_not_awaited()

    async def test_joining_another_room_leaves_the_current_one(
        self, server, rooms, authorized
    ):
        rooms.store["room-0"] = _room()
        rooms.store["room-1"] = _room(
            players={"owner": _player("sid-owner", "Owner", "owner")}
        )
        server.sessions["sid"] = {"session_id": "room-0", "player_id": "me"}

        assert await join_room("sid", _join()) is not None

        assert "me" not in rooms.store["room-0"]["players"]
        server.leave_room.assert_awaited_once_with(
            "sid", netplay_module._socket_room("room-0")
        )

    async def test_a_malformed_max_players_falls_back_to_the_default(
        self, server, rooms, authorized
    ):
        data: Any = _open()
        data["maxPlayers"] = "lots"

        await open_room("sid", data)

        assert rooms.store["room-1"]["max_players"] == DEFAULT_MAX_PLAYERS

    async def test_stores_the_rom_id_the_gate_resolved(self, server, rooms, authorized):
        await open_room("sid", _open(game_id=f" {ROM_ID}"))

        assert rooms.store["room-1"]["game_id"] == str(ROM_ID)


class TestLoginSessionBinding:
    """Revoking a login session must close the netplay sockets it opened."""

    async def test_disconnect_forgets_the_binding(self, mocker, server, rooms):
        unbind = mocker.patch.object(
            netplay_socket_handler,
            "unbind_from_login_session",
            AsyncMock(),
        )

        await disconnect("sid")

        unbind.assert_awaited_once_with("sid")


class TestEventWiring:
    """The gates only hold if they are attached to the netplay server, not `/ws`."""

    def test_handlers_are_registered_on_the_netplay_server(self):
        handlers = netplay_socket_handler.socket_server.handlers["/"]

        assert handlers["connect"] is connect
        assert handlers["disconnect"] is disconnect
        for event in ("open-room", "join-room", "webrtc-signal"):
            assert event in handlers


class TestConnectIdentity:
    @pytest.fixture
    def authenticate(self, mocker) -> AsyncMock:
        return mocker.patch.object(netplay_socket_handler, "authenticate", AsyncMock())

    async def test_stores_identity_for_an_authenticated_session(
        self, server, authenticate
    ):
        user = _user(Scope.ROMS_READ)
        authenticate.return_value = user

        await connect("sid", {"HTTP_COOKIE": "c"})

        authenticate.assert_awaited_once_with("sid", {"HTTP_COOKIE": "c"})
        assert server.sessions["sid"][AUTH_USER_SESSION_KEY] == user.id

    async def test_leaves_an_anonymous_socket_unidentified(self, server, authenticate):
        authenticate.return_value = None

        await connect("sid", {})

        assert AUTH_USER_SESSION_KEY not in server.sessions.get("sid", {})

    async def test_never_refuses_the_connection(self, server, authenticate):
        authenticate.side_effect = RuntimeError("redis down")

        assert await connect("sid", {}) is None
