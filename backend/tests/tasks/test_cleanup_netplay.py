from unittest.mock import AsyncMock

import tasks.scheduled.cleanup_netplay as mod
from handler.netplay_handler import netplay_handler
from tasks.scheduled.cleanup_netplay import CleanupNetplayTask


def test_default_schedule():
    task = CleanupNetplayTask()
    assert task.enabled is True
    assert task.cron_string == "*/30 * * * *"
    assert task.manual_run is False


def test_custom_schedule(monkeypatch):
    monkeypatch.setattr(mod, "SCHEDULED_CLEANUP_NETPLAY_CRON", "0 2 * * *")
    assert CleanupNetplayTask().cron_string == "0 2 * * *"


async def test_disabled_cleanup_does_not_access_rooms(monkeypatch):
    monkeypatch.setattr(mod, "ENABLE_SCHEDULED_CLEANUP_NETPLAY", False)
    get_all = AsyncMock()
    monkeypatch.setattr(netplay_handler, "get_all", get_all)
    task = CleanupNetplayTask()
    assert task.enabled is False
    await task.run()
    get_all.assert_not_awaited()


async def test_enabled_cleanup_removes_only_empty_rooms(monkeypatch):
    monkeypatch.setattr(mod, "ENABLE_SCHEDULED_CLEANUP_NETPLAY", True)
    monkeypatch.setattr(
        netplay_handler,
        "get_all",
        AsyncMock(
            return_value={
                "empty": {"players": {}},
                "active": {"players": {"player1": {}}},
            }
        ),
    )
    delete = AsyncMock()
    monkeypatch.setattr(netplay_handler, "delete", delete)
    await CleanupNetplayTask().run()
    delete.assert_awaited_once_with(["empty"])
