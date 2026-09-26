from handler.database import db_deleted_asset_handler
from models.deleted_asset import MAX_REMEMBERED_HASHES, DeletedAsset
from models.rom import Rom
from models.user import User


def _record(user: User, rom: Rom, slot: str, content_hash: str) -> DeletedAsset:
    return db_deleted_asset_handler.record_deletion(
        user_id=user.id, rom_id=rom.id, slot=slot, content_hash=content_hash
    )


class TestRecordDeletion:
    def test_remembers_the_slot_that_was_emptied(self, rom: Rom, admin_user: User):
        record = _record(admin_user, rom, "autosave", "abc123")

        assert record.id is not None
        assert record.slot == "autosave"
        assert record.content_hashes == ["abc123"]

    def test_a_slot_emptied_twice_keeps_one_record(self, rom: Rom, admin_user: User):
        # A device may still hold either version, so both stay on the one row.
        _record(admin_user, rom, "autosave", "old")
        _record(admin_user, rom, "autosave", "new")

        [record] = db_deleted_asset_handler.get_deletions(
            user_id=admin_user.id, rom_ids=[rom.id]
        )
        assert record.content_hashes == ["old", "new"]

    def test_a_named_slot_is_its_own_record(self, rom: Rom, admin_user: User):
        for slot in ("autosave", "main_quest"):
            _record(admin_user, rom, slot, "abc123")

        slots = {
            record.slot
            for record in db_deleted_asset_handler.get_deletions(
                user_id=admin_user.id, rom_ids=[rom.id]
            )
        }
        assert slots == {"autosave", "main_quest"}


class TestGetDeletions:
    def test_an_empty_scope_asks_about_nothing(self, rom: Rom, admin_user: User):
        _record(admin_user, rom, "autosave", "abc123")

        assert db_deleted_asset_handler.get_deletions(admin_user.id, rom_ids=[]) == []


class TestRememberedVersions:
    def test_the_same_version_twice_is_remembered_once(
        self, rom: Rom, admin_user: User
    ):
        for _ in range(3):
            record = _record(admin_user, rom, "repeats", "same")

        assert record.content_hashes == ["same"]

    def test_a_version_lost_again_is_the_newest(self, rom: Rom, admin_user: User):
        for content_hash in ("first", "second", "first"):
            record = _record(admin_user, rom, "relost", content_hash)

        assert record.content_hashes == ["second", "first"]

    def test_the_oldest_versions_fall_off(self, rom: Rom, admin_user: User):
        for index in range(MAX_REMEMBERED_HASHES + 5):
            record = _record(admin_user, rom, "many", f"hash-{index}")

        assert len(record.content_hashes) == MAX_REMEMBERED_HASHES
        assert record.content_hashes[-1] == f"hash-{MAX_REMEMBERED_HASHES + 4}"
        assert "hash-0" not in record.content_hashes
