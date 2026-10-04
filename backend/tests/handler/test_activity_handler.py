import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from handler.activity_handler import ActivityEntry, activity_handler
from handler.database import db_rom_handler, db_user_handler
from handler.database.base_handler import sync_session
from handler.redis_handler import async_cache, sync_cache
from handler.socket_handler import socket_handler
from models.permission import HiddenEntity, PermEntity
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
        assert emit.await_args.kwargs == {"to": [f"user:{admin_user.id}"]}
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


@pytest.fixture
def clean_cache():
    sync_cache.flushall()
    yield
    sync_cache.flushall()


def _session(device_id: str, rom_id: int) -> dict[str, object]:
    return {"user_id": 1, "device_id": device_id, "rom_id": rom_id}


async def _seed(rom_id: int, sessions: dict[str, object], *members: str) -> None:
    for device_id, value in sessions.items():
        raw = value if isinstance(value, str) else json.dumps(value)
        await async_cache.set(f"activity:user:1:{device_id}", raw)
    await async_cache.sadd(f"activity:rom:{rom_id}", *members)


def test_active_for_rom_reads_every_session_at_once_and_drops_stale_members(
    clean_cache,
):
    live = _session("live", 7)
    asyncio.run(
        _seed(
            7,
            {
                "live": live,
                "corrupt": "not-json",
                "listed": "[]",
                "moved": _session("moved", 9),
            },
            "1:live",
            "1:expired",
            "1:corrupt",
            "1:listed",
            "1:moved",
            "not-a-member",
        )
    )

    with patch.object(async_cache, "get", wraps=async_cache.get) as get:
        assert asyncio.run(activity_handler.get_active_for_rom(7)) == [live]

    get.assert_not_called()
    assert asyncio.run(async_cache.smembers("activity:rom:7")) == {b"1:live"}


def test_active_for_rom_spares_a_member_a_heartbeat_revived(clean_cache):
    """A device that moves back to the ROM mid-read keeps its index entry."""
    asyncio.run(_seed(7, {"dev": _session("dev", 9)}, "1:dev"))
    real_mget = async_cache.mget

    async def mget_then_heartbeat(keys):
        raws = await real_mget(keys)
        await async_cache.set("activity:user:1:dev", json.dumps(_session("dev", 7)))
        return raws

    with patch.object(async_cache, "mget", side_effect=mget_then_heartbeat):
        assert asyncio.run(activity_handler.get_active_for_rom(7)) == []

    assert asyncio.run(async_cache.smembers("activity:rom:7")) == {b"1:dev"}


class TestAudience:
    """Who an activity update reaches: never sockets with no user."""

    @pytest.fixture
    def entry(self, admin_user: User, rom: Rom) -> Iterator[ActivityEntry]:
        entry = asyncio.run(
            activity_handler.build_entry(
                user_id=admin_user.id,
                device_id="deck",
                rom_id=rom.id,
                preserve_started_at=False,
            )
        )
        assert entry is not None
        yield entry
        _clear(admin_user, "deck")

    @staticmethod
    def _rooms(emit: AsyncMock) -> set[str]:
        call = emit.await_args
        assert call is not None
        return set(call.kwargs["to"])

    async def test_an_update_goes_to_each_user_who_can_see_the_rom(
        self,
        entry: ActivityEntry,
        admin_user: User,
        editor_user: User,
        viewer_user: User,
    ):
        with _captured_emits() as emit:
            await activity_handler.publish_active(entry)

        assert self._rooms(emit) == {
            f"user:{admin_user.id}",
            f"user:{editor_user.id}",
            f"user:{viewer_user.id}",
        }

    @pytest.mark.parametrize("hidden", ["rom", "platform", "age"])
    async def test_a_user_the_rom_is_hidden_from_is_left_out(
        self,
        entry: ActivityEntry,
        admin_user: User,
        viewer_user: User,
        rom: Rom,
        hidden: str,
    ):
        if hidden == "age":
            db_rom_handler.update_rom(rom.id, {"min_age": 18})
            db_user_handler.update_user(viewer_user.id, {"age_limit": 12})
        else:
            entity, entity_id = (
                (PermEntity.ROMS, rom.id)
                if hidden == "rom"
                else (PermEntity.PLATFORMS, rom.platform_id)
            )
            with sync_session.begin() as session:
                session.add(
                    HiddenEntity(
                        entity=entity, entity_id=entity_id, user_id=viewer_user.id
                    )
                )

        with _captured_emits() as emit:
            await activity_handler.publish_active(entry)

        assert self._rooms(emit) == {f"user:{admin_user.id}"}

    async def test_a_disabled_user_is_left_out(
        self, entry: ActivityEntry, admin_user: User, viewer_user: User
    ):
        db_user_handler.update_user(viewer_user.id, {"enabled": False})

        with _captured_emits() as emit:
            await activity_handler.publish_active(entry)

        assert self._rooms(emit) == {f"user:{admin_user.id}"}

    async def test_a_clear_goes_to_the_same_users(
        self, entry: ActivityEntry, admin_user: User, viewer_user: User, rom: Rom
    ):
        await activity_handler.set_active(entry)
        with sync_session.begin() as session:
            session.add(
                HiddenEntity(
                    entity=PermEntity.ROMS, entity_id=rom.id, user_id=viewer_user.id
                )
            )

        with _captured_emits() as emit:
            await activity_handler.publish_clear(admin_user.id, "deck")

        assert self._rooms(emit) == {f"user:{admin_user.id}"}

    async def test_nothing_is_sent_when_no_one_can_see_the_rom(
        self, entry: ActivityEntry, admin_user: User, rom: Rom
    ):
        db_user_handler.update_user(admin_user.id, {"enabled": False})

        with _captured_emits() as emit:
            await activity_handler.publish_active(entry)

        emit.assert_not_awaited()
        assert await activity_handler.get_active(admin_user.id, "deck") == entry

    async def test_switching_to_a_rom_someone_cannot_see_clears_their_card(
        self,
        entry: ActivityEntry,
        admin_user: User,
        viewer_user: User,
        second_rom: Rom,
    ):
        await activity_handler.publish_active(entry)
        with sync_session.begin() as session:
            session.add(
                HiddenEntity(
                    entity=PermEntity.ROMS,
                    entity_id=second_rom.id,
                    user_id=viewer_user.id,
                )
            )
        switched = await activity_handler.build_entry(
            user_id=admin_user.id,
            device_id="deck",
            rom_id=second_rom.id,
            preserve_started_at=False,
        )
        assert switched is not None

        with _captured_emits() as emit:
            await activity_handler.publish_active(switched)

        assert [(c.args, c.kwargs) for c in emit.await_args_list] == [
            (("activity:update", dict(switched)), {"to": [f"user:{admin_user.id}"]}),
            (
                (
                    "activity:clear",
                    {
                        "user_id": admin_user.id,
                        "device_id": "deck",
                        "rom_id": entry["rom_id"],
                    },
                ),
                {"to": [f"user:{viewer_user.id}"]},
            ),
        ]

    async def test_switching_to_a_rom_everyone_can_see_sends_no_clear(
        self,
        entry: ActivityEntry,
        admin_user: User,
        viewer_user: User,
        second_rom: Rom,
    ):
        await activity_handler.publish_active(entry)
        switched = await activity_handler.build_entry(
            user_id=admin_user.id,
            device_id="deck",
            rom_id=second_rom.id,
            preserve_started_at=False,
        )
        assert switched is not None

        with _captured_emits() as emit:
            await activity_handler.publish_active(switched)

        assert [c.args[0] for c in emit.await_args_list] == ["activity:update"]
