"""Unit tests for DBRomsHandler's derived-column bookkeeping.

Bulk `update()` bypasses the ORM `@validates` hooks, so `update_rom` keeps
the columns derived from `name` / `fs_name` in sync explicitly.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom


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
