from datetime import datetime, timedelta, timezone

from handler.database import db_deleted_asset_handler
from models.deleted_asset import MAX_REMEMBERED_HASHES
from models.rom import Rom
from models.user import User


class TestRecordDeletion:
    def test_remembers_the_slot_that_was_emptied(self, rom: Rom, admin_user: User):
        deleted_at = datetime.now(timezone.utc)

        record = db_deleted_asset_handler.record_deletion(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="autosave",
            content_hash="abc123",
            deleted_at=deleted_at,
        )

        assert record.id is not None
        assert record.slot == "autosave"
        assert record.content_hashes == ["abc123"]

    def test_a_slot_emptied_twice_keeps_one_record(self, rom: Rom, admin_user: User):
        # A slot can be emptied, refilled and emptied again, and a device may
        # still hold either version, so both are remembered on the one row.
        first = datetime.now(timezone.utc) - timedelta(days=2)
        db_deleted_asset_handler.record_deletion(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="autosave",
            content_hash="old",
            deleted_at=first,
        )
        db_deleted_asset_handler.record_deletion(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="autosave",
            content_hash="new",
            deleted_at=first + timedelta(days=1),
        )

        records = [
            record
            for record in db_deleted_asset_handler.get_deletions(
                user_id=admin_user.id, rom_ids=[rom.id]
            )
            if record.slot == "autosave"
        ]
        assert len(records) == 1
        assert records[0].content_hashes == ["old", "new"]

    def test_a_named_slot_is_its_own_record(self, rom: Rom, admin_user: User):
        for slot in ("autosave", "main_quest"):
            db_deleted_asset_handler.record_deletion(
                user_id=admin_user.id,
                rom_id=rom.id,
                slot=slot,
                content_hash=None,
                deleted_at=datetime.now(timezone.utc),
            )

        slots = {
            record.slot
            for record in db_deleted_asset_handler.get_deletions(
                user_id=admin_user.id, rom_ids=[rom.id]
            )
        }
        assert {"autosave", "main_quest"} <= slots


class TestGetDeletions:
    def test_an_empty_scope_asks_about_nothing(self, rom: Rom, admin_user: User):
        # A client that named no ROMs is not asking about every ROM it has ever
        # deleted a save for.
        db_deleted_asset_handler.record_deletion(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="autosave",
            content_hash=None,
            deleted_at=datetime.now(timezone.utc),
        )

        assert db_deleted_asset_handler.get_deletions(admin_user.id, rom_ids=[]) == []
        assert db_deleted_asset_handler.get_deletions(admin_user.id, rom_ids=None)


class TestRememberedVersions:
    def test_the_same_version_twice_is_remembered_once(
        self, rom: Rom, admin_user: User
    ):
        for _ in range(3):
            record = db_deleted_asset_handler.record_deletion(
                user_id=admin_user.id,
                rom_id=rom.id,
                slot="repeats",
                content_hash="same",
                deleted_at=datetime.now(timezone.utc),
            )

        assert record.content_hashes == ["same"]

    def test_a_version_lost_again_is_the_newest(self, rom: Rom, admin_user: User):
        for content_hash in ("first", "second", "first"):
            record = db_deleted_asset_handler.record_deletion(
                user_id=admin_user.id,
                rom_id=rom.id,
                slot="relost",
                content_hash=content_hash,
                deleted_at=datetime.now(timezone.utc),
            )

        assert record.content_hashes == ["second", "first"]

    def test_the_oldest_versions_fall_off(self, rom: Rom, admin_user: User):
        # A slot emptied this often is one whose oldest versions no device
        # still holds, and the row is read on every negotiation.
        for index in range(MAX_REMEMBERED_HASHES + 5):
            record = db_deleted_asset_handler.record_deletion(
                user_id=admin_user.id,
                rom_id=rom.id,
                slot="many",
                content_hash=f"hash-{index}",
                deleted_at=datetime.now(timezone.utc),
            )

        assert len(record.content_hashes) == MAX_REMEMBERED_HASHES
        assert record.content_hashes[-1] == f"hash-{MAX_REMEMBERED_HASHES + 4}"
        assert "hash-0" not in record.content_hashes
