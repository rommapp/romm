import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from handler.activity_handler import activity_handler
from handler.redis_handler import async_cache
from handler.socket_handler import socket_handler
from models.rom import Rom
from models.user import User


def _clear(user: User, device_id: str) -> None:
    asyncio.run(activity_handler.clear_active(user.id, device_id))


@contextmanager
def _captured_emits():
    with patch.object(
        socket_handler.socket_server, "emit", new_callable=AsyncMock
    ) as emit:
        yield emit


def test_build_entry_names_the_game_the_player_and_the_device(
    admin_user: User, rom: Rom
):
    entry = asyncio.run(
        activity_handler.build_entry(
            user_id=admin_user.id,
            device_id="container-1",
            rom_id=rom.id,
            preserve_started_at=False,
            device_type="streaming",
        )
    )
    assert entry is not None
    assert entry["user_id"] == admin_user.id
    assert entry["username"] == admin_user.username
    assert entry["rom_id"] == rom.id
    assert entry["platform_slug"] == rom.platform_slug
    assert entry["device_id"] == "container-1"
    assert entry["device_type"] == "streaming"


def test_build_entry_returns_none_for_a_rom_that_is_gone(admin_user: User):
    """A stale session must be a no-op for its caller, not an error."""
    assert (
        asyncio.run(
            activity_handler.build_entry(
                user_id=admin_user.id,
                device_id="container-1",
                rom_id=999_999,
                preserve_started_at=False,
            )
        )
        is None
    )


def test_refreshing_an_entry_keeps_the_original_start_time(admin_user: User, rom: Rom):
    """The board shows how long someone has been playing, so a refresh must not
    restart the clock."""
    try:
        first = asyncio.run(
            activity_handler.build_entry(
                user_id=admin_user.id,
                device_id="container-1",
                rom_id=rom.id,
                preserve_started_at=False,
            )
        )
        assert first is not None
        asyncio.run(activity_handler.set_active(first))

        refreshed = asyncio.run(
            activity_handler.build_entry(
                user_id=admin_user.id,
                device_id="container-1",
                rom_id=rom.id,
                preserve_started_at=True,
            )
        )
        assert refreshed is not None
        assert refreshed["started_at"] == first["started_at"]
    finally:
        _clear(admin_user, "container-1")


def test_publishing_stores_the_entry_and_broadcasts_it(admin_user: User, rom: Rom):
    entry = asyncio.run(
        activity_handler.build_entry(
            user_id=admin_user.id,
            device_id="container-1",
            rom_id=rom.id,
            preserve_started_at=False,
        )
    )
    assert entry is not None
    try:
        with _captured_emits() as emit:
            asyncio.run(activity_handler.publish_active(entry))
        assert emit.await_args[0] == ("activity:update", dict(entry))
        assert (
            asyncio.run(activity_handler.get_active(admin_user.id, "container-1"))
            == entry
        )
    finally:
        _clear(admin_user, "container-1")


def test_clearing_broadcasts_only_when_there_was_something_to_clear(
    admin_user: User, rom: Rom
):
    """Clearing runs on every teardown path, including ones where the entry has
    already expired, and those must not tell clients a session just ended."""
    entry = asyncio.run(
        activity_handler.build_entry(
            user_id=admin_user.id,
            device_id="container-1",
            rom_id=rom.id,
            preserve_started_at=False,
        )
    )
    assert entry is not None
    asyncio.run(activity_handler.set_active(entry))

    with _captured_emits() as emit:
        assert (
            asyncio.run(activity_handler.publish_clear(admin_user.id, "container-1"))
            == rom.id
        )
        assert emit.await_args[0] == (
            "activity:clear",
            {
                "user_id": admin_user.id,
                "device_id": "container-1",
                "rom_id": rom.id,
            },
        )

        emit.reset_mock()
        assert (
            asyncio.run(activity_handler.publish_clear(admin_user.id, "container-1"))
            is None
        )
        emit.assert_not_awaited()

    assert (
        asyncio.run(async_cache.get(f"activity:user:{admin_user.id}:container-1"))
        is None
    )
