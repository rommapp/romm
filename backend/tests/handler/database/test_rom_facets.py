"""Checks for the `roms_facets` mirror that backs the filter dropdowns.

The table holds a copy of each ROM's filter values (migration 0100) and is
maintained by database triggers on `roms`, not by application code, so these
tests write through the normal handlers and assert the mirror follows.
"""

from sqlalchemy import select

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.rom import Rom, RomFacets


def _facets(rom_id: int) -> RomFacets | None:
    with sync_session.begin() as session:
        return session.scalar(select(RomFacets).where(RomFacets.rom_id == rom_id))


class TestRomFacets:
    def test_insert_mirrors_the_rom(self, rom: Rom):
        facets = _facets(rom.id)
        assert facets is not None
        assert facets.platform_id == rom.platform_id

    def test_update_mirrors_derived_and_raw_values(self, rom: Rom):
        db_rom_handler.update_rom(
            rom.id,
            {
                "igdb_metadata": {"genres": ["Action", "RPG"], "franchises": ["Zelda"]},
                "regions": ["USA"],
                "tags": ["Proto"],
            },
        )

        facets = _facets(rom.id)
        assert facets is not None
        assert facets.genres == ["Action", "RPG"]
        assert facets.franchises == ["Zelda"]
        assert facets.regions == ["USA"]
        assert facets.tags == ["Proto"]

    def test_provider_ids_mirror_the_rom(self, rom: Rom):
        # Backs the Server Stats metadata-coverage breakdown, which counts these
        # off the mirror instead of scanning `roms`.
        db_rom_handler.update_rom(
            rom.id,
            {"igdb_id": 1234, "moby_id": 56, "flashpoint_id": "fp-1"},
        )

        facets = _facets(rom.id)
        assert facets is not None
        assert facets.igdb_id == 1234
        assert facets.moby_id == 56
        assert facets.flashpoint_id == "fp-1"
        # Sources the ROM didn't match stay null.
        assert facets.ss_id is None

    def test_delete_cascades(self, rom: Rom):
        rom_id = rom.id
        db_rom_handler.delete_rom(rom_id)

        assert _facets(rom_id) is None

    def test_filter_values_follow_a_metadata_edit(self, rom: Rom):
        db_rom_handler.update_rom(
            rom.id, {"igdb_metadata": {"genres": ["Puzzle"]}, "languages": ["En"]}
        )

        filters = db_rom_handler.get_rom_filters()
        assert "Puzzle" in filters["genres"]
        assert "En" in filters["languages"]
