from datetime import datetime, timezone

from sqlalchemy import update

from handler.database import db_deleted_asset_handler
from handler.database.base_handler import sync_session
from models.deleted_asset import MAX_REMEMBERED_HASHES, DeletedAsset
from models.rom import Rom
from models.user import User
from utils.datetime import to_utc


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

    def test_a_slot_differing_only_in_case_is_its_own_record(
        self, rom: Rom, admin_user: User
    ):
        for slot in ("Autosave", "autosave"):
            _record(admin_user, rom, slot, slot)

        records = {
            record.slot: record.content_hashes
            for record in db_deleted_asset_handler.get_deletions(
                user_id=admin_user.id, rom_ids=[rom.id]
            )
        }
        assert records == {"Autosave": ["Autosave"], "autosave": ["autosave"]}

    def test_ensuring_a_record_twice_keeps_one_empty_row(
        self, rom: Rom, admin_user: User
    ):
        for _ in range(2):
            db_deleted_asset_handler.ensure_record(admin_user.id, rom.id, "autosave")

        [record] = db_deleted_asset_handler.get_deletions(
            user_id=admin_user.id, rom_ids=[rom.id]
        )
        assert record.content_hashes == []


class TestRemovalTimes:
    def test_each_version_is_stamped_when_it_was_lost(self, rom: Rom, admin_user: User):
        before = datetime.now(timezone.utc)
        _record(admin_user, rom, "autosave", "lost")

        times = db_deleted_asset_handler.removal_times(
            admin_user.id, rom.id, "autosave"
        )

        assert list(times) == ["lost"]
        assert before <= times["lost"] <= datetime.now(timezone.utc)

    def test_a_version_lost_again_is_stamped_again(self, rom: Rom, admin_user: User):
        first = _record(admin_user, rom, "autosave", "again").removal_times()["again"]
        _record(admin_user, rom, "autosave", "other")
        again = _record(admin_user, rom, "autosave", "again").removal_times()["again"]

        assert again >= first

    def test_an_unstamped_version_falls_back_to_the_records_time(
        self, rom: Rom, admin_user: User
    ):
        record = _record(admin_user, rom, "autosave", "stamped")
        record.removed_at = {}
        record.content_hashes = ["legacy", "stamped"]

        assert record.removal_times() == {
            "legacy": to_utc(record.updated_at),
            "stamped": to_utc(record.updated_at),
        }

    def test_an_unstamped_version_keeps_its_time_when_another_is_lost(
        self, rom: Rom, admin_user: User
    ):
        """Recording bumps the record's own time, which must not move older losses."""
        legacy = _record(admin_user, rom, "autosave", "legacy")
        recorded = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with sync_session.begin() as session:
            session.execute(
                update(DeletedAsset)
                .where(DeletedAsset.id == legacy.id)
                .values(removed_at=None, updated_at=recorded)
            )

        times = _record(admin_user, rom, "autosave", "later").removal_times()

        assert times["legacy"] == recorded
        assert times["later"] > recorded

    def test_trimmed_versions_lose_their_stamps(self, rom: Rom, admin_user: User):
        for index in range(MAX_REMEMBERED_HASHES + 1):
            record = _record(admin_user, rom, "autosave", f"v{index}")

        assert set(record.removed_at or {}) == set(record.content_hashes)
        assert "v0" not in (record.removed_at or {})

    def test_a_slot_that_lost_nothing_has_no_times(self, rom: Rom, admin_user: User):
        assert db_deleted_asset_handler.removal_times(admin_user.id, rom.id, "x") == {}


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
