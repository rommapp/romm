from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from endpoints.sockets import activity
from handler.activity_handler import activity_handler
from handler.database import db_user_handler
from handler.socket_handler import socket_handler

SID = "sid-1"


@pytest.fixture
def sessions(mocker) -> dict[str, dict[str, Any]]:
    stored: dict[str, dict[str, Any]] = {}

    async def get_session(sid: str) -> dict[str, Any]:
        if sid not in stored:
            raise KeyError(sid)
        return dict(stored[sid])

    async def save_session(sid: str, session: dict[str, Any]) -> None:
        stored[sid] = dict(session)

    mocker.patch.object(socket_handler.socket_server, "get_session", get_session)
    mocker.patch.object(socket_handler.socket_server, "save_session", save_session)
    return stored


@pytest.fixture
def entry() -> MagicMock:
    return MagicMock(name="entry")


@pytest.fixture
def build_entry(mocker, entry: MagicMock):
    return mocker.patch.object(
        activity_handler, "build_entry", AsyncMock(return_value=entry)
    )


@pytest.fixture
def publish_active(mocker):
    return mocker.patch.object(activity_handler, "publish_active", AsyncMock())


@pytest.fixture
def publish_clear(mocker):
    return mocker.patch.object(activity_handler, "publish_clear", AsyncMock())


@pytest.fixture
async def signed_in(sessions) -> None:
    await activity.store_authenticated_user(SID, 7)


class TestStart:
    async def test_publishes_for_the_socket_user_not_the_payload(
        self, signed_in, build_entry, publish_active, entry, sessions
    ):
        await activity.activity_start(
            SID, {"rom_id": 42, "device_id": "deck", "user_id": 99}  # type: ignore[typeddict-unknown-key]
        )

        build_entry.assert_awaited_once_with(
            user_id=7, device_id="deck", rom_id=42, preserve_started_at=False
        )
        publish_active.assert_awaited_once_with(entry)
        assert sessions[SID]["activity_user_id"] == 7
        assert sessions[SID]["activity_device_id"] == "deck"

    async def test_an_unauthenticated_socket_is_ignored(
        self, sessions, build_entry, publish_active
    ):
        await activity.activity_start(SID, {"rom_id": 42, "device_id": "deck"})

        build_entry.assert_not_awaited()
        publish_active.assert_not_awaited()

    @pytest.mark.parametrize(
        "payload",
        [
            None,
            "rom 42",
            {"device_id": "deck"},
            {"rom_id": 42},
            {"rom_id": 42, "device_id": ""},
            {"rom_id": 42, "device_id": 5},
            {"rom_id": "forty-two", "device_id": "deck"},
            {"rom_id": [42], "device_id": "deck"},
        ],
        ids=[
            "none",
            "not_a_dict",
            "no_rom",
            "no_device",
            "empty_device",
            "non_string_device",
            "non_numeric_rom",
            "list_rom",
        ],
    )
    async def test_an_invalid_payload_is_ignored(
        self, signed_in, build_entry, publish_active, payload: Any
    ):
        await activity.activity_start(SID, payload)

        build_entry.assert_not_awaited()
        publish_active.assert_not_awaited()

    async def test_a_numeric_string_rom_id_is_accepted(
        self, signed_in, build_entry, publish_active
    ):
        await activity.activity_start(SID, {"rom_id": "42", "device_id": "deck"})  # type: ignore[typeddict-item]

        assert build_entry.await_args.kwargs["rom_id"] == 42

    async def test_a_missing_rom_or_user_publishes_nothing(
        self, signed_in, build_entry, publish_active, sessions
    ):
        build_entry.return_value = None

        await activity.activity_start(SID, {"rom_id": 42, "device_id": "deck"})

        publish_active.assert_not_awaited()
        assert "activity_device_id" not in sessions[SID]


class TestHeartbeat:
    async def test_keeps_the_original_start_time(
        self, signed_in, build_entry, publish_active, entry
    ):
        await activity.activity_heartbeat(SID, {"rom_id": 42, "device_id": "deck"})

        build_entry.assert_awaited_once_with(
            user_id=7, device_id="deck", rom_id=42, preserve_started_at=True
        )
        publish_active.assert_awaited_once_with(entry)

    async def test_an_unauthenticated_socket_is_ignored(
        self, sessions, build_entry, publish_active
    ):
        await activity.activity_heartbeat(SID, {"rom_id": 42, "device_id": "deck"})

        build_entry.assert_not_awaited()

    async def test_a_missing_rom_or_user_publishes_nothing(
        self, signed_in, build_entry, publish_active
    ):
        build_entry.return_value = None

        await activity.activity_heartbeat(SID, {"rom_id": 42, "device_id": "deck"})

        publish_active.assert_not_awaited()


class TestStop:
    async def test_clears_the_named_device(self, signed_in, publish_clear):
        await activity.activity_stop(SID, {"device_id": "deck"})

        publish_clear.assert_awaited_once_with(7, "deck")

    async def test_falls_back_to_the_device_it_started_on(
        self, signed_in, build_entry, publish_active, publish_clear
    ):
        await activity.activity_start(SID, {"rom_id": 42, "device_id": "deck"})

        await activity.activity_stop(SID)

        publish_clear.assert_awaited_once_with(7, "deck")

    async def test_without_any_device_does_nothing(self, signed_in, publish_clear):
        await activity.activity_stop(SID, {})

        publish_clear.assert_not_awaited()

    async def test_an_unauthenticated_socket_is_ignored(self, sessions, publish_clear):
        await activity.activity_stop(SID, {"device_id": "deck"})

        publish_clear.assert_not_awaited()


class TestDisconnect:
    async def test_clears_the_activity_the_socket_started(
        self, signed_in, build_entry, publish_active, publish_clear
    ):
        await activity.activity_start(SID, {"rom_id": 42, "device_id": "deck"})

        await activity.activity_on_disconnect(SID)

        publish_clear.assert_awaited_once_with(7, "deck")

    async def test_a_socket_that_never_played_clears_nothing(
        self, signed_in, publish_clear
    ):
        await activity.activity_on_disconnect(SID)

        publish_clear.assert_not_awaited()

    async def test_an_unknown_socket_clears_nothing(self, sessions, publish_clear):
        await activity.activity_on_disconnect("gone")

        publish_clear.assert_not_awaited()


async def test_the_authenticated_user_is_looked_up_from_the_session(signed_in, mocker):
    user = MagicMock(id=7)
    get_user = mocker.patch.object(db_user_handler, "get_user", return_value=user)

    assert await activity.get_authenticated_user(SID) is user
    get_user.assert_called_once_with(7)


async def test_an_unauthenticated_socket_has_no_user(sessions, mocker):
    get_user = mocker.patch.object(db_user_handler, "get_user")

    assert await activity.get_authenticated_user(SID) is None
    get_user.assert_not_called()
