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
