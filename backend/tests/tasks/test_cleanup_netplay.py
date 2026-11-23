from dataclasses import replace
from unittest.mock import AsyncMock

from handler.netplay_handler import netplay_handler
from tasks.registry import CLEANUP_NETPLAY_SPEC
from tasks.scheduled.cleanup_netplay import CleanupNetplayTask


def test_default_schedule():
    assert CLEANUP_NETPLAY_SPEC.enabled is True
    assert CLEANUP_NETPLAY_SPEC.cron_string == "*/30 * * * *"
    assert CLEANUP_NETPLAY_SPEC.manual_run is False


async def test_disabled_cleanup_does_not_access_rooms(monkeypatch):
    get_all = AsyncMock()
    monkeypatch.setattr(netplay_handler, "get_all", get_all)
    task = CleanupNetplayTask()
    task.spec = replace(task.spec, enabled=False)
    await task.run()
    get_all.assert_not_awaited()


async def test_enabled_cleanup_removes_only_empty_rooms(monkeypatch):
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
