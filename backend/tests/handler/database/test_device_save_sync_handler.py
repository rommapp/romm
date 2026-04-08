from datetime import datetime, timezone

from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_save_handler,
)
from models.assets import Save
from models.device import Device
from models.rom import Rom
from models.user import User


class TestGetSync:
    def test_get_existing_sync(self, admin_user: User, rom: Rom, save: Save):
        device = db_device_handler.add_device(
            Device(id="sync-dev-1", user_id=admin_user.id)
        )
        db_device_save_sync_handler.upsert_sync(device.id, save.id)

        result = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert result is not None
        assert result.device_id == device.id
        assert result.save_id == save.id

    def test_get_nonexistent_sync(self, admin_user: User):
        result = db_device_save_sync_handler.get_sync("no-device", 999)
        assert result is None


class TestGetSyncsForDeviceAndSaves:
    def test_returns_matching_syncs(self, admin_user: User, rom: Rom):
        device = db_device_handler.add_device(
            Device(id="bulk-dev-1", user_id=admin_user.id)
        )
        saves = []
        for i in range(3):
            s = db_save_handler.add_save(
                Save(
                    rom_id=rom.id,
                    user_id=admin_user.id,
                    file_name=f"bulk_{i}.sav",
                    file_name_no_tags=f"bulk_{i}",
                    file_name_no_ext=f"bulk_{i}",
                    file_extension="sav",
                    emulator="emu",
                    file_path=f"{rom.platform_slug}/saves",
                    file_size_bytes=100,
                )
            )
            saves.append(s)
            db_device_save_sync_handler.upsert_sync(device.id, s.id)

        result = db_device_save_sync_handler.get_syncs_for_device_and_saves(
            device.id, [saves[0].id, saves[2].id]
        )
        assert len(result) == 2
        ids = {r.save_id for r in result}
        assert saves[0].id in ids
        assert saves[2].id in ids

    def test_empty_save_ids_returns_empty(self, admin_user: User):
        result = db_device_save_sync_handler.get_syncs_for_device_and_saves(
            "any-dev", []
        )
        assert result == []


class TestUpsertSync:
    def test_creates_new_sync(self, admin_user: User, rom: Rom, save: Save):
        device = db_device_handler.add_device(
            Device(id="upsert-dev-1", user_id=admin_user.id)
        )
        result = db_device_save_sync_handler.upsert_sync(device.id, save.id)

        assert result.device_id == device.id
        assert result.save_id == save.id
        assert result.is_untracked is False
        assert result.last_synced_at is not None

    def test_updates_existing_sync(self, admin_user: User, rom: Rom, save: Save):
        device = db_device_handler.add_device(
            Device(id="upsert-dev-2", user_id=admin_user.id)
        )
        earlier = datetime(2020, 1, 1, tzinfo=timezone.utc)
        db_device_save_sync_handler.upsert_sync(device.id, save.id, synced_at=earlier)

        later = datetime(2025, 6, 1, tzinfo=timezone.utc)
        result = db_device_save_sync_handler.upsert_sync(
            device.id, save.id, synced_at=later
        )

        assert result.last_synced_at == later
        assert result.is_untracked is False

    def test_upsert_clears_untracked(self, admin_user: User, rom: Rom, save: Save):
        device = db_device_handler.add_device(
            Device(id="upsert-dev-3", user_id=admin_user.id)
        )
        db_device_save_sync_handler.set_untracked(device.id, save.id, True)
        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.is_untracked is True

        db_device_save_sync_handler.upsert_sync(device.id, save.id)
        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.is_untracked is False

    def test_upsert_with_custom_timestamp(self, admin_user: User, rom: Rom, save: Save):
        device = db_device_handler.add_device(
            Device(id="upsert-dev-4", user_id=admin_user.id)
        )
        ts = datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = db_device_save_sync_handler.upsert_sync(
            device.id, save.id, synced_at=ts
        )
        assert result.last_synced_at == ts


class TestSetUntracked:
    def test_set_untracked_on_existing(self, admin_user: User, rom: Rom, save: Save):
        device = db_device_handler.add_device(
            Device(id="untrack-dev-1", user_id=admin_user.id)
        )
        db_device_save_sync_handler.upsert_sync(device.id, save.id)

        result = db_device_save_sync_handler.set_untracked(device.id, save.id, True)
        assert result is not None
        assert result.is_untracked is True

    def test_set_tracked_on_existing(self, admin_user: User, rom: Rom, save: Save):
        device = db_device_handler.add_device(
            Device(id="untrack-dev-2", user_id=admin_user.id)
        )
        db_device_save_sync_handler.upsert_sync(device.id, save.id)
        db_device_save_sync_handler.set_untracked(device.id, save.id, True)

        result = db_device_save_sync_handler.set_untracked(device.id, save.id, False)
        assert result is not None
        assert result.is_untracked is False

    def test_set_untracked_creates_new_record(
        self, admin_user: User, rom: Rom, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="untrack-dev-3", user_id=admin_user.id)
        )
        result = db_device_save_sync_handler.set_untracked(device.id, save.id, True)
        assert result is not None
        assert result.is_untracked is True
        assert result.device_id == device.id

    def test_set_tracked_nonexistent_returns_none(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="untrack-dev-4", user_id=admin_user.id)
        )
        result = db_device_save_sync_handler.set_untracked(device.id, 999999, False)
        assert result is None


class TestDeleteSyncsForDevice:
    def test_deletes_all_syncs(self, admin_user: User, rom: Rom):
        device = db_device_handler.add_device(
            Device(id="del-dev-1", user_id=admin_user.id)
        )
        for i in range(3):
            s = db_save_handler.add_save(
                Save(
                    rom_id=rom.id,
                    user_id=admin_user.id,
                    file_name=f"del_{i}.sav",
                    file_name_no_tags=f"del_{i}",
                    file_name_no_ext=f"del_{i}",
                    file_extension="sav",
                    emulator="emu",
                    file_path=f"{rom.platform_slug}/saves",
                    file_size_bytes=100,
                )
            )
            db_device_save_sync_handler.upsert_sync(device.id, s.id)

        db_device_save_sync_handler.delete_syncs_for_device(device.id)

        result = db_device_save_sync_handler.get_syncs_for_device_and_saves(
            device.id, [1, 2, 3]
        )
        assert len(result) == 0

    def test_delete_nonexistent_device_no_error(self):
        db_device_save_sync_handler.delete_syncs_for_device("nonexistent-device")
