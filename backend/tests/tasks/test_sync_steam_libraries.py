from unittest.mock import AsyncMock, patch

import pytest

from endpoints.sockets.scan import ScanPayload
from exceptions.socket_exceptions import NoScanWorkerException
from handler.database import db_user_handler
from handler.scan.sources import ScanType
from handler.steam_library_handler import SteamLibraryError, SteamSyncResult
from models.user import User
from tasks.scheduled.sync_steam_libraries import SyncSteamLibrariesTask

MODULE = "tasks.scheduled.sync_steam_libraries"


@pytest.fixture
def task() -> SyncSteamLibrariesTask:
    return SyncSteamLibrariesTask()


@pytest.fixture(autouse=True)
def api_key():
    with patch(f"{MODULE}.STEAM_API_KEY", "key"):
        yield


@pytest.fixture
def linked_user(admin_user: User) -> User:
    db_user_handler.update_user(admin_user.id, {"steam_id": "76561197960287930"})
    return admin_user


@pytest.fixture
def queue_scan():
    with patch(f"{MODULE}.queue_scan", new_callable=AsyncMock) as queue:
        yield queue


async def test_syncs_every_linked_user(
    task: SyncSteamLibrariesTask, linked_user: User, viewer_user: User, queue_scan
):
    with patch(
        f"{MODULE}.sync_steam_library",
        new_callable=AsyncMock,
        return_value=SteamSyncResult(owned=1, created=1, unmatched_rom_ids=[7]),
    ) as sync:
        stats = await task.run()

    [call] = sync.await_args_list
    assert call.args[0].id == linked_user.id
    assert stats == {"processed": 1, "total": 1}
    queue_scan.assert_awaited_once_with(
        ScanPayload(type=ScanType.UNMATCHED, roms_ids=[7]), started_by_user_id=None
    )


async def test_one_users_failure_does_not_stop_the_rest(
    task: SyncSteamLibrariesTask, linked_user: User, viewer_user: User, queue_scan
):
    db_user_handler.update_user(viewer_user.id, {"steam_id": "76561197960287931"})
    with patch(
        f"{MODULE}.sync_steam_library",
        new_callable=AsyncMock,
        side_effect=[SteamLibraryError("private"), SteamSyncResult()],
    ) as sync:
        stats = await task.run()

    assert sync.await_count == 2
    assert stats == {"processed": 2, "total": 2}
    queue_scan.assert_not_awaited()


async def test_a_requested_sync_reports_its_failure(
    task: SyncSteamLibrariesTask, linked_user: User, queue_scan
):
    with patch(
        f"{MODULE}.sync_steam_library",
        new_callable=AsyncMock,
        side_effect=SteamLibraryError("private"),
    ):
        with pytest.raises(SteamLibraryError, match="private"):
            await task.run(user_id=linked_user.id)


async def test_a_requested_sync_scans_for_that_user(
    task: SyncSteamLibrariesTask, linked_user: User, queue_scan
):
    with patch(
        f"{MODULE}.sync_steam_library",
        new_callable=AsyncMock,
        return_value=SteamSyncResult(unmatched_rom_ids=[3, 1]),
    ):
        await task.run(user_id=linked_user.id)

    queue_scan.assert_awaited_once_with(
        ScanPayload(type=ScanType.UNMATCHED, roms_ids=[1, 3]),
        started_by_user_id=linked_user.id,
    )


async def test_no_scan_worker_leaves_the_games_for_the_next_sync(
    task: SyncSteamLibrariesTask, linked_user: User, queue_scan
):
    queue_scan.side_effect = NoScanWorkerException("none")
    with patch(
        f"{MODULE}.sync_steam_library",
        new_callable=AsyncMock,
        return_value=SteamSyncResult(unmatched_rom_ids=[1]),
    ):
        stats = await task.run(user_id=linked_user.id)

    assert stats == {"processed": 1, "total": 1}


async def test_does_nothing_without_an_api_key(
    task: SyncSteamLibrariesTask, linked_user: User
):
    with (
        patch(f"{MODULE}.STEAM_API_KEY", None),
        patch(f"{MODULE}.sync_steam_library", new_callable=AsyncMock) as sync,
    ):
        stats = await task.run()

    sync.assert_not_awaited()
    assert stats == {"processed": 0, "total": 0}
