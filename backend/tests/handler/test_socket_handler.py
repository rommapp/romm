from unittest.mock import AsyncMock, MagicMock

from handler import socket_handler as socket_handler_module
from handler.socket_handler import SocketHandler, netplay_socket_handler, socket_handler


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
