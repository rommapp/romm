"""
Unit tests for DBSavesHandler platform filtering functionality.

This module tests the platform filtering fixes for DBSavesHandler to ensure
it properly filters by platform_id through the Rom relationship.
"""

from handler.database import db_save_handler
from models.assets import Save
from models.platform import Platform
from models.rom import Rom
from models.user import User


class TestDBSavesHandlerPlatformFiltering:
    """Test suite for platform filtering in DBSavesHandler."""

    def test_get_saves_without_platform_filter(self, admin_user: User, save: Save):
        """Test that get_saves returns all saves when no platform filter is applied."""
        saves = db_save_handler.get_saves(user_id=admin_user.id)

        assert len(saves) >= 1
        save_ids = [save.id for save in saves]
        assert save.id in save_ids

    def test_get_saves_with_platform_filter(
        self, admin_user: User, platform: Platform, save: Save
    ):
        """Test that get_saves filters correctly by platform_id."""
        saves = db_save_handler.get_saves(
            user_id=admin_user.id, platform_id=platform.id
        )

        assert len(saves) == 1
        assert saves[0].id == save.id
        assert saves[0].file_name == "test_save.sav"

    def test_get_saves_with_rom_id_and_platform_filter(
        self, admin_user: User, platform: Platform, rom: Rom, save: Save
    ):
        """Test that get_saves works with both rom_id and platform_id filters."""
        saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_id=rom.id, platform_id=platform.id
        )

        assert len(saves) == 1
        assert saves[0].id == save.id

    def test_get_saves_with_nonexistent_platform(self, admin_user: User, save: Save):
        """Test that get_saves returns empty list for nonexistent platform."""
        saves = db_save_handler.get_saves(user_id=admin_user.id, platform_id=999)

        assert len(saves) == 0

    def test_platform_filtering_relationship_integrity(
        self, admin_user: User, platform: Platform, rom: Rom, save: Save
    ):
        """Test that platform filtering correctly uses the Rom relationship."""
        assert rom.platform_id == platform.id

        saves_platform = db_save_handler.get_saves(
            user_id=admin_user.id, platform_id=platform.id
        )

        assert len(saves_platform) == 1

    def test_multiple_saves_same_platform(self, admin_user: User, rom: Rom):
        """Test filtering with multiple saves on the same platform."""
        save1 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="save1.sav",
            file_name_no_tags="save1",
            file_name_no_ext="save1",
            file_extension="sav",
            emulator="emulator1",
            file_path=f"{rom.platform_slug}/saves/emulator1",
            file_size_bytes=100,
        )
        save2 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="save2.sav",
            file_name_no_tags="save2",
            file_name_no_ext="save2",
            file_extension="sav",
            emulator="emulator2",
            file_path=f"{rom.platform_slug}/saves/emulator2",
            file_size_bytes=200,
        )

        db_save_handler.add_save(save1)
        db_save_handler.add_save(save2)

        # Filter by platform should return both saves
        saves = db_save_handler.get_saves(
            user_id=admin_user.id, platform_id=rom.platform_id
        )

        assert len(saves) == 2
        save_names = [save.file_name for save in saves]
        assert "save1.sav" in save_names
        assert "save2.sav" in save_names

    def test_get_save_by_filename_with_platform_filter(
        self, admin_user: User, rom: Rom, save: Save
    ):
        """Test that get_save_by_filename works correctly with platform filtering."""
        retrieved_save = db_save_handler.get_save_by_filename(
            user_id=admin_user.id, rom_id=rom.id, file_name=save.file_name
        )

        assert retrieved_save is not None
        assert retrieved_save.id == save.id
        assert retrieved_save.file_name == save.file_name

    def test_platform_filtering_with_different_emulators(
        self, admin_user: User, platform: Platform, rom: Rom
    ):
        """Test platform filtering with saves from different emulators."""
        save_emulator1 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="save_emu1.sav",
            file_name_no_tags="save_emu1",
            file_name_no_ext="save_emu1",
            file_extension="sav",
            emulator="emulator1",
            file_path=f"{platform.slug}/saves/emulator1",
            file_size_bytes=100,
        )
        save_emulator2 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="save_emu2.sav",
            file_name_no_tags="save_emu2",
            file_name_no_ext="save_emu2",
            file_extension="sav",
            emulator="emulator2",
            file_path=f"{platform.slug}/saves/emulator2",
            file_size_bytes=200,
        )

        db_save_handler.add_save(save_emulator1)
        db_save_handler.add_save(save_emulator2)

        # Filter by platform should return both saves regardless of emulator
        saves = db_save_handler.get_saves(
            user_id=admin_user.id, platform_id=platform.id
        )

        assert len(saves) == 2
        emulators = [save.emulator for save in saves]
        assert "emulator1" in emulators
        assert "emulator2" in emulators

    def test_get_save_by_id_with_platform_context(
        self, admin_user: User, platform: Platform, save: Save
    ):
        """Test that get_save works correctly and maintains platform context."""
        retrieved_save = db_save_handler.get_save(user_id=admin_user.id, id=save.id)

        assert retrieved_save is not None
        assert retrieved_save.id == save.id
        assert retrieved_save.file_name == "test_save.sav"

        # Verify the save is associated with the correct platform through ROM
        assert retrieved_save.rom.platform_id == platform.id


class TestDBSavesHandlerSlotFiltering:
    def test_get_saves_with_slot_filter(self, admin_user: User, rom: Rom):
        save1 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="slot_test_1.sav",
            file_name_no_tags="slot_test_1",
            file_name_no_ext="slot_test_1",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="Slot A",
        )
        save2 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="slot_test_2.sav",
            file_name_no_tags="slot_test_2",
            file_name_no_ext="slot_test_2",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="Slot A",
        )
        save3 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="slot_test_3.sav",
            file_name_no_tags="slot_test_3",
            file_name_no_ext="slot_test_3",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="Slot B",
        )

        db_save_handler.add_save(save1)
        db_save_handler.add_save(save2)
        db_save_handler.add_save(save3)

        slot_a_saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_id=rom.id, slot="Slot A"
        )
        assert len(slot_a_saves) == 2
        assert all(s.slot == "Slot A" for s in slot_a_saves)

        slot_b_saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_id=rom.id, slot="Slot B"
        )
        assert len(slot_b_saves) == 1
        assert slot_b_saves[0].slot == "Slot B"

    def test_get_saves_with_null_slot_filter(self, admin_user: User, rom: Rom):
        save_with_slot = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="with_slot.sav",
            file_name_no_tags="with_slot",
            file_name_no_ext="with_slot",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="Main",
        )
        save_without_slot = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="without_slot.sav",
            file_name_no_tags="without_slot",
            file_name_no_ext="without_slot",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot=None,
        )

        db_save_handler.add_save(save_with_slot)
        db_save_handler.add_save(save_without_slot)

        all_saves = db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id)
        assert len(all_saves) >= 2

    def test_get_saves_order_by(self, admin_user: User, rom: Rom):
        from datetime import datetime, timedelta, timezone

        base_time = datetime.now(timezone.utc)

        save1 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="order_test_1.sav",
            file_name_no_tags="order_test_1",
            file_name_no_ext="order_test_1",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="order_test",
        )
        save2 = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="order_test_2.sav",
            file_name_no_tags="order_test_2",
            file_name_no_ext="order_test_2",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="order_test",
        )

        created1 = db_save_handler.add_save(save1)
        created2 = db_save_handler.add_save(save2)

        db_save_handler.update_save(
            created1.id, {"updated_at": base_time - timedelta(hours=2)}
        )
        db_save_handler.update_save(
            created2.id, {"updated_at": base_time - timedelta(hours=1)}
        )

        ordered_saves_desc = db_save_handler.get_saves(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="order_test",
            order_by="updated_at",
        )

        assert len(ordered_saves_desc) == 2
        assert ordered_saves_desc[0].id == created2.id
        assert ordered_saves_desc[1].id == created1.id

        ordered_saves_asc = db_save_handler.get_saves(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="order_test",
            order_by="updated_at",
            order_dir="asc",
        )

        assert len(ordered_saves_asc) == 2
        assert ordered_saves_asc[0].id == created1.id
        assert ordered_saves_asc[1].id == created2.id


class TestDBSavesHandlerSummary:
    def test_get_saves_summary_basic(self, admin_user: User, rom: Rom):
        from datetime import datetime, timedelta, timezone

        base_time = datetime.now(timezone.utc)

        configs = [
            ("summary_a_1.sav", "Slot A", -3),
            ("summary_a_2.sav", "Slot A", -1),
            ("summary_b_1.sav", "Slot B", -2),
            ("summary_none_1.sav", None, -4),
        ]

        for filename, slot, hours_offset in configs:
            save = Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=filename,
                file_name_no_tags=filename.replace(".sav", ""),
                file_name_no_ext=filename.replace(".sav", ""),
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot=slot,
            )
            created = db_save_handler.add_save(save)
            db_save_handler.update_save(
                created.id, {"updated_at": base_time + timedelta(hours=hours_offset)}
            )

        summary = db_save_handler.get_saves_summary(
            user_id=admin_user.id, rom_id=rom.id
        )

        assert "total_count" in summary
        assert "slots" in summary
        assert summary["total_count"] == 4
        assert len(summary["slots"]) == 3

    def test_get_saves_summary_latest_per_slot(self, admin_user: User, rom: Rom):
        from datetime import datetime, timedelta, timezone

        base_time = datetime.now(timezone.utc)

        old_save = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="latest_test_old.sav",
            file_name_no_tags="latest_test_old",
            file_name_no_ext="latest_test_old",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="latest_test",
        )
        new_save = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="latest_test_new.sav",
            file_name_no_tags="latest_test_new",
            file_name_no_ext="latest_test_new",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="latest_test",
        )

        old_created = db_save_handler.add_save(old_save)
        new_created = db_save_handler.add_save(new_save)

        db_save_handler.update_save(
            old_created.id, {"updated_at": base_time - timedelta(hours=5)}
        )
        db_save_handler.update_save(
            new_created.id, {"updated_at": base_time - timedelta(hours=1)}
        )

        summary = db_save_handler.get_saves_summary(
            user_id=admin_user.id, rom_id=rom.id
        )

        latest_slot = next(
            (s for s in summary["slots"] if s["slot"] == "latest_test"), None
        )
        assert latest_slot is not None
        assert latest_slot["count"] == 2
        assert latest_slot["latest"].file_name == "latest_test_new.sav"

    def test_get_saves_summary_empty_rom(self, admin_user: User):
        summary = db_save_handler.get_saves_summary(
            user_id=admin_user.id, rom_id=999999
        )

        assert summary["total_count"] == 0
        assert summary["slots"] == []

    def test_get_saves_summary_count_accuracy(self, admin_user: User, rom: Rom):
        for i in range(5):
            save = Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=f"count_test_{i}.sav",
                file_name_no_tags=f"count_test_{i}",
                file_name_no_ext=f"count_test_{i}",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="count_test",
            )
            db_save_handler.add_save(save)

        summary = db_save_handler.get_saves_summary(
            user_id=admin_user.id, rom_id=rom.id
        )

        count_slot = next(
            (s for s in summary["slots"] if s["slot"] == "count_test"), None
        )
        assert count_slot is not None
        assert count_slot["count"] == 5
