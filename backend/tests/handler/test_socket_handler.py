from contextlib import asynccontextmanager
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
import socketio
from tests.redis_stubs import fail_expire, record_pipelines

from handler.database import db_user_handler
from handler.redis_handler import async_cache, sync_cache
from handler.socket_handler import (
    DEVICES_NAMESPACE,
    LOGIN_SESSION_ID_KEY,
    SocketHandler,
    close_client_token_sockets,
    close_login_session_sockets,
    netplay_socket_handler,
    socket_handler,
)
from utils import auth as auth_utils
from utils import json_module


def test_netplay_cannot_join_the_main_servers_rooms():
    # Netplay clients may be anonymous and name their own rooms, so an emit to
    # `user:{id}` or `admin` must not reach a netplay socket that picked that name.
    netplay = netplay_socket_handler.socket_server.manager
    main = socket_handler.socket_server.manager
    assert netplay.channel != main.channel


class TestEmitToUser:
    async def test_targets_the_users_room_on_the_servers_channel(self, mocker):
        manager = MagicMock(emit=AsyncMock())
        make = mocker.patch.object(socketio, "AsyncRedisManager", return_value=manager)
        handler = SocketHandler(path="/test", channel="test-channel")

        await handler.emit_to_user(5, "notifications:read", {"ids": None})

        assert make.call_args.kwargs == {
            "channel": "test-channel",
            "write_only": True,
            "json": json_module,
        }
        manager.emit.assert_awaited_once_with(
            "notifications:read", {"ids": None}, room="user:5"
        )

    async def test_reuses_one_client_on_the_same_loop(self, mocker):
        manager = MagicMock(emit=AsyncMock())
        make = mocker.patch.object(socketio, "AsyncRedisManager", return_value=manager)
        handler = SocketHandler(path="/test")
        make.reset_mock()

        await handler.emit_to_user(5, "notifications:read", {"ids": None})
        await handler.emit_to_user(6, "notifications:read", {"ids": None})

        make.assert_called_once()
        assert manager.emit.await_count == 2

    async def test_swallows_a_broker_failure(self, mocker):
        manager = MagicMock(emit=AsyncMock(side_effect=ConnectionError("redis")))
        mocker.patch.object(socketio, "AsyncRedisManager", return_value=manager)
        handler = SocketHandler(path="/test")

        await handler.emit_to_user(5, "notifications:read", {"ids": None})


@pytest.fixture
def cache():
    sync_cache.flushall()
    yield async_cache
    sync_cache.flushall()


class TestLoginSessionSockets:
    async def test_binding_records_the_socket_both_ways(self, mocker, cache):
        handler = SocketHandler(path="/test")
        socket_session: dict[str, str] = {}

        @asynccontextmanager
        async def session(sid: str):
            yield socket_session

        mocker.patch.object(handler.socket_server, "session", session)
        await cache.set("session:s1", "{}")

        assert await handler.bind_to_login_session("sid-1", "s1")

        key = "session_sockets:socketio:s1"
        assert await cache.smembers(key) == {b"sid-1"}
        assert await cache.ttl(key) > 0
        assert socket_session == {LOGIN_SESSION_ID_KEY: "s1"}

    async def test_binding_is_one_transaction(self, mocker, cache):
        handler = SocketHandler(path="/test")

        @asynccontextmanager
        async def session(sid: str):
            yield {}

        mocker.patch.object(handler.socket_server, "session", session)
        await cache.set("session:s1", "{}")
        executed = record_pipelines(mocker)

        await handler.bind_to_login_session("sid-1", "s1")

        assert executed == [(True, ["SADD", "EXPIRE", "EXISTS"])]

    async def test_binding_to_a_revoked_session_binds_nothing(self, mocker, cache):
        """A socket that authenticated just before its session was revoked."""
        handler = SocketHandler(path="/test")
        socket_session: dict[str, str] = {}

        @asynccontextmanager
        async def session(sid: str):
            yield socket_session

        mocker.patch.object(handler.socket_server, "session", session)

        assert not await handler.bind_to_login_session("sid-1", "s1")

        assert not await cache.exists("session_sockets:socketio:s1")
        assert socket_session == {}

    async def test_closing_a_session_reads_and_deletes_in_one_transaction(
        self, mocker, cache
    ):
        handler = SocketHandler(path="/test")
        mocker.patch.object(handler.socket_server, "disconnect", AsyncMock())
        executed = record_pipelines(mocker)

        await handler.close_login_sessions(["s1"])

        assert executed == [(True, ["SMEMBERS", "DEL"])]

    async def test_a_failed_binding_leaves_no_set_without_a_ttl(self, mocker, cache):
        handler = SocketHandler(path="/test")
        fail_expire(mocker)

        with pytest.raises(ConnectionError):
            await handler.bind_to_login_session("sid-1", "s1")

        assert not await cache.exists("session_sockets:socketio:s1")

    async def test_unbinding_forgets_the_socket(self, mocker, cache):
        handler = SocketHandler(path="/test")
        mocker.patch.object(
            handler.socket_server,
            "get_session",
            AsyncMock(return_value={LOGIN_SESSION_ID_KEY: "s1"}),
        )
        await cache.sadd("session_sockets:socketio:s1", "sid-1", "sid-2")

        await handler.unbind_from_login_session("sid-1")

        assert await cache.smembers("session_sockets:socketio:s1") == {b"sid-2"}

    async def test_unbinding_an_anonymous_socket_touches_nothing(self, mocker, cache):
        handler = SocketHandler(path="/test")
        mocker.patch.object(
            handler.socket_server, "get_session", AsyncMock(return_value={})
        )
        await cache.sadd("session_sockets:socketio:s1", "sid-1")

        await handler.unbind_from_login_session("sid-1")

        assert await cache.smembers("session_sockets:socketio:s1") == {b"sid-1"}

    async def test_closing_a_session_disconnects_its_sockets(self, mocker, cache):
        handler = SocketHandler(path="/test")
        disconnect = mocker.patch.object(
            handler.socket_server, "disconnect", AsyncMock()
        )
        await cache.sadd("session_sockets:socketio:s1", "sid-1")

        await handler.close_login_sessions(["s1"])

        assert not await cache.exists("session_sockets:socketio:s1")
        disconnect.assert_awaited_once_with("sid-1", namespace=None)

    async def test_a_broker_failure_moves_on_to_the_next_session(self, mocker, cache):
        handler = SocketHandler(path="/test")
        disconnect = mocker.patch.object(
            handler.socket_server,
            "disconnect",
            AsyncMock(side_effect=[ConnectionError("redis"), None]),
        )
        await cache.sadd("session_sockets:socketio:s1", "sid-1")
        await cache.sadd("session_sockets:socketio:s2", "sid-2")

        await handler.close_login_sessions(["s1", "s2"])

        assert disconnect.await_count == 2

    async def test_each_server_keeps_its_own_sockets(self, mocker, cache):
        handler = SocketHandler(path="/test", channel="netplay")

        @asynccontextmanager
        async def session(sid: str):
            yield {}

        mocker.patch.object(handler.socket_server, "session", session)
        await cache.set("session:s1", "{}")

        await handler.bind_to_login_session("sid-1", "s1")

        assert await cache.smembers("session_sockets:netplay:s1") == {b"sid-1"}
        assert not await cache.exists("session_sockets:socketio:s1")


class TestTrackedSockets:
    async def test_tracking_adds_the_socket_and_renews_the_ttl(self, cache):
        handler = SocketHandler(path="/test")

        assert await handler.track("some:key", "sid-1", 90)

        assert await cache.smembers("some:key") == {b"sid-1"}
        assert 0 < await cache.ttl("some:key") <= 90

    async def test_tracking_while_a_key_is_gone_adds_nothing(self, cache):
        handler = SocketHandler(path="/test")

        assert not await handler.track("some:key", "sid-1", 90, while_exists="gone")

        assert not await cache.exists("some:key")

    async def test_untracking_drops_the_socket(self, cache):
        handler = SocketHandler(path="/test")

        await cache.sadd("some:key", "sid-1", "sid-2")

        await handler.untrack("some:key", "sid-1")

        assert await cache.smembers("some:key") == {b"sid-2"}

    async def test_untracking_swallows_a_broker_failure(self, mocker, cache):
        mocker.patch.object(cache, "srem", side_effect=ConnectionError("redis"))
        handler = SocketHandler(path="/test")

        await handler.untrack("some:key", "sid-1")

    async def test_closing_disconnects_on_the_given_namespace(self, mocker, cache):
        handler = SocketHandler(path="/test")
        disconnect = mocker.patch.object(
            handler.socket_server, "disconnect", AsyncMock()
        )
        await cache.sadd("some:key", "sid-1")

        await handler.close_tracked("some:key", "/devices")

        assert not await cache.exists("some:key")
        disconnect.assert_awaited_once_with("sid-1", namespace="/devices")

    async def test_a_failed_disconnect_still_closes_the_other_sockets(
        self, mocker, cache
    ):
        handler = SocketHandler(path="/test")

        async def fail_for_the_first(sid: str, namespace: str | None = None) -> None:
            if sid == "sid-1":
                raise ConnectionError("broker")

        disconnect = mocker.patch.object(
            handler.socket_server,
            "disconnect",
            AsyncMock(side_effect=fail_for_the_first),
        )
        await cache.sadd("some:key", "sid-1", "sid-2")

        await handler.close_tracked("some:key", "/devices")

        disconnect.assert_any_await("sid-2", namespace="/devices")
        assert disconnect.await_count == 2


class TestClientTokenSockets:
    async def test_closing_a_token_disconnects_its_device_sockets(self, mocker):
        close = mocker.patch.object(socket_handler, "close_tracked", AsyncMock())

        await close_client_token_sockets([42])

        close.assert_awaited_once_with("device_token_sockets:42", DEVICES_NAMESPACE)

    async def test_a_broker_failure_moves_on_to_the_next_token(self, mocker, cache):
        await cache.sadd("device_token_sockets:1", "sid-1")
        await cache.sadd("device_token_sockets:2", "sid-2")
        disconnect = mocker.patch.object(
            socket_handler.socket_server,
            "disconnect",
            AsyncMock(side_effect=[ConnectionError("redis"), None]),
        )

        await close_client_token_sockets([1, 2])

        assert disconnect.await_count == 2


async def test_revoking_a_session_closes_its_sockets_on_every_server(mocker):
    main = mocker.patch.object(socket_handler, "close_login_sessions", AsyncMock())
    netplay = mocker.patch.object(
        netplay_socket_handler, "close_login_sessions", AsyncMock()
    )

    await close_login_session_sockets(["s1"])

    main.assert_awaited_once_with(["s1"])
    netplay.assert_awaited_once_with(["s1"])


class TestAuthenticate:
    @pytest.fixture
    def handler(self) -> SocketHandler:
        return SocketHandler(path="/test")

    @pytest.fixture
    def bind(self, mocker, handler) -> AsyncMock:
        return cast(
            AsyncMock,
            mocker.patch.object(
                handler, "bind_to_login_session", AsyncMock(return_value=True)
            ),
        )

    @pytest.fixture
    def user(self, mocker) -> MagicMock:
        user = MagicMock(enabled=True)
        mocker.patch.object(db_user_handler, "get_user_by_username", return_value=user)
        return user

    def _session(self, mocker, **session) -> None:
        mocker.patch.object(
            auth_utils, "get_session_from_environ", AsyncMock(return_value=session)
        )

    async def test_resolves_and_binds_a_login_session(
        self, mocker, handler, bind, user
    ):
        self._session(mocker, iss="romm:auth", sub="sam", session_id="s1")

        assert await handler.authenticate("sid-1", {}) is user
        bind.assert_awaited_once_with("sid-1", "s1")

    async def test_rejects_a_session_revoked_while_binding(
        self, mocker, handler, bind, user
    ):
        bind.return_value = False
        self._session(mocker, iss="romm:auth", sub="sam", session_id="s1")

        assert await handler.authenticate("sid-1", {}) is None

    async def test_rejects_a_foreign_issuer(self, mocker, handler, bind, user):
        self._session(mocker, iss="other", sub="sam", session_id="s1")

        assert await handler.authenticate("sid-1", {}) is None
        bind.assert_not_awaited()

    async def test_rejects_a_disabled_user(self, mocker, handler, bind, user):
        user.enabled = False
        self._session(mocker, iss="romm:auth", sub="sam", session_id="s1")

        assert await handler.authenticate("sid-1", {}) is None
        bind.assert_not_awaited()
