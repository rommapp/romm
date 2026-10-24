import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from tests.factories import make_platform, make_rom, make_save
from tests.handler.sync.ps3.fakes import SAVEDATA, WRITTEN_AT, FakeConsole, build_sfo

from endpoints.sockets import sync as sync_sockets
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.filesystem import fs_asset_handler
from handler.redis_handler import async_cache
from handler.sync.ps3 import sync_handler
from handler.sync.ps3.console import PS3_DEVICE_TYPE, PS3SyncConfig
from handler.sync.ps3.ftp import AsyncPS3Ftp
from handler.sync.ps3.sync_handler import (
    PS3_SAVE_EMULATOR,
    PS3SyncCounts,
    _PS3Sync,
    _zip_folder,
    sync_ps3_device,
)
from models.assets import Save
from models.device import Device
from models.platform import Platform
from models.rom import Rom
from models.sync_session import SyncSessionStatus
from models.user import User
from utils.memory_cards import content_hash_of_bytes

FOLDER = "BLES01138SAVAUTOSAVE_SLOT1_SAV"
SFO = build_sfo(TITLE_ID="BLES01138", TITLE=" Far Cry® 3")


@pytest.fixture(autouse=True)
def quiet_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "emit_sync_started",
        "emit_sync_progress",
        "emit_sync_completed",
        "emit_sync_conflict",
        "emit_sync_error",
    ):
        monkeypatch.setattr(sync_sockets, name, AsyncMock())


@pytest.fixture
def ps3() -> Platform:
    return make_platform("ps3", name="PlayStation 3")


@pytest.fixture
def far_cry(ps3: Platform) -> Rom:
    return make_rom(ps3, "Far Cry 3", fs_extension="iso", title_id="BLES-01138")


@pytest.fixture
def device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(
            id="ps3-device",
            user_id=admin_user.id,
            name="Living room PS3",
            platform=PS3_DEVICE_TYPE.platform,
            client=PS3_DEVICE_TYPE.client,
            sync_mode=PS3_DEVICE_TYPE.sync_mode,
            ip_address="192.168.1.115",
            sync_config={},
        )
    )


@pytest.fixture
def console() -> FakeConsole:
    console = FakeConsole()
    console.add_dir(SAVEDATA)
    return console


async def run_sync(
    device: Device, console: FakeConsole, ps3: Platform
) -> PS3SyncCounts:
    session = db_sync_session_handler.create_session(
        device_id=device.id, user_id=device.user_id
    )
    device = db_device_handler.get_device_by_id(device.id) or device
    return await _PS3Sync(
        device, console, PS3SyncConfig.of(device.sync_config), ps3, session.id
    ).run()


def slot_versions(user: User, rom: Rom, slot: str = FOLDER) -> list[Save]:
    return list(
        db_save_handler.get_saves(
            user_id=user.id, rom_ids=[rom.id], slot=slot, order_by="updated_at"
        )
    )


async def store_server_version(
    user: User,
    rom: Rom,
    files: dict[str, bytes],
    *,
    origin: str | None,
    updated_at: datetime,
    slot: str = FOLDER,
) -> Save:
    """A server version as another sync would have filed it."""
    zip_bytes = _zip_folder(slot, files)
    path = fs_asset_handler.build_saves_file_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=PS3_SAVE_EMULATOR,
    )
    name = f"{slot} [{updated_at:%Y-%m-%d_%H-%M-%S}].zip"
    await fs_asset_handler.write_file(file=zip_bytes, path=path, filename=name)
    save = make_save(
        rom,
        user,
        name,
        file_path=path,
        slot=slot,
        emulator=PS3_SAVE_EMULATOR,
        content_hash=content_hash_of_bytes(zip_bytes),
        origin_device_id=origin,
    )
    return db_save_handler.update_save(save.id, {"updated_at": updated_at})


@pytest.fixture(autouse=True)
async def clear_cache(device: Device):
    yield
    async for key in async_cache.scan_iter(f"romm:ps3_sync:{device.id}:*"):
        await async_cache.delete(key)


class TestPull:
    async def test_pulls_a_new_folder_as_the_slot_first_version(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"progress"})

        counts = await run_sync(device, console, ps3)

        assert counts.pulled == 1
        [save] = slot_versions(admin_user, far_cry)
        assert save.emulator == PS3_SAVE_EMULATOR
        assert save.origin_device_id == device.id
        assert save.file_name.startswith(f"{FOLDER} [")
        with zipfile.ZipFile(fs_asset_handler.validate_path(save.full_path)) as zf:
            assert sorted(zf.namelist()) == [
                f"{FOLDER}/PARAM.SFO",
                f"{FOLDER}/SAVEDATA.000",
            ]
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync and sync.last_sync_hash == save.content_hash

    async def test_an_unchanged_folder_is_not_downloaded_again(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"progress"})
        await run_sync(device, console, ps3)
        console.reads.clear()

        counts = await run_sync(device, console, ps3)

        assert counts.unchanged == 1 and counts.pulled == 0
        assert console.reads == []
        assert len(slot_versions(admin_user, far_cry)) == 1

    async def test_a_console_change_adds_a_version(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"progress"})
        await run_sync(device, console, ps3)
        # Older than the sync, as a console keeping local time can write.
        console.add_save(
            FOLDER,
            {"SAVEDATA.000": b"more progress"},
            modified=WRITTEN_AT - timedelta(hours=5),
        )

        counts = await run_sync(device, console, ps3)

        assert counts.pulled == 1
        assert len(slot_versions(admin_user, far_cry)) == 2

    async def test_keeps_the_configured_number_of_versions(
        self, device, console, ps3, far_cry, admin_user
    ):
        db_device_handler.update_device(
            device_id=device.id,
            user_id=admin_user.id,
            data={"sync_config": {"keep_versions": 1}},
        )
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"one"})
        await run_sync(device, console, ps3)
        console.add_save(FOLDER, {"SAVEDATA.000": b"two"})

        await run_sync(device, console, ps3)

        assert len(slot_versions(admin_user, far_cry)) == 1

    async def test_matches_a_rom_by_the_save_title(
        self, device, console, ps3, admin_user
    ):
        rom = make_rom(ps3, "Far Cry 3", fs_extension="iso")
        console.add_save(FOLDER, {"PARAM.SFO": SFO})

        counts = await run_sync(device, console, ps3)

        assert counts.pulled == 1
        assert len(slot_versions(admin_user, rom)) == 1

    async def test_counts_a_folder_no_rom_matches(self, device, console, ps3):
        console.add_save("BLES99999SAVE", {"PARAM.SFO": build_sfo(TITLE="Other")})

        counts = await run_sync(device, console, ps3)

        assert counts.unmatched == 1
        assert counts.unmatched_folders == ["BLES99999SAVE"]

    async def test_skips_folders_that_are_not_saves(self, device, console, ps3):
        console.add_save("NP0APOLLO-OPTIONS", {"PARAM.SFO": b""})

        counts = await run_sync(device, console, ps3)

        assert counts == PS3SyncCounts()


class TestPush:
    async def test_pushes_a_newer_server_version(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"old"})
        await run_sync(device, console, ps3)
        await store_server_version(
            admin_user,
            far_cry,
            {"PARAM.SFO": SFO, "SAVEDATA.000": b"restored"},
            origin=device.id,
            updated_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )

        counts = await run_sync(device, console, ps3)

        assert counts.pushed == 1
        assert console.folder(f"{SAVEDATA}/{FOLDER}") == {
            "PARAM.SFO": SFO,
            "SAVEDATA.000": b"restored",
        }
        assert {e.name for e in await console.list(SAVEDATA)} == {FOLDER}

    async def test_does_not_push_a_version_from_another_device(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"old"})
        await run_sync(device, console, ps3)
        await store_server_version(
            admin_user,
            far_cry,
            {"PARAM.SFO": SFO, "SAVEDATA.000": b"from rpcs3"},
            origin=None,
            updated_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )

        counts = await run_sync(device, console, ps3)

        assert counts.pushed == 0
        assert console.folder(f"{SAVEDATA}/{FOLDER}")["SAVEDATA.000"] == b"old"

    async def test_pushes_a_missing_slot_only_for_games_on_the_console(
        self, device, console, ps3, far_cry, admin_user
    ):
        other = make_rom(ps3, "Not Installed", fs_extension="iso", title_id="BLES99999")
        console.add_save("BLES01138USERPROFILE", {"PARAM.SFO": SFO})
        for rom, slot in ((far_cry, FOLDER), (other, "BLES99999SAVE")):
            await store_server_version(
                admin_user,
                rom,
                {"PARAM.SFO": SFO, "DATA": b"x"},
                origin=device.id,
                updated_at=WRITTEN_AT,
                slot=slot,
            )

        counts = await run_sync(device, console, ps3)

        assert counts.pushed == 1
        assert await console.exists(f"{SAVEDATA}/{FOLDER}")
        assert not await console.exists(f"{SAVEDATA}/BLES99999SAVE")

    async def test_does_not_restore_a_slot_deleted_on_the_console(
        self, device, console, ps3, far_cry
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO})
        await run_sync(device, console, ps3)
        await console.remove_tree(f"{SAVEDATA}/{FOLDER}")

        counts = await run_sync(device, console, ps3)

        assert counts.pushed == 0
        assert not await console.exists(f"{SAVEDATA}/{FOLDER}")

    async def test_finishes_an_interrupted_push(self, device, console, ps3):
        console.add_save(f"{FOLDER}.ROMMOLD", {"PARAM.SFO": SFO})
        console.add_save(f"{FOLDER}.ROMMNEW", {"PARAM.SFO": b"partial"})

        await run_sync(device, console, ps3)

        assert {e.name for e in await console.list(SAVEDATA)} == {FOLDER}


class TestConflict:
    async def test_leaves_both_sides_when_both_changed(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"base"})
        await run_sync(device, console, ps3)
        console.add_save(FOLDER, {"SAVEDATA.000": b"console"})
        await store_server_version(
            admin_user,
            far_cry,
            {"PARAM.SFO": SFO, "SAVEDATA.000": b"server"},
            origin=device.id,
            updated_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )

        counts = await run_sync(device, console, ps3)

        assert counts.conflicts == 1
        assert console.folder(f"{SAVEDATA}/{FOLDER}")["SAVEDATA.000"] == b"console"
        assert len(slot_versions(admin_user, far_cry)) == 2


class TestSyncPS3Device:
    @pytest.fixture
    def connect(self, console: FakeConsole):
        with patch.object(
            AsyncPS3Ftp, "connect", AsyncMock(return_value=console)
        ) as connect:
            yield connect

    async def test_completes_the_session(self, device, connect, ps3, far_cry, console):
        console.add_save(FOLDER, {"PARAM.SFO": SFO})

        result = await sync_ps3_device(device)

        assert result["status"] == "completed" and result["pulled"] == 1
        [session] = db_sync_session_handler.get_sessions(
            user_id=device.user_id, device_id=device.id
        )
        assert session.status == SyncSessionStatus.COMPLETED
        refreshed = db_device_handler.get_device_by_id(device.id)
        assert refreshed and refreshed.last_seen is not None

    async def test_fails_the_session_when_the_console_is_unreachable(self, device, ps3):
        with patch.object(
            AsyncPS3Ftp,
            "connect",
            AsyncMock(side_effect=ConnectionRefusedError()),
        ):
            result = await sync_ps3_device(device)

        assert result["status"] == "connection_failed"
        [session] = db_sync_session_handler.get_sessions(
            user_id=device.user_id, device_id=device.id
        )
        assert session.status == SyncSessionStatus.FAILED

    async def test_refuses_a_second_sync_of_the_same_console(
        self, device, connect, ps3
    ):
        # Another record of the console, even another user's, holds the same key.
        await async_cache.set(
            sync_handler._lock_key("192.168.1.115", PS3SyncConfig()), "1"
        )

        result = await sync_ps3_device(device)

        assert result["status"] == "busy"
        connect.assert_not_called()

    @pytest.mark.parametrize("address", ["127.0.0.1", "8.8.8.8", "console.local"])
    async def test_refuses_an_address_off_the_local_network(
        self, device, connect, ps3, address: str
    ):
        db_device_handler.update_device(
            device_id=device.id,
            user_id=device.user_id,
            data={"ip_address": address},
        )

        moved = db_device_handler.get_device_by_id(device.id)
        assert moved is not None

        result = await sync_ps3_device(moved)

        assert result["status"] == "error"
        connect.assert_not_called()

    async def test_needs_a_ps3_platform(self, device, connect):
        result = await sync_ps3_device(device)

        assert result["status"] == "error"
        connect.assert_not_called()


class TestConsoleWritesDuringSync:
    async def test_skips_a_folder_the_game_saved_while_read(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"before"})

        def game_saves(path: str) -> None:
            console.on_read = None
            console.add_save(
                FOLDER, {"SAVEDATA.000": b"after!"}, WRITTEN_AT + timedelta(hours=1)
            )

        console.on_read = game_saves

        counts = await run_sync(device, console, ps3)

        assert counts.pulled == 0
        assert slot_versions(admin_user, far_cry) == []
        assert (await run_sync(device, console, ps3)).pulled == 1

    async def test_abandons_a_push_when_the_game_saves_meanwhile(
        self, device, console, ps3, far_cry, admin_user
    ):
        console.add_save(FOLDER, {"PARAM.SFO": SFO, "SAVEDATA.000": b"old"})
        await run_sync(device, console, ps3)
        await store_server_version(
            admin_user,
            far_cry,
            {"PARAM.SFO": SFO, "SAVEDATA.000": b"restored"},
            origin=device.id,
            updated_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )

        def game_saves(path: str) -> None:
            console.on_write = None
            console.add_save(FOLDER, {"SAVEDATA.000": b"played"})

        console.on_write = game_saves

        counts = await run_sync(device, console, ps3)

        assert counts.pushed == 0
        assert console.folder(f"{SAVEDATA}/{FOLDER}")["SAVEDATA.000"] == b"played"
        assert {e.name for e in await console.list(SAVEDATA)} == {FOLDER}


class TestLimits:
    async def test_stops_reading_past_the_folder_budget(
        self, device, console, ps3, far_cry, admin_user, monkeypatch
    ):
        monkeypatch.setattr(sync_handler, "_FOLDER_MAX_BYTES", 10)
        console.add_save(FOLDER, {"PARAM.SFO": b"x" * 6, "SAVEDATA.000": b"y" * 6})
        # Listed small enough to pass, then each read returns more.
        for name in ("PARAM.SFO", "SAVEDATA.000"):
            console.listed_sizes[f"{SAVEDATA}/{FOLDER}/{name}"] = 1

        counts = await run_sync(device, console, ps3)

        assert counts.failed == 1
        assert slot_versions(admin_user, far_cry) == []
