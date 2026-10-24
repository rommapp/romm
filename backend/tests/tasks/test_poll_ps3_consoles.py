from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handler.database import db_device_handler
from handler.redis_handler import async_cache
from handler.sync.ps3.console import PS3_DEVICE_TYPE
from models.device import Device, SyncMode
from models.user import User
from tasks import sync_push_pull_task
from tasks.registry import POLL_PS3_CONSOLES_SPEC, SCHEDULED_TASKS
from tasks.scheduled import poll_ps3_consoles
from tasks.scheduled.poll_ps3_consoles import PollPS3ConsolesTask


def add_ps3(user: User, **fields: object) -> Device:
    values: dict[str, object] = {
        "id": "ps3-device",
        "user_id": user.id,
        "client": PS3_DEVICE_TYPE.client,
        "sync_mode": SyncMode.PUSH_PULL,
        "sync_enabled": True,
        "ip_address": "192.168.1.115",
        "sync_config": {"poll_interval_minutes": 5},
    }
    return db_device_handler.add_device(Device(**(values | fields)))


@pytest.fixture
def probe():
    with patch.object(
        poll_ps3_consoles, "probe", AsyncMock(return_value="webMAN")
    ) as probe:
        yield probe


@pytest.fixture
def enqueue():
    with patch.object(poll_ps3_consoles, "enqueue_ps3_sync", MagicMock()) as enqueue:
        yield enqueue


@pytest.fixture(autouse=True)
async def clear_checks():
    yield
    async for key in async_cache.scan_iter("romm:ps3_sync:*"):
        await async_cache.delete(key)


class TestPollPS3Consoles:
    def test_is_scheduled_every_minute(self):
        assert SCHEDULED_TASKS["poll_ps3_consoles"] is POLL_PS3_CONSOLES_SPEC
        assert POLL_PS3_CONSOLES_SPEC.cron_string == "* * * * *"

    async def test_syncs_a_console_on_the_network(
        self, admin_user: User, probe, enqueue
    ):
        device = add_ps3(admin_user)

        await PollPS3ConsolesTask().run()

        probe.assert_awaited_once_with("192.168.1.115", 21)
        enqueue.assert_called_once()
        assert enqueue.call_args.args[0].id == device.id

    async def test_checks_again_only_after_the_interval(
        self, admin_user: User, probe, enqueue
    ):
        add_ps3(admin_user)

        await PollPS3ConsolesTask().run()
        await PollPS3ConsolesTask().run()

        assert probe.await_count == 1
        assert enqueue.call_count == 1

    async def test_skips_a_console_off_the_network(
        self, admin_user: User, probe, enqueue
    ):
        add_ps3(admin_user)
        probe.return_value = None

        await PollPS3ConsolesTask().run()

        enqueue.assert_not_called()

    @pytest.mark.parametrize(
        "fields",
        [
            {"sync_enabled": False},
            {"ip_address": None},
            {"ip_address": "127.0.0.1"},
            {"client": "argosy-launcher"},
            {"sync_config": {"ftp_port": "nope"}},
        ],
    )
    async def test_skips_consoles_it_cannot_sync(
        self, admin_user: User, probe, enqueue, fields: dict[str, object]
    ):
        add_ps3(admin_user, **fields)

        await PollPS3ConsolesTask().run()

        probe.assert_not_awaited()
        enqueue.assert_not_called()

    async def test_does_nothing_when_disabled(self, admin_user: User, probe, enqueue):
        add_ps3(admin_user)
        task = PollPS3ConsolesTask()
        task.spec = replace(POLL_PS3_CONSOLES_SPEC, enabled=False)

        await task.run()

        probe.assert_not_awaited()


class TestPushPullRoutesConsoles:
    async def test_a_direct_request_syncs_the_console(self, admin_user: User):
        device = add_ps3(admin_user)
        with patch.object(
            sync_push_pull_task,
            "sync_ps3_device",
            AsyncMock(return_value={"status": "completed"}),
        ) as sync_ps3:
            result = await sync_push_pull_task.run_push_pull_sync(
                device_id=device.id, session_id=7, force=True
            )

        sync_ps3.assert_awaited_once()
        assert sync_ps3.call_args.kwargs["session_id"] == 7
        assert result["device_results"] == [{"status": "completed"}]

    async def test_the_push_pull_schedule_leaves_consoles_alone(self, admin_user: User):
        add_ps3(admin_user)
        with patch.object(
            sync_push_pull_task, "sync_ps3_device", AsyncMock()
        ) as sync_ps3:
            await sync_push_pull_task.run_push_pull_sync(force=True)

        sync_ps3.assert_not_awaited()
