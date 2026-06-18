"""Unit tests for DBRomsHandler's derived-column bookkeeping.

Bulk `update()` bypasses the ORM `@validates` hooks, so `update_rom` keeps
the columns derived from `name` / `fs_name` in sync explicitly.
"""

from handler.database import db_rom_handler
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
