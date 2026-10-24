from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handler.database import db_device_handler
from handler.redis_handler import async_cache
from handler.sync.console.ps3 import PS3
from handler.sync.console.ps4 import PS4
from models.device import Device, SyncMode
from models.user import User
from tasks import sync_push_pull_task
from tasks.registry import POLL_CONSOLES_SPEC, SCHEDULED_TASKS
from tasks.scheduled import poll_consoles
from tasks.scheduled.poll_consoles import PollConsolesTask


def add_console(user: User, **fields: object) -> Device:
    values: dict[str, object] = {
        "id": "ps3-device",
        "user_id": user.id,
        "client": PS3.device_type.client,
        "sync_mode": SyncMode.PUSH_PULL,
        "sync_enabled": True,
        "ip_address": "192.168.1.115",
        "sync_config": {"user_id": "00000001", "poll_interval_minutes": 5},
    }
    return db_device_handler.add_device(Device(**(values | fields)))


@pytest.fixture
def probe():
    with patch.object(
        poll_consoles, "probe", AsyncMock(return_value="webMAN")
    ) as probe:
        yield probe


@pytest.fixture
def enqueue():
    with patch.object(poll_consoles, "enqueue_console_sync", MagicMock()) as enqueue:
        yield enqueue


@pytest.fixture(autouse=True)
async def clear_checks():
    yield
    async for key in async_cache.scan_iter("romm:console_sync:*"):
        await async_cache.delete(key)


class TestPollConsoles:
    def test_is_scheduled_every_minute(self):
        assert SCHEDULED_TASKS["poll_consoles"] is POLL_CONSOLES_SPEC
        assert POLL_CONSOLES_SPEC.cron_string == "* * * * *"

    async def test_syncs_a_console_on_the_network(
        self, admin_user: User, probe, enqueue
    ):
        device = add_console(admin_user)

        await PollConsolesTask().run()

        probe.assert_awaited_once_with("192.168.1.115", 21)
        enqueue.assert_called_once()
        assert enqueue.call_args.args[0].id == device.id

    async def test_probes_a_ps4_on_its_ftp_port(self, admin_user: User, probe, enqueue):
        add_console(
            admin_user,
            client=PS4.device_type.client,
            ip_address="192.168.1.177",
            sync_config={"user_id": "1cabafc9"},
        )

        await PollConsolesTask().run()

        probe.assert_awaited_once_with("192.168.1.177", 2121)
        enqueue.assert_called_once()

    async def test_checks_again_only_after_the_interval(
        self, admin_user: User, probe, enqueue
    ):
        add_console(admin_user)

        await PollConsolesTask().run()
        await PollConsolesTask().run()

        assert probe.await_count == 1
        assert enqueue.call_count == 1

    async def test_skips_a_console_off_the_network(
        self, admin_user: User, probe, enqueue
    ):
        add_console(admin_user)
        probe.return_value = None

        await PollConsolesTask().run()

        enqueue.assert_not_called()

    @pytest.mark.parametrize(
        "fields",
        [
            {"sync_enabled": False},
            {"ip_address": None},
            {"ip_address": "127.0.0.1"},
            {"client": "argosy-launcher"},
            {"sync_config": {"user_id": "00000001", "ftp_port": "nope"}},
            {"sync_config": {"user_id": "1cabafc9"}},
        ],
    )
    async def test_skips_consoles_it_cannot_sync(
        self, admin_user: User, probe, enqueue, fields: dict[str, object]
    ):
        add_console(admin_user, **fields)

        await PollConsolesTask().run()

        probe.assert_not_awaited()
        enqueue.assert_not_called()

    async def test_does_nothing_when_disabled(self, admin_user: User, probe, enqueue):
        add_console(admin_user)
        task = PollConsolesTask()
        task.spec = replace(POLL_CONSOLES_SPEC, enabled=False)

        await task.run()

        probe.assert_not_awaited()


class TestPushPullRoutesConsoles:
    async def test_a_direct_request_syncs_the_console(self, admin_user: User):
        device = add_console(admin_user)
        with patch.object(
            sync_push_pull_task,
            "sync_console_device",
            AsyncMock(return_value={"status": "completed"}),
        ) as sync_console:
            result = await sync_push_pull_task.run_push_pull_sync(
                device_id=device.id, session_id=7, force=True
            )

        sync_console.assert_awaited_once()
        assert sync_console.call_args.kwargs["session_id"] == 7
        assert result["device_results"] == [{"status": "completed"}]

    async def test_the_push_pull_schedule_leaves_consoles_alone(self, admin_user: User):
        add_console(admin_user)
        with patch.object(
            sync_push_pull_task, "sync_console_device", AsyncMock()
        ) as sync_console:
            await sync_push_pull_task.run_push_pull_sync(force=True)

        sync_console.assert_not_awaited()
