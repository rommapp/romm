"""
Unit tests for DBSavesHandler platform filtering functionality.

This module tests the platform filtering fixes for DBSavesHandler to ensure
it properly filters by platform_id through the Rom relationship.
"""

import ast
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from sqlalchemy import Delete, event
from sqlalchemy.exc import NoResultFound

import handler.database.saves_handler as saves_handler_module
from handler.database import db_deleted_asset_handler, db_save_handler
from handler.database.base_handler import sync_engine
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
            user_id=admin_user.id, rom_ids=[rom.id], platform_id=platform.id
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
            user_id=admin_user.id,
            rom_id=rom.id,
            file_name=save.file_name,
            slot=save.slot,
        )

        assert retrieved_save is not None
        assert retrieved_save.id == save.id
        assert retrieved_save.file_name == save.file_name

    def test_get_save_by_filename_slotless_ignores_slotted_save(
        self, admin_user: User, rom: Rom
    ):
        """A slot-less lookup must not match a same-named save in a named slot."""
        slotted = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="shared.sav",
            file_name_no_tags="shared",
            file_name_no_ext="shared",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="Slot A",
        )
        slotted = db_save_handler.add_save(slotted)

        # No null-slot save exists, so a slot-less lookup should find nothing.
        assert (
            db_save_handler.get_save_by_filename(
                user_id=admin_user.id, rom_id=rom.id, file_name="shared.sav", slot=None
            )
            is None
        )

        # The named-slot lookup still resolves the slotted save.
        found = db_save_handler.get_save_by_filename(
            user_id=admin_user.id,
            rom_id=rom.id,
            file_name="shared.sav",
            slot="Slot A",
        )
        assert found is not None
        assert found.id == slotted.id

    def test_get_save_by_filename_slotted_ignores_slotless_save(
        self, admin_user: User, rom: Rom
    ):
        """A named-slot lookup must not match a same-named null-slot save."""
        slotless = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="shared.sav",
            file_name_no_tags="shared",
            file_name_no_ext="shared",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot=None,
        )
        slotless = db_save_handler.add_save(slotless)

        assert (
            db_save_handler.get_save_by_filename(
                user_id=admin_user.id,
                rom_id=rom.id,
                file_name="shared.sav",
                slot="Slot A",
            )
            is None
        )

        found = db_save_handler.get_save_by_filename(
            user_id=admin_user.id, rom_id=rom.id, file_name="shared.sav", slot=None
        )
        assert found is not None
        assert found.id == slotless.id

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
            user_id=admin_user.id, rom_ids=[rom.id], slot="Slot A"
        )
        assert len(slot_a_saves) == 2
        assert all(s.slot == "Slot A" for s in slot_a_saves)

        slot_b_saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_ids=[rom.id], slot="Slot B"
        )
        assert len(slot_b_saves) == 1
        assert slot_b_saves[0].slot == "Slot B"

    @pytest.mark.parametrize(
        "slot,sibling",
        [("autosave", "Autosave"), ("Cafe", "Café"), ("autosave", "autosave ")],
        ids=["case", "accent", "trailing-space"],
    )
    def test_a_slot_is_matched_exactly(
        self, admin_user: User, rom: Rom, slot: str, sibling: str
    ):
        """Sync pairs slots in Python, so the database must not fold them."""
        for index, name in enumerate((slot, sibling)):
            db_save_handler.add_save(
                Save(
                    rom_id=rom.id,
                    user_id=admin_user.id,
                    file_name=f"exact_{index}.sav",
                    file_name_no_tags=f"exact_{index}",
                    file_name_no_ext=f"exact_{index}",
                    file_extension="sav",
                    file_path=f"{rom.platform_slug}/saves",
                    file_size_bytes=100,
                    slot=name,
                )
            )

        [found] = db_save_handler.get_saves(
            user_id=admin_user.id, rom_ids=[rom.id], slot=slot
        )
        assert found.slot == slot

        db_save_handler.prune_slot(
            user_id=admin_user.id, rom_id=rom.id, slot=slot, keep=0
        )
        [kept] = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        assert kept.slot == sibling

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

        all_saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
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
            rom_ids=[rom.id],
            slot="order_test",
            order_by="updated_at",
        )

        assert len(ordered_saves_desc) == 2
        assert ordered_saves_desc[0].id == created2.id
        assert ordered_saves_desc[1].id == created1.id

        ordered_saves_asc = db_save_handler.get_saves(
            user_id=admin_user.id,
            rom_ids=[rom.id],
            slot="order_test",
            order_by="updated_at",
            order_dir="asc",
        )

        assert len(ordered_saves_asc) == 2
        assert ordered_saves_asc[0].id == created1.id
        assert ordered_saves_asc[1].id == created2.id


class TestDBSavesHandlerGetSaveByContentHash:
    """Pin the slot filter behavior of get_save_by_content_hash (commit
    3d71ef3f6). Legacy callers still pass slot=None and expect cross-slot
    lookup, while sync negotiation passes a concrete slot value and expects
    a strict match.
    """

    def test_returns_row_matching_slot_when_multiple_slots_share_hash(
        self, admin_user: User, rom: Rom
    ):
        """Two rows share (rom_id, user_id, content_hash) but differ in slot.
        A call with a specific slot must return the row with that slot, not
        the other."""
        shared_hash = "abc123abc123abc123abc123abc12345"

        slot_a = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="hash_match_a.sav",
                file_name_no_tags="hash_match_a",
                file_name_no_ext="hash_match_a",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="Slot A",
                content_hash=shared_hash,
            )
        )
        slot_b = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="hash_match_b.sav",
                file_name_no_tags="hash_match_b",
                file_name_no_ext="hash_match_b",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="Slot B",
                content_hash=shared_hash,
            )
        )

        result_a = db_save_handler.get_save_by_content_hash(
            user_id=admin_user.id,
            rom_id=rom.id,
            content_hash=shared_hash,
            slot="Slot A",
        )
        assert result_a is not None
        assert result_a.id == slot_a.id

        result_b = db_save_handler.get_save_by_content_hash(
            user_id=admin_user.id,
            rom_id=rom.id,
            content_hash=shared_hash,
            slot="Slot B",
        )
        assert result_b is not None
        assert result_b.id == slot_b.id

    def test_returns_none_when_slot_does_not_match(self, admin_user: User, rom: Rom):
        """A single row exists. Querying with a different slot value returns
        None, even though the (rom_id, user_id, content_hash) tuple matches."""
        target_hash = "ffffffffffffffffffffffffffffffff"

        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="only_slot.sav",
                file_name_no_tags="only_slot",
                file_name_no_ext="only_slot",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="autosave",
                content_hash=target_hash,
            )
        )

        result = db_save_handler.get_save_by_content_hash(
            user_id=admin_user.id,
            rom_id=rom.id,
            content_hash=target_hash,
            slot="manual",
        )
        assert result is None

    def test_slot_none_finds_row_with_concrete_slot(self, admin_user: User, rom: Rom):
        """Legacy / cross-slot lookup: passing slot=None must not filter by
        slot at all and must still return the row, regardless of the row's
        own slot value."""
        target_hash = "1234567890abcdef1234567890abcdef"

        created = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="cross_slot.sav",
                file_name_no_tags="cross_slot",
                file_name_no_ext="cross_slot",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="autosave",
                content_hash=target_hash,
            )
        )

        result = db_save_handler.get_save_by_content_hash(
            user_id=admin_user.id,
            rom_id=rom.id,
            content_hash=target_hash,
            slot=None,
        )
        assert result is not None
        assert result.id == created.id


class TestDBSavesHandlerSlotNotNullFilter:
    """Pin the slot_not_null kwarg: when true, archival/null-slot saves are
    excluded; when false (default), they are returned alongside slot-bound
    rows. Sync callsites use slot_not_null=True so the database does the
    filter instead of pulling the whole table into Python."""

    def test_slot_not_null_false_returns_both(self, admin_user: User, rom: Rom):
        slot_save = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="slotted.sav",
            file_name_no_tags="slotted",
            file_name_no_ext="slotted",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="autosave",
        )
        archival_save = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="archival.sav",
            file_name_no_tags="archival",
            file_name_no_ext="archival",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot=None,
        )
        db_save_handler.add_save(slot_save)
        db_save_handler.add_save(archival_save)

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])

        names = {s.file_name for s in saves}
        assert "slotted.sav" in names
        assert "archival.sav" in names

    def test_slot_not_null_true_excludes_null_slot(self, admin_user: User, rom: Rom):
        slot_save = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="slotted_only.sav",
            file_name_no_tags="slotted_only",
            file_name_no_ext="slotted_only",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="autosave",
        )
        archival_save = Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="archival_only.sav",
            file_name_no_tags="archival_only",
            file_name_no_ext="archival_only",
            file_extension="sav",
            emulator="test_emu",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot=None,
        )
        db_save_handler.add_save(slot_save)
        db_save_handler.add_save(archival_save)

        saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_ids=[rom.id], slot_not_null=True
        )

        names = {s.file_name for s in saves}
        assert "slotted_only.sav" in names
        assert "archival_only.sav" not in names
        assert all(s.slot is not None for s in saves)

    def test_slot_not_null_true_composes_with_slot_value(
        self, admin_user: User, rom: Rom
    ):
        """slot_not_null and slot can both be set; the explicit slot filter
        wins (and is implicitly not-null), so slot_not_null=True is a no-op
        in that case. Pin that behavior so callers don't have to reason
        about the interaction."""
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="compose_a.sav",
                file_name_no_tags="compose_a",
                file_name_no_ext="compose_a",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="A",
            )
        )
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="compose_b.sav",
                file_name_no_tags="compose_b",
                file_name_no_ext="compose_b",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="B",
            )
        )

        saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_ids=[rom.id], slot="A", slot_not_null=True
        )

        assert len(saves) == 1
        assert saves[0].slot == "A"


class TestDBSavesHandlerGetSavesAfterId:
    """Cover keyset pagination used by the recompute_save_content_hashes
    maintenance task. Per-page bounded reads avoid materializing the full
    saves table on instances with very large libraries."""

    def test_paginates_in_order_and_terminates(self, admin_user: User, rom: Rom):
        created_ids = []
        for i in range(5):
            created = db_save_handler.add_save(
                Save(
                    rom_id=rom.id,
                    user_id=admin_user.id,
                    file_name=f"page_{i}.sav",
                    file_name_no_tags=f"page_{i}",
                    file_name_no_ext=f"page_{i}",
                    file_extension="sav",
                    emulator="test_emu",
                    file_path=f"{rom.platform_slug}/saves",
                    file_size_bytes=100,
                    slot=f"slot_{i}",
                )
            )
            created_ids.append(created.id)

        seen: list[int] = []
        last_id = 0
        while True:
            batch = db_save_handler.get_saves_after_id(after_id=last_id, limit=2)
            if not batch:
                break
            for s in batch:
                seen.append(s.id)
                last_id = s.id

        for cid in created_ids:
            assert cid in seen
        # IDs returned monotonically by primary key
        assert seen == sorted(seen)

    def test_after_id_excludes_anchor_row(self, admin_user: User, rom: Rom):
        created = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="anchor.sav",
                file_name_no_tags="anchor",
                file_name_no_ext="anchor",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot="anchor_slot",
            )
        )

        batch = db_save_handler.get_saves_after_id(after_id=created.id, limit=10)

        assert all(s.id > created.id for s in batch)


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


class TestDBSavesHandlerGetLatestSavesForRoms:
    """Cover the continue-playing rail's batch lookup of the newest save per
    ROM."""

    def test_returns_newest_save_per_rom(self, admin_user: User, rom: Rom):
        from datetime import datetime, timedelta, timezone

        base_time = datetime.now(timezone.utc)

        older = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="latest_old.sav",
                file_name_no_tags="latest_old",
                file_name_no_ext="latest_old",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
            )
        )
        newer = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="latest_new.sav",
                file_name_no_tags="latest_new",
                file_name_no_ext="latest_new",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
            )
        )
        db_save_handler.update_save(
            older.id, {"updated_at": base_time - timedelta(hours=2)}
        )
        db_save_handler.update_save(
            newer.id, {"updated_at": base_time - timedelta(hours=1)}
        )

        latest = db_save_handler.get_latest_saves_for_roms(
            user_id=admin_user.id, rom_ids=[rom.id]
        )

        assert set(latest.keys()) == {rom.id}
        assert latest[rom.id].id == newer.id

    def test_empty_rom_ids_returns_empty_dict(self, admin_user: User):
        assert (
            db_save_handler.get_latest_saves_for_roms(user_id=admin_user.id, rom_ids=[])
            == {}
        )

    def test_excludes_other_users_saves(
        self, admin_user: User, editor_user: User, rom: Rom
    ):
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=editor_user.id,
                file_name="other_user.sav",
                file_name_no_tags="other_user",
                file_name_no_ext="other_user",
                file_extension="sav",
                emulator="test_emu",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
            )
        )

        latest = db_save_handler.get_latest_saves_for_roms(
            user_id=admin_user.id, rom_ids=[rom.id]
        )

        assert latest == {}


class TestGetSavesRomIdsScope:
    """Test suite for the `rom_ids` scope on DBSavesHandler.get_saves."""

    def test_scopes_to_listed_roms(
        self, admin_user: User, rom: Rom, save: Save, second_save: Save
    ):
        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])

        assert [s.id for s in saves] == [save.id]

    def test_scopes_to_multiple_roms(
        self,
        admin_user: User,
        rom: Rom,
        second_rom: Rom,
        save: Save,
        second_save: Save,
    ):
        saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_ids=[rom.id, second_rom.id]
        )

        assert {s.id for s in saves} == {save.id, second_save.id}

    def test_empty_scope_returns_nothing(self, admin_user: User, save: Save):
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[]) == []

    def test_omitted_scope_returns_everything(self, admin_user: User, save: Save):
        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=None)

        assert save.id in [s.id for s in saves]

    def test_combines_with_slot_filter(
        self, admin_user: User, rom: Rom, save: Save, archival_save: Save
    ):
        saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_ids=[rom.id], slot_not_null=True
        )

        assert [s.id for s in saves] == [save.id]


class TestDBSavesHandlerRecordsLostVersions:
    """Every way a version leaves its slot is remembered for sync."""

    @staticmethod
    def _add(
        user: User, rom: Rom, stem: str, slot: str | None, content_hash: str | None
    ) -> Save:
        return db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=user.id,
                file_name=f"{stem}.sav",
                file_name_no_tags=stem,
                file_name_no_ext=stem,
                file_extension="sav",
                file_path=f"{rom.platform_slug}/saves",
                file_size_bytes=100,
                slot=slot,
                content_hash=content_hash,
            )
        )

    @staticmethod
    def _lost(user: User, rom: Rom) -> dict[str, list[str]]:
        return {
            record.slot: record.content_hashes
            for record in db_deleted_asset_handler.get_deletions(
                user_id=user.id, rom_ids=[rom.id]
            )
        }

    def test_a_deleted_version_is_recorded(self, admin_user: User, rom: Rom):
        save = self._add(admin_user, rom, "deleted", "autosave", "gone")

        db_save_handler.delete_save(save.id)

        assert self._lost(admin_user, rom) == {"autosave": ["gone"]}

    def test_a_deleted_version_never_hashed_takes_the_callers_hash(
        self, admin_user: User, rom: Rom
    ):
        save = self._add(admin_user, rom, "unhashed", "autosave", None)

        db_save_handler.delete_save(save.id, content_hash="from_file")

        assert self._lost(admin_user, rom) == {"autosave": ["from_file"]}

    def test_a_save_outside_any_slot_is_not_recorded(self, admin_user: User, rom: Rom):
        save = self._add(admin_user, rom, "archival", None, "archived")

        db_save_handler.delete_save(save.id)

        assert self._lost(admin_user, rom) == {}

    def test_pruned_versions_are_recorded(self, admin_user: User, rom: Rom):
        for index in range(3):
            save = self._add(admin_user, rom, f"v{index}", "autosave", f"v{index}")
            db_save_handler.update_save(
                save.id, {"updated_at": datetime(2026, 1, 1 + index, tzinfo=UTC)}
            )

        db_save_handler.prune_slot(
            user_id=admin_user.id, rom_id=rom.id, slot="autosave", keep=1
        )

        assert self._lost(admin_user, rom) == {"autosave": ["v0", "v1"]}

    def test_only_unhashed_versions_a_prune_drops_are_listed(
        self, admin_user: User, rom: Rom
    ):
        for index, content_hash in enumerate([None, "hashed", None]):
            save = self._add(admin_user, rom, f"v{index}", "autosave", content_hash)
            db_save_handler.update_save(
                save.id, {"updated_at": datetime(2026, 1, 1 + index, tzinfo=UTC)}
            )

        unhashed = db_save_handler.get_unhashed_versions_past(
            admin_user.id, rom.id, "autosave", keep=1
        )

        assert [row.file_name for row in unhashed] == ["v0.sav"]

    def test_a_version_overwritten_since_it_was_read_is_recorded(
        self, admin_user: User, rom: Rom
    ):
        """Two overwrites racing: the second replaces what the first wrote."""
        save = self._add(admin_user, rom, "raced", "autosave", "v0")
        stale = db_save_handler._slot_version(save.id)
        db_save_handler.update_save(save.id, {"content_hash": "v1"})

        with mock.patch.object(db_save_handler, "_slot_version", return_value=stale):
            db_save_handler.update_save(save.id, {"content_hash": "v2"})

        assert self._lost(admin_user, rom) == {"autosave": ["v0", "v1"]}

    def test_a_version_moved_since_it_was_read_is_retried_in_its_new_slot(
        self, admin_user: User, rom: Rom
    ):
        save = self._add(admin_user, rom, "moved", "autosave", "v0")
        moved_from = SimpleNamespace(
            user_id=admin_user.id, rom_id=rom.id, slot="manual", content_hash="v0"
        )
        pre_reads = iter([moved_from])
        read_current = db_save_handler._slot_version

        with mock.patch.object(
            db_save_handler,
            "_slot_version",
            side_effect=lambda id: next(pre_reads, None) or read_current(id),
        ) as pre_read:
            db_save_handler.update_save(save.id, {"content_hash": "v1"})

        assert pre_read.call_count == 2
        assert db_save_handler.get_save(admin_user.id, save.id).content_hash == "v1"
        assert self._lost(admin_user, rom)["autosave"] == ["v0"]

    def test_a_version_that_keeps_moving_gives_up(self, admin_user: User, rom: Rom):
        save = self._add(admin_user, rom, "moving", "autosave", "v0")
        moved_from = SimpleNamespace(
            user_id=admin_user.id, rom_id=rom.id, slot="manual", content_hash="v0"
        )

        with (
            mock.patch.object(
                db_save_handler, "_slot_version", return_value=moved_from
            ),
            pytest.raises(saves_handler_module._SlotMoved),
        ):
            db_save_handler.delete_save(save.id)

        assert db_save_handler.get_save(admin_user.id, save.id).content_hash == "v0"

    def test_a_prune_that_fails_records_nothing(self, admin_user: User, rom: Rom):
        """The record commits with the removal, so no negotiation sees one alone."""
        self._add(admin_user, rom, "kept", "autosave", "kept")

        # Raised before a cursor exists: failing inside one leaves the MariaDB
        # driver's pooled connection unusable, and the next checkout crashes.
        def fail_the_delete(_conn: Any, statement: Any, *_: Any) -> None:
            if isinstance(statement, Delete) and statement.table.description == "saves":
                raise RuntimeError("delete failed")

        event.listen(sync_engine, "before_execute", fail_the_delete)
        try:
            with pytest.raises(RuntimeError):
                db_save_handler.prune_slot(
                    user_id=admin_user.id, rom_id=rom.id, slot="autosave", keep=0
                )
        finally:
            event.remove(sync_engine, "before_execute", fail_the_delete)

        assert self._lost(admin_user, rom) == {"autosave": []}
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])

    def test_a_loss_the_first_read_missed_is_still_recorded(
        self, admin_user: User, rom: Rom
    ):
        save = self._add(admin_user, rom, "missed", "autosave", "old")
        looks_unchanged = SimpleNamespace(
            user_id=admin_user.id, rom_id=rom.id, slot="autosave", content_hash="new"
        )

        with mock.patch.object(
            db_save_handler, "_slot_version", return_value=looks_unchanged
        ):
            db_save_handler.update_save(save.id, {"content_hash": "new"})

        assert self._lost(admin_user, rom) == {"autosave": ["old"]}

    def test_concurrent_removals_record_every_lost_version(
        self, admin_user: User, rom: Rom
    ):
        """One lock order, the slot's record before its rows, so none deadlock."""
        # Five slots against four kinds of write, so every pair races on a slot.
        saves = [
            self._add(admin_user, rom, f"c{index}", f"slot{index % 5}", f"c{index}")
            for index in range(120)
        ]

        def remove(index: int) -> None:
            save = saves[index]
            try:
                if index % 4 == 0:
                    db_save_handler.delete_save(save.id)
                elif index % 4 == 1:
                    db_save_handler.update_save(save.id, {"content_hash": f"n{index}"})
                elif index % 4 == 2:
                    db_save_handler.prune_slot(
                        user_id=admin_user.id,
                        rom_id=rom.id,
                        slot=f"slot{index % 5}",
                        keep=3,
                    )
                else:
                    # Writes a row a prune may be deleting, without the slot's lock.
                    db_save_handler.update_save(
                        save.id, {"is_favorite": True}, touch=False
                    )
            except NoResultFound:
                pass  # A prune removed the row first.

        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(remove, range(120)))

        remaining = {
            save.content_hash
            for save in db_save_handler.get_saves(
                user_id=admin_user.id, rom_ids=[rom.id]
            )
        }
        lost = {h for hashes in self._lost(admin_user, rom).values() for h in hashes}
        assert {save.content_hash for save in saves} - remaining <= lost

    @pytest.mark.parametrize("path", ["delete", "prune", "overwrite"])
    def test_recording_never_checks_out_a_second_connection(
        self, admin_user: User, rom: Rom, path: str
    ):
        """A second checkout per removal would starve the pool under load."""
        save = self._add(admin_user, rom, "pooled", "autosave", "pooled")
        checked_out: dict[str, int] = {}
        deleted_assets = saves_handler_module._deleted_assets
        ensure, record = deleted_assets.ensure_record, deleted_assets.record_deletions

        def spy(name: str, wrapped: Callable[..., Any]) -> Callable[..., Any]:
            def call(*args: Any, **kwargs: Any) -> Any:
                checked_out[name] = sync_engine.pool.checkedout()  # type: ignore[attr-defined]
                return wrapped(*args, **kwargs)

            return call

        with (
            mock.patch.object(deleted_assets, "ensure_record", spy("ensure", ensure)),
            mock.patch.object(
                deleted_assets, "record_deletions", spy("record", record)
            ),
        ):
            if path == "delete":
                db_save_handler.delete_save(save.id)
            elif path == "prune":
                db_save_handler.prune_slot(
                    user_id=admin_user.id, rom_id=rom.id, slot="autosave", keep=0
                )
            else:
                db_save_handler.update_save(save.id, {"content_hash": "new"})

        # Ensuring runs before the removal holds one; recording joins it.
        assert checked_out == {"ensure": 0, "record": 1}

    def test_an_overwritten_version_is_recorded(self, admin_user: User, rom: Rom):
        save = self._add(admin_user, rom, "overwritten", "autosave", "before")

        db_save_handler.update_save(save.id, {"content_hash": "after"})

        assert self._lost(admin_user, rom) == {"autosave": ["before"]}

    def test_a_version_moved_to_another_slot_is_recorded_in_the_first(
        self, admin_user: User, rom: Rom
    ):
        save = self._add(admin_user, rom, "moved", "autosave", "moved")

        db_save_handler.update_save(save.id, {"slot": "main_quest"})

        assert self._lost(admin_user, rom) == {"autosave": ["moved"]}

    def test_a_recomputed_hash_of_the_same_bytes_records_nothing(
        self, admin_user: User, rom: Rom
    ):
        save = self._add(admin_user, rom, "rehashed", "autosave", "raw_md5")

        assert db_save_handler.rehash_save(save.id, "entries_md5", replacing="raw_md5")
        assert self._lost(admin_user, rom) == {}

    def test_a_recomputed_hash_never_replaces_a_newer_one(
        self, admin_user: User, rom: Rom
    ):
        save = self._add(admin_user, rom, "rewritten", "autosave", "newer")

        assert not db_save_handler.rehash_save(
            save.id, "entries_md5", replacing="read_before"
        )
        [kept] = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        assert kept.content_hash == "newer"

    @pytest.mark.parametrize(
        "data",
        [{"content_hash": "same"}, {"is_favorite": True}],
        ids=["same-bytes", "annotation"],
    )
    def test_an_update_that_keeps_the_version_records_nothing(
        self, admin_user: User, rom: Rom, data: dict
    ):
        save = self._add(admin_user, rom, "kept", "autosave", "same")

        db_save_handler.update_save(save.id, data)

        assert not any(self._lost(admin_user, rom).values())


BACKEND_ROOT = Path(__file__).parents[3]
SAVES_HANDLER = BACKEND_ROOT / "handler" / "database" / "saves_handler.py"


def _writes_save_rows(node: ast.Call) -> bool:
    """Whether `node` is `delete(Save)`, `update(Save)` or `.query(Save)...delete()`."""
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    if name not in {"delete", "update"}:
        return False
    if any(isinstance(arg, ast.Name) and arg.id == "Save" for arg in node.args):
        return True
    return isinstance(func, ast.Attribute) and "query(Save)" in ast.unparse(func.value)


def test_only_the_saves_handler_writes_save_rows():
    """The handler records every version leaving a slot, so nothing may go around it."""
    offenders = []
    for path in BACKEND_ROOT.rglob("*.py"):
        relative = path.relative_to(BACKEND_ROOT)
        if relative.parts[0] in {"tests", "alembic"} or path == SAVES_HANDLER:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        offenders += [
            f"{relative}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _writes_save_rows(node)
        ]

    assert offenders == []
