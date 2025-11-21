"""
Unit tests for DBStatesHandler platform filtering functionality.

This module tests the platform filtering fixes for DBStatesHandler to ensure
it properly filters by platform_id through the Rom relationship.
"""

from handler.database import db_state_handler
from models.assets import State
from models.platform import Platform
from models.rom import Rom
from models.user import User


class TestDBStatesHandlerPlatformFiltering:
    """Test suite for platform filtering in DBStatesHandler."""

    def test_get_states_without_platform_filter(self, admin_user: User, state: State):
        """Test that get_states returns all states when no platform filter is applied."""
        states = db_state_handler.get_states(user_id=admin_user.id)

        assert len(states) >= 1
        state_ids = [state.id for state in states]
        assert state.id in state_ids

    def test_get_states_with_platform_filter(
        self, admin_user: User, platform: Platform, state: State
    ):
        """Test that get_states filters correctly by platform_id."""
        states = db_state_handler.get_states(
            user_id=admin_user.id, platform_id=platform.id
        )

        assert len(states) == 1
        assert states[0].id == state.id
        assert states[0].file_name == "test_state.state"

    def test_get_states_with_rom_id_and_platform_filter(
        self, admin_user: User, platform: Platform, rom: Rom, state: State
    ):
        """Test that get_states works with both rom_id and platform_id filters."""
        states = db_state_handler.get_states(
            user_id=admin_user.id, rom_id=rom.id, platform_id=platform.id
        )

        assert len(states) == 1
        assert states[0].id == state.id

    def test_get_states_with_nonexistent_platform(self, admin_user: User, state: State):
        """Test that get_states returns empty list for nonexistent platform."""
        states = db_state_handler.get_states(user_id=admin_user.id, platform_id=999)

        assert len(states) == 0

    def test_platform_filtering_relationship_integrity(
        self, admin_user: User, platform: Platform, rom: Rom, state: State
    ):
        """Test that platform filtering correctly uses the Rom relationship."""
        assert rom.platform_id == platform.id

        states_platform = db_state_handler.get_states(
            user_id=admin_user.id, platform_id=platform.id
        )

        assert len(states_platform) == 1

    def test_multiple_states_same_platform(
        self, admin_user: User, platform: Platform, rom: Rom
    ):
        """Test filtering with multiple states on the same platform."""
        state1 = State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="state1.state",
            file_name_no_tags="state1",
            file_name_no_ext="state1",
            file_extension="state",
            emulator="emulator1",
            file_path=f"{platform.slug}/states/emulator1",
            file_size_bytes=100,
        )
        state2 = State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="state2.state",
            file_name_no_tags="state2",
            file_name_no_ext="state2",
            file_extension="state",
            emulator="emulator2",
            file_path=f"{platform.slug}/states/emulator2",
            file_size_bytes=200,
        )

        db_state_handler.add_state(state1)
        db_state_handler.add_state(state2)

        # Filter by platform should return both states
        states = db_state_handler.get_states(
            user_id=admin_user.id, platform_id=platform.id
        )

        assert len(states) == 2
        state_names = [state.file_name for state in states]
        assert "state1.state" in state_names
        assert "state2.state" in state_names

    def test_get_state_by_filename_with_platform_filter(
        self, admin_user: User, rom: Rom, state: State
    ):
        """Test that get_state_by_filename works correctly with platform filtering."""
        retrieved_state = db_state_handler.get_state_by_filename(
            user_id=admin_user.id, rom_id=rom.id, file_name=state.file_name
        )

        assert retrieved_state is not None
        assert retrieved_state.id == state.id
        assert retrieved_state.file_name == state.file_name

    def test_platform_filtering_with_different_emulators(
        self, admin_user: User, platform: Platform, rom: Rom
    ):
        """Test platform filtering with states from different emulators."""
        state_emulator1 = State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="state_emu1.state",
            file_name_no_tags="state_emu1",
            file_name_no_ext="state_emu1",
            file_extension="state",
            emulator="emulator1",
            file_path=f"{platform.slug}/states/emulator1",
            file_size_bytes=100,
        )
        state_emulator2 = State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="state_emu2.state",
            file_name_no_tags="state_emu2",
            file_name_no_ext="state_emu2",
            file_extension="state",
            emulator="emulator2",
            file_path=f"{platform.slug}/states/emulator2",
            file_size_bytes=200,
        )

        db_state_handler.add_state(state_emulator1)
        db_state_handler.add_state(state_emulator2)

        # Filter by platform should return both states regardless of emulator
        states = db_state_handler.get_states(
            user_id=admin_user.id, platform_id=platform.id
        )

        assert len(states) == 2
        emulators = [state.emulator for state in states]
        assert "emulator1" in emulators
        assert "emulator2" in emulators

    def test_get_state_by_id_with_platform_context(
        self, admin_user: User, platform: Platform, state: State
    ):
        """Test that get_state works correctly and maintains platform context."""
        retrieved_state = db_state_handler.get_state(user_id=admin_user.id, id=state.id)

        assert retrieved_state is not None
        assert retrieved_state.id == state.id
        assert retrieved_state.file_name == "test_state.state"

        # Verify the state is associated with the correct platform through ROM
        assert retrieved_state.rom.platform_id == platform.id
