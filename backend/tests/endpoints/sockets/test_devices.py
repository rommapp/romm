from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from socketio import exceptions as socketio_exceptions

from endpoints.responses.device_install import InstallRequestSchema, InstallStatus
from endpoints.sockets import devices
from handler.auth.hybrid_auth import resolve_client_token
from handler.database import db_client_token_handler, db_device_handler
from handler.redis_handler import as_text, async_cache, sync_cache
from handler.socket_handler import DEVICES_NAMESPACE, socket_handler
from models.client_token import ClientToken
from models.device import Device
from models.user import User

NAMESPACE = DEVICES_NAMESPACE


@pytest.fixture(autouse=True)
def clear_cache():
    sync_cache.flushall()
    yield
    sync_cache.flushall()


async def _members(key: str) -> set[str]:
    return {as_text(member) for member in await async_cache.smembers(key)}


@pytest.fixture
def socket_session(mocker) -> dict[str, Any]:
    stored: dict[str, Any] = {}

    @asynccontextmanager
    async def session(sid: str, namespace: str | None = None):
        yield stored

    mocker.patch.object(socket_handler.socket_server, "session", session)
    return stored


@pytest.fixture
def background(mocker) -> MagicMock:
    """The ``_keep_tracked`` a connect schedules, without running it."""
    keep_tracked = mocker.patch.object(devices, "_keep_tracked", MagicMock())
    mocker.patch.object(devices, "fire_and_forget")
    return keep_tracked


@pytest.fixture
def enter_room(mocker, socket_session, background):
    return mocker.patch.object(socket_handler.socket_server, "enter_room", AsyncMock())


@pytest.fixture
def device_token(add_device_token):
    """A token for a new ``dev-socket`` device, or an unbound one."""

    def _make(
        user: User, *, device_bound: bool = True, **kwargs
    ) -> tuple[ClientToken, str]:
        device_id = None
        if device_bound:
            device_id = db_device_handler.add_device(
                Device(id="dev-socket", user_id=user.id, name="Handheld")
            ).id
        token: tuple[ClientToken, str] = add_device_token(user, device_id, **kwargs)
        return token

    return _make


class TestConnect:
    async def test_joins_the_devices_room_from_the_auth_payload(
        self, enter_room, socket_session, admin_user, device_token
    ):
        token, raw = device_token(admin_user)

        await devices.connect("sid-1", {}, {"token": raw})

        enter_room.assert_awaited_once_with(
            "sid-1", "device:dev-socket", namespace=NAMESPACE
        )
        assert socket_session == {
            devices.CLIENT_TOKEN_ID_KEY: token.id,
            devices.DEVICE_ID_KEY: "dev-socket",
        }

    async def test_accepts_a_bearer_header(self, enter_room, admin_user, device_token):
        _, raw = device_token(admin_user)

        await devices.connect("sid-1", {"HTTP_AUTHORIZATION": f"Bearer {raw}"}, None)

        enter_room.assert_awaited_once()

    async def test_tracks_the_socket_for_revocation_and_presence(
        self, enter_room, admin_user, device_token
    ):
        token, raw = device_token(admin_user)

        await devices.connect("sid-1", {}, {"token": raw})

        token_key = f"device_token_sockets:{token.id}"
        presence_key = "device_presence:dev-socket"
        assert await _members(token_key) == {"sid-1"}
        assert await _members(presence_key) == {"sid-1"}
        assert (
            0 < await async_cache.ttl(token_key) <= devices.SOCKET_TRACKING_TTL_SECONDS
        )
        assert 0 < await async_cache.ttl(presence_key) <= devices.PRESENCE_TTL_SECONDS

    async def test_refuses_a_token_revoked_before_the_socket_was_tracked(
        self, mocker, enter_room, admin_user, device_token
    ):
        token, raw = device_token(admin_user)
        mocker.patch.object(
            devices,
            "resolve_client_token",
            side_effect=[resolve_client_token(raw), None],
        )

        with pytest.raises(socketio_exceptions.ConnectionRefusedError):
            await devices.connect("sid-1", {}, {"token": raw})

        assert not await async_cache.exists(f"device_token_sockets:{token.id}")
        assert await devices.online_device_ids(["dev-socket"]) == []
        enter_room.assert_not_awaited()

    async def test_keeps_the_tracking_fresh_while_connected(
        self, enter_room, background, admin_user, device_token
    ):
        token, raw = device_token(admin_user)

        await devices.connect("sid-1", {}, {"token": raw})

        background.assert_called_once_with(
            "sid-1", devices.BoundToken(token.id, "dev-socket", None)
        )
        devices.fire_and_forget.assert_called_once_with(background.return_value)

    async def test_bumps_the_tokens_last_use(
        self, enter_room, admin_user, device_token
    ):
        token, raw = device_token(admin_user)

        await devices.connect("sid-1", {}, {"token": raw})

        [stored] = db_client_token_handler.get_tokens_by_user(admin_user.id)
        assert stored.id == token.id
        assert stored.last_used_at is not None

    async def test_never_writes_the_devices_capabilities(
        self, enter_room, admin_user, device_token
    ):
        _, raw = device_token(admin_user)

        await devices.connect(
            "sid-1", {}, {"token": raw, "capabilities": {"remote_install": True}}
        )

        stored = db_device_handler.get_device(
            device_id="dev-socket", user_id=admin_user.id
        )
        assert stored is not None
        assert stored.capabilities is None

    @pytest.mark.parametrize(
        "token_kwargs",
        [
            {"device_bound": False},
            {"scopes": "roms.read"},
            {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)},
        ],
    )
    async def test_refuses_a_token_that_does_not_speak_for_a_device(
        self, enter_room, admin_user, device_token, token_kwargs
    ):
        _, raw = device_token(admin_user, **token_kwargs)

        with pytest.raises(socketio_exceptions.ConnectionRefusedError):
            await devices.connect("sid-1", {}, {"token": raw})

        enter_room.assert_not_awaited()

    @pytest.mark.parametrize("auth", [None, {"token": "rmm_unknown"}, {"token": "x"}])
    async def test_refuses_a_missing_or_unknown_token(self, enter_room, auth):
        with pytest.raises(socketio_exceptions.ConnectionRefusedError):
            await devices.connect("sid-1", {}, auth)

        enter_room.assert_not_awaited()

    async def test_never_accepts_a_browser_session(self, enter_room):
        environ = {"HTTP_COOKIE": "romm_session=abc"}

        with pytest.raises(socketio_exceptions.ConnectionRefusedError):
            await devices.connect("sid-1", environ, None)

    async def test_refuses_every_device_while_install_is_disabled(
        self, mocker, enter_room, admin_user, device_token
    ):
        _, raw = device_token(admin_user)
        mocker.patch.object(devices, "DEVICE_INSTALL_ENABLED", False)

        with pytest.raises(socketio_exceptions.ConnectionRefusedError):
            await devices.connect("sid-1", {}, {"token": raw})

        enter_room.assert_not_awaited()


BOUND = devices.BoundToken(42, "dev-1", None)


class TestKeepTracked:
    @pytest.fixture(autouse=True)
    def sleep(self, mocker) -> AsyncMock:
        sleep = AsyncMock()
        mocker.patch.object(socket_handler.socket_server, "sleep", sleep)
        return sleep

    async def test_refreshes_while_the_socket_is_connected(self, mocker):
        mocker.patch.object(
            socket_handler.socket_server.manager,
            "is_connected",
            side_effect=[True, False],
        )

        await devices._keep_tracked("sid-1", BOUND)

        assert await _members("device_presence:dev-1") == {"sid-1"}
        assert 0 < await async_cache.ttl("device_presence:dev-1")

    async def test_keeps_a_long_lived_socket_revocable(self, mocker):
        mocker.patch.object(
            socket_handler.socket_server.manager,
            "is_connected",
            side_effect=[True, False],
        )
        await async_cache.sadd("device_token_sockets:42", "sid-1")
        await async_cache.expire("device_token_sockets:42", 5)

        await devices._keep_tracked("sid-1", BOUND)

        assert await _members("device_token_sockets:42") == {"sid-1"}
        assert (
            await async_cache.ttl("device_token_sockets:42")
            > devices.SOCKET_TRACKING_TTL_SECONDS - 60
        )

    async def test_stops_once_the_socket_is_gone(self, mocker):
        mocker.patch.object(
            socket_handler.socket_server.manager, "is_connected", return_value=False
        )

        await devices._keep_tracked("sid-1", BOUND)

        assert not await async_cache.exists("device_presence:dev-1")
        assert not await async_cache.exists("device_token_sockets:42")

    async def test_closes_the_socket_once_its_token_expires(self, mocker):
        mocker.patch.object(
            socket_handler.socket_server.manager,
            "is_connected",
            side_effect=[True, False],
        )
        disconnect = mocker.patch.object(
            socket_handler.socket_server, "disconnect", AsyncMock()
        )
        expired = BOUND._replace(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )

        await devices._keep_tracked("sid-1", expired)

        disconnect.assert_awaited_once_with("sid-1", namespace=NAMESPACE)
        assert not await async_cache.exists("device_presence:dev-1")

    async def test_keeps_a_socket_whose_token_has_not_expired(self, mocker):
        mocker.patch.object(
            socket_handler.socket_server.manager,
            "is_connected",
            side_effect=[True, False],
        )
        disconnect = mocker.patch.object(
            socket_handler.socket_server, "disconnect", AsyncMock()
        )
        later = BOUND._replace(
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )

        await devices._keep_tracked("sid-1", later)

        disconnect.assert_not_awaited()
        assert await _members("device_presence:dev-1") == {"sid-1"}


class TestEmitToDevice:
    async def test_cancelled_goes_to_the_devices_room(self, mocker):
        emit = AsyncMock()
        mocker.patch.object(
            socket_handler, "write_manager", return_value=MagicMock(emit=emit)
        )
        request = InstallRequestSchema(
            id="req-1",
            user_id=1,
            device_id="dev-1",
            rom_id=7,
            file_ids=[10],
            status=InstallStatus.CANCELLED,
            reason=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        await devices.emit_install_cancelled(request)

        emit.assert_awaited_once_with(
            "install:cancelled",
            {"id": "req-1", "rom_id": 7},
            namespace=NAMESPACE,
            room="device:dev-1",
        )


class TestDisconnect:
    async def test_forgets_the_socket(self, mocker):
        await async_cache.sadd("device_token_sockets:42", "sid-1", "sid-2")
        await async_cache.sadd("device_presence:dev-1", "sid-1")
        mocker.patch.object(
            socket_handler.socket_server,
            "get_session",
            AsyncMock(
                return_value={
                    devices.CLIENT_TOKEN_ID_KEY: 42,
                    devices.DEVICE_ID_KEY: "dev-1",
                }
            ),
        )

        await devices.disconnect("sid-1")

        assert await _members("device_token_sockets:42") == {"sid-2"}
        assert await devices.online_device_ids(["dev-1"]) == []

    def test_is_registered_on_the_devices_namespace_only(self):
        handlers = socket_handler.socket_server.handlers
        assert handlers[NAMESPACE]["disconnect"] is devices.disconnect
        assert handlers[NAMESPACE]["connect"] is devices.connect
        assert handlers["/"]["connect"] is not devices.connect


class TestPresence:
    async def test_a_device_with_a_fresh_presence_is_online(self):
        await async_cache.sadd("device_presence:dev-1", "sid-1")

        assert await devices.online_device_ids(["dev-1", "dev-2"]) == ["dev-1"]

    async def test_keeps_the_callers_order(self):
        await async_cache.sadd("device_presence:dev-1", "sid-1")
        await async_cache.sadd("device_presence:dev-2", "sid-2")

        assert await devices.online_device_ids(["dev-2", "dev-1"]) == [
            "dev-2",
            "dev-1",
        ]

    async def test_a_revocation_entry_alone_is_not_presence(self):
        await async_cache.sadd("device_token_sockets:42", "sid-1")

        assert await devices.online_device_ids(["dev-1"]) == []

    async def test_no_devices_asks_nothing(self):
        assert await devices.online_device_ids([]) == []


class TestEmit:
    @pytest.fixture
    def manager(self, mocker) -> MagicMock:
        manager = MagicMock(emit=AsyncMock())
        mocker.patch.object(socket_handler, "write_manager", return_value=manager)
        return manager

    def _request(self) -> InstallRequestSchema:
        now = datetime.now(timezone.utc)
        return InstallRequestSchema(
            id="r1",
            user_id=5,
            device_id="dev-1",
            rom_id=7,
            file_ids=[1],
            status=InstallStatus.PENDING,
            reason=None,
            created_at=now,
            updated_at=now,
        )

    async def test_queued_reaches_only_the_devices_room_on_its_namespace(self, manager):
        await devices.emit_install_queued(self._request())

        manager.emit.assert_awaited_once_with(
            "install:queued",
            {"id": "r1", "rom_id": 7},
            namespace=NAMESPACE,
            room="device:dev-1",
        )

    async def test_updated_reaches_the_owners_tabs(self, manager):
        await devices.emit_install_updated(self._request())

        event, payload = manager.emit.await_args.args
        assert event == "install:updated"
        assert payload["id"] == "r1"
        assert manager.emit.await_args.kwargs == {"room": "user:5"}
