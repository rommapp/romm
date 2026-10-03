"""Checks for the `roms_facets` mirror that backs the filter dropdowns.

The table holds a copy of each ROM's filter values (migration 0100) and is
maintained by database triggers on `roms`, not by application code, so these
tests write through the normal handlers and assert the mirror follows.
"""

import gc

from sqlalchemy import String, select
from sqlalchemy.engine import CursorResult, ExecutionContext
from tests.factories import make_rom

from handler.database import db_rom_handler, roms_handler
from handler.database.base_handler import sync_session
from models.platform import Platform
from models.rom import (
    METADATA_SOURCE_COLUMNS,
    METADATA_SOURCE_FACET_COLUMNS,
    Rom,
    RomFacets,
)


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

    def test_every_provider_id_is_mirrored(self, rom: Rom):
        """Guards the trigger column list: a provider missed there mirrors null."""
        # A string id for the providers whose column is a slug, else an int.
        values = {
            slug: f"{slug}-1" if isinstance(column.type, String) else index + 1
            for index, (slug, column) in enumerate(METADATA_SOURCE_COLUMNS.items())
        }
        db_rom_handler.update_rom(
            rom.id,
            {
                column.key: values[slug]
                for slug, column in METADATA_SOURCE_COLUMNS.items()
            },
        )

        facets = _facets(rom.id)
        assert facets is not None
        assert {
            slug: getattr(facets, column.key)
            for slug, column in METADATA_SOURCE_FACET_COLUMNS.items()
        } == values

    def test_publishers_developers_mirror(self, rom: Rom):
        db_rom_handler.update_rom(
            rom.id,
            {
                "ss_metadata": {
                    "companies": ["Atari", "Artech Studios"],
                    "publishers": ["Atari"],
                    "developers": ["Artech Studios"],
                }
            },
        )

        facets = _facets(rom.id)
        assert facets is not None
        assert facets.publishers == ["Atari"]
        assert facets.developers == ["Artech Studios"]

        filters = db_rom_handler.get_rom_filters()
        assert "Atari" in filters["publishers"]
        assert "Artech Studios" in filters["developers"]

    def test_steam_only_metadata_mirrors(self, rom: Rom):
        # Steam feeds the same generated columns as every other provider, so a
        # game matched only there is filterable and indexable like any other.
        db_rom_handler.update_rom(
            rom.id,
            {
                "steam_metadata": {
                    "genres": ["Action", "Indie"],
                    "companies": ["Team Cherry"],
                    "developers": ["Team Cherry"],
                    "publishers": ["Team Cherry"],
                    "game_modes": ["Single player"],
                }
            },
        )

        facets = _facets(rom.id)
        assert facets is not None
        assert facets.genres == ["Action", "Indie"]
        assert facets.companies == ["Team Cherry"]
        assert facets.developers == ["Team Cherry"]
        assert facets.publishers == ["Team Cherry"]
        assert facets.game_modes == ["Single player"]

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

    def test_filter_values_merge_repeated_lists(
        self, rom: Rom, second_rom: Rom, platform: Platform, monkeypatch
    ):
        # Three copies of one list can't share a batch of two, so a repeat is
        # always skipped in a later batch, whatever order the rows come back in.
        monkeypatch.setattr(roms_handler, "_FILTER_VALUES_BATCH_SIZE", 2)
        third = make_rom(platform, "test_rom_3", slug="test_rom_slug_3")
        for rom_id in (rom.id, second_rom.id, third.id):
            db_rom_handler.update_rom(
                rom_id, {"igdb_metadata": {"genres": ["RPG", "Action"]}}
            )
        fourth = make_rom(platform, "test_rom_4", slug="test_rom_slug_4")
        db_rom_handler.update_rom(
            fourth.id, {"igdb_metadata": {"genres": ["Puzzle", "RPG"]}}
        )
        make_rom(platform, "test_rom_5", slug="test_rom_slug_5")

        filters = db_rom_handler.get_rom_filters()
        assert filters["genres"] == ["Action", "Puzzle", "RPG"]
        assert filters["platforms"] == [platform.id]

    def test_filter_values_survive_a_scalar_where_a_list_belongs(
        self, rom: Rom, second_rom: Rom
    ):
        db_rom_handler.update_rom(rom.id, {"manual_metadata": {"genres": "RPG"}})
        db_rom_handler.update_rom(
            second_rom.id, {"igdb_metadata": {"genres": ["Action"]}}
        )

        assert "Action" in db_rom_handler.get_rom_filters()["genres"]

    def test_filter_values_free_the_cursor_without_the_gc(self, rom: Rom):
        # A cursor left for the cyclic GC is finalized on whichever thread
        # collects next, which segfaults the mariadb connector under load.
        db_rom_handler.update_rom(rom.id, {"igdb_metadata": {"genres": ["Puzzle"]}})
        was_enabled, debug_flags = gc.isenabled(), gc.get_debug()
        gc.collect()
        gc.disable()
        gc.set_debug(gc.DEBUG_SAVEALL)
        garbage_start = len(gc.garbage)
        try:
            db_rom_handler.get_rom_filters()
            gc.collect()
            # The execution context owns the DBAPI cursor, so check it as well.
            leaked = [
                o
                for o in gc.garbage[garbage_start:]
                if isinstance(o, (CursorResult, ExecutionContext))
            ]
        finally:
            gc.set_debug(debug_flags)
            del gc.garbage[garbage_start:]
            if was_enabled:
                gc.enable()

        assert leaked == []
