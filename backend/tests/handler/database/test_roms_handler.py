"""Unit tests for DBRomsHandler's derived-column bookkeeping.

Bulk `update()` bypasses the ORM `@validates` hooks, so `update_rom` keeps
the columns derived from `name` / `fs_name` in sync explicitly.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from handler.database import (
    db_platform_handler,
    db_rom_handler,
    db_save_handler,
    db_state_handler,
)
from models.assets import Save, State
from models.platform import Platform
from models.rom import Rom
from models.user import User


class TestUpdateRomDerivedColumns:
    def test_update_name_resyncs_name_sort_key(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"name": "The New Name 2"})

        assert updated.name == "The New Name 2"
        assert updated.name_sort_key == "new name 000000000002"

    def test_update_fs_name_resyncs_all_parts(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"fs_name": "Sonic (Europe).md"})

        assert updated.fs_name == "Sonic (Europe).md"
        assert updated.fs_name_no_tags == "Sonic"
        assert updated.fs_name_no_ext == "Sonic (Europe)"
        # The extension is resynced too — the rename endpoint used to omit it.
        assert updated.fs_extension == "md"

    def test_update_unrelated_field_leaves_derived_columns(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"summary": "just a summary"})

        assert updated.summary == "just a summary"
        assert updated.fs_name_no_tags == "test_rom"
        assert updated.fs_extension == "zip"
        assert updated.name_sort_key == "test_rom"

    def test_explicit_name_sort_key_marks_custom(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"name_sort_key": "zelda"})

        assert updated.name_sort_key == "zelda"

    def test_update_name_keeps_custom_sort_key(self, rom: Rom):
        db_rom_handler.update_rom(rom.id, {"name_sort_key": "pinned"})
        updated = db_rom_handler.update_rom(rom.id, {"name": "The New Name 2"})

        # A pinned custom key is never clobbered by a name change.
        assert updated.name == "The New Name 2"
        assert updated.name_sort_key == "pinned"


def _make_rom(platform: Platform, fs_name: str) -> Rom:
    return Rom(
        platform_id=platform.id,
        fs_name=fs_name,
        fs_path=f"{platform.slug}/roms",
        name=fs_name,
        url_cover="",
        url_manual="",
        url_screenshots=[],
    )


class TestUniquePlatformFsName:
    """A platform folder can't hold two entries with the same name, so the DB
    rejects a second ROM with the same (platform_id, fs_name). This is what
    stops racing scans (e.g. after the patcher uploads a patched ROM) from
    creating duplicate library entries."""

    def test_duplicate_platform_fs_name_rejected(self, platform: Platform):
        db_rom_handler.add_rom(_make_rom(platform, "Patched Game.gba"))

        with pytest.raises(IntegrityError):
            db_rom_handler.add_rom(_make_rom(platform, "Patched Game.gba"))

    def test_same_fs_name_other_platform_allowed(self, platform: Platform):
        other = db_platform_handler.add_platform(
            Platform(name="other", slug="other_slug", fs_slug="other_slug")
        )

        first = db_rom_handler.add_rom(_make_rom(platform, "Patched Game.gba"))
        second = db_rom_handler.add_rom(_make_rom(other, "Patched Game.gba"))

        assert first.id != second.id


class TestHasSavesStatesFilter:
    """The has-saves / has-states filters match a user's own assets plus other
    users' public (community) ones, mirroring the shared-assets visibility."""

    def _add_save(self, rom: Rom, user_id: int, *, is_public: bool) -> Save:
        return db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=user_id,
                file_name="filter.sav",
                file_path=f"{rom.fs_path}/saves",
                file_size_bytes=1,
                is_public=is_public,
            )
        )

    def _add_state(self, rom: Rom, user_id: int, *, is_public: bool) -> State:
        return db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=user_id,
                file_name="filter.state",
                file_path=f"{rom.fs_path}/states",
                file_size_bytes=1,
                is_public=is_public,
            )
        )

    def _rom_ids(self, **kwargs) -> set[int]:
        return {r.id for r in db_rom_handler.get_roms_scalar(**kwargs)}

    # ---- saves ----

    def test_own_save_matches(self, rom: Rom, admin_user: User):
        self._add_save(rom, admin_user.id, is_public=False)
        assert rom.id in self._rom_ids(user_id=admin_user.id, has_saves=True)

    def test_other_users_private_save_does_not_match(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_save(rom, editor_user.id, is_public=False)
        assert rom.id not in self._rom_ids(user_id=admin_user.id, has_saves=True)

    def test_other_users_public_save_matches(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_save(rom, editor_user.id, is_public=True)
        assert rom.id in self._rom_ids(user_id=admin_user.id, has_saves=True)

    def test_has_saves_false_excludes_public(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_save(rom, editor_user.id, is_public=True)
        assert rom.id not in self._rom_ids(user_id=admin_user.id, has_saves=False)

    # ---- states ----

    def test_other_users_public_state_matches(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_state(rom, editor_user.id, is_public=True)
        assert rom.id in self._rom_ids(user_id=admin_user.id, has_states=True)

    def test_other_users_private_state_does_not_match(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_state(rom, editor_user.id, is_public=False)
        assert rom.id not in self._rom_ids(user_id=admin_user.id, has_states=True)
