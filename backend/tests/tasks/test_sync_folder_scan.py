import dataclasses
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handler.database import db_device_handler, db_sync_session_handler
from handler.filesystem.sync_handler import FSSyncHandler
from models.device import Device, SyncMode
from models.sync_session import SyncSession, SyncSessionStatus
from models.user import User
from tasks.manual.sync_folder_scan import sync_folder_scan_task


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = dataclasses.replace(sync_folder_scan_task.spec, enabled=True)
    monkeypatch.setattr(sync_folder_scan_task, "spec", spec)


@pytest.fixture
def sync_root(tmp_path: Path) -> Iterator[Path]:
    handler = FSSyncHandler.__new__(FSSyncHandler)
    handler.base_path = tmp_path
    with (
        patch(
            "tasks.manual.sync_folder_scan.get_fs_sync_handler", return_value=handler
        ),
        patch("sync_watcher.get_fs_sync_handler", return_value=handler),
    ):
        yield tmp_path


@pytest.fixture
def emitted() -> Iterator[dict[str, AsyncMock]]:
    with (
        patch("endpoints.sockets.sync.emit_sync_started") as started,
        patch("endpoints.sockets.sync.emit_sync_completed") as completed,
        patch("endpoints.sockets.sync.emit_sync_error") as error,
    ):
        yield {"started": started, "completed": completed, "error": error}


@pytest.fixture
def process_file() -> Iterator[MagicMock]:
    with patch("sync_watcher._process_incoming_file") as process:
        yield process


def _device(
    user: User,
    device_id: str,
    sync_mode: SyncMode = SyncMode.FILE_TRANSFER,
    sync_enabled: bool = True,
) -> Device:
    return db_device_handler.add_device(
        Device(
            id=device_id,
            user_id=user.id,
            sync_mode=sync_mode,
            sync_enabled=sync_enabled,
        )
    )


def _incoming(root: Path, device_id: str, platform_slug: str, name: str) -> str:
    path = root / device_id / "incoming" / platform_slug / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"device bytes")
    return str(path)


def _sessions(device: Device) -> list[SyncSession]:
    return list(
        db_sync_session_handler.get_sessions(
            user_id=device.user_id, device_id=device.id
        )
    )


async def test_a_disabled_scan_does_nothing(
    monkeypatch: pytest.MonkeyPatch, admin_user: User, sync_root: Path
):
    spec = dataclasses.replace(sync_folder_scan_task.spec, enabled=False)
    monkeypatch.setattr(sync_folder_scan_task, "spec", spec)
    device = _device(admin_user, "deck")
    _incoming(sync_root, "deck", "gba", "a.srm")

    assert await sync_folder_scan_task.run() == {"status": "disabled"}
    assert _sessions(device) == []


async def test_without_file_transfer_devices_there_is_nothing_to_scan(
    admin_user: User, sync_root: Path
):
    _device(admin_user, "api-deck", sync_mode=SyncMode.API)

    assert await sync_folder_scan_task.run() == {"status": "no_devices"}


async def test_processes_each_devices_incoming_files(
    admin_user: User,
    sync_root: Path,
    emitted: dict[str, AsyncMock],
    process_file: MagicMock,
):
    deck = _device(admin_user, "deck")
    handheld = _device(admin_user, "handheld")
    deck_a = _incoming(sync_root, "deck", "gba", "a.srm")
    deck_b = _incoming(sync_root, "deck", "snes", "b.srm")
    handheld_c = _incoming(sync_root, "handheld", "gba", "c.srm")

    result = await sync_folder_scan_task.run()

    assert result == {"status": "completed", "files_processed": 3}
    processed = {(c.args[0].id, *c.args[2:]) for c in process_file.call_args_list}
    assert processed == {
        ("deck", "gba", "a.srm", deck_a),
        ("deck", "snes", "b.srm", deck_b),
        ("handheld", "gba", "c.srm", handheld_c),
    }
    for device, files in ((deck, 2), (handheld, 1)):
        [session] = _sessions(device)
        assert session.status == SyncSessionStatus.COMPLETED
        assert (session.operations_planned, session.operations_completed) == (
            files,
            files,
        )
    assert emitted["started"].await_count == 2
    assert emitted["completed"].await_count == 2


async def test_a_failed_file_is_counted_in_its_session(
    admin_user: User,
    sync_root: Path,
    emitted: dict[str, AsyncMock],
    process_file: MagicMock,
):
    deck = _device(admin_user, "deck")
    _incoming(sync_root, "deck", "gba", "a.srm")
    process_file.side_effect = OSError("unreadable")

    result = await sync_folder_scan_task.run()

    assert result == {"status": "completed", "files_processed": 1}
    [session] = _sessions(deck)
    assert (session.operations_completed, session.operations_failed) == (0, 1)
    emitted["error"].assert_awaited_once()


async def test_devices_with_sync_off_or_nothing_incoming_are_skipped(
    admin_user: User,
    sync_root: Path,
    emitted: dict[str, AsyncMock],
    process_file: MagicMock,
):
    paused = _device(admin_user, "paused", sync_enabled=False)
    idle = _device(admin_user, "idle")
    _incoming(sync_root, "paused", "gba", "a.srm")
    (sync_root / "idle" / "incoming" / "gba").mkdir(parents=True)

    result = await sync_folder_scan_task.run()

    assert result == {"status": "completed", "files_processed": 0}
    process_file.assert_not_called()
    assert _sessions(paused) == []
    assert _sessions(idle) == []
    emitted["started"].assert_not_awaited()
