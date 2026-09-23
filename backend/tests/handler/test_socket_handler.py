from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from handler import socket_handler as socket_handler_module
from handler.socket_handler import (
    LOGIN_SESSION_ID_KEY,
    SocketHandler,
    netplay_socket_handler,
    socket_handler,
)


def test_netplay_cannot_join_the_main_servers_rooms():
    # Netplay clients are unauthenticated and name their own rooms, so an emit to
    # `user:{id}` or `admin` must not reach a netplay socket that picked that name.
    netplay = netplay_socket_handler.socket_server.manager
    main = socket_handler.socket_server.manager
    assert netplay.channel != main.channel


class TestEmitToUser:
    async def test_targets_the_users_room_on_the_servers_channel(self, mocker):
        manager = MagicMock(emit=AsyncMock())
        make = mocker.patch.object(
            socket_handler_module.socketio, "AsyncRedisManager", return_value=manager
        )
        handler = SocketHandler(path="/test", channel="test-channel")

        await handler.emit_to_user(5, "notifications:read", {"ids": None})

        assert make.call_args.kwargs == {
            "channel": "test-channel",
            "write_only": True,
            "json": socket_handler_module.json_module,
        }
        manager.emit.assert_awaited_once_with(
            "notifications:read", {"ids": None}, room="user:5"
        )

    async def test_reuses_one_client_on_the_same_loop(self, mocker):
        manager = MagicMock(emit=AsyncMock())
        make = mocker.patch.object(
            socket_handler_module.socketio, "AsyncRedisManager", return_value=manager
        )
        handler = SocketHandler(path="/test")
        make.reset_mock()

        await handler.emit_to_user(5, "notifications:read", {"ids": None})
        await handler.emit_to_user(6, "notifications:read", {"ids": None})

        make.assert_called_once()
        assert manager.emit.await_count == 2

    async def test_swallows_a_broker_failure(self, mocker):
        manager = MagicMock(emit=AsyncMock(side_effect=ConnectionError("redis")))
        mocker.patch.object(
            socket_handler_module.socketio, "AsyncRedisManager", return_value=manager
        )
        handler = SocketHandler(path="/test")

        await handler.emit_to_user(5, "notifications:read", {"ids": None})


@pytest.fixture
def cache(mocker):
    cache = MagicMock(
        sadd=AsyncMock(),
        srem=AsyncMock(),
        expire=AsyncMock(),
        delete=AsyncMock(),
        smembers=AsyncMock(return_value=set()),
    )
    mocker.patch.object(socket_handler_module, "async_cache", cache)
    return cache


class TestLoginSessionSockets:
    async def test_binding_records_the_socket_both_ways(self, mocker, cache):
        handler = SocketHandler(path="/test")
        socket_session: dict[str, str] = {}

        @asynccontextmanager
        async def session(sid: str):
            yield socket_session

        mocker.patch.object(handler.socket_server, "session", session)

        await handler.bind_to_login_session("sid-1", "s1")

        cache.sadd.assert_awaited_once_with("session_sockets:s1", "sid-1")
        cache.expire.assert_awaited_once()
        assert socket_session == {LOGIN_SESSION_ID_KEY: "s1"}

    async def test_unbinding_forgets_the_socket(self, mocker, cache):
        handler = SocketHandler(path="/test")
        mocker.patch.object(
            handler.socket_server,
            "get_session",
            AsyncMock(return_value={LOGIN_SESSION_ID_KEY: "s1"}),
        )

        await handler.unbind_from_login_session("sid-1")

        cache.srem.assert_awaited_once_with("session_sockets:s1", "sid-1")

    async def test_unbinding_an_anonymous_socket_touches_nothing(self, mocker, cache):
        handler = SocketHandler(path="/test")
        mocker.patch.object(
            handler.socket_server, "get_session", AsyncMock(return_value={})
        )

        await handler.unbind_from_login_session("sid-1")

        cache.srem.assert_not_awaited()

    async def test_closing_a_session_disconnects_its_sockets(self, mocker, cache):
        handler = SocketHandler(path="/test")
        disconnect = mocker.patch.object(
            handler.socket_server, "disconnect", AsyncMock()
        )
        cache.smembers.return_value = {b"sid-1"}

        await handler.close_login_sessions(["s1"])

        cache.delete.assert_awaited_once_with("session_sockets:s1")
        disconnect.assert_awaited_once_with("sid-1")

    async def test_a_broker_failure_moves_on_to_the_next_session(self, mocker, cache):
        handler = SocketHandler(path="/test")
        disconnect = mocker.patch.object(
            handler.socket_server,
            "disconnect",
            AsyncMock(side_effect=[ConnectionError("redis"), None]),
        )
        cache.smembers.side_effect = [{"sid-1"}, {"sid-2"}]

        await handler.close_login_sessions(["s1", "s2"])

        assert disconnect.await_count == 2
