"""End-to-end checks for the roms_metadata derivations.

roms_metadata is a view over STORED generated columns on ``roms`` (migration
0098). These tests write raw provider-metadata blobs and assert the values the
engine derives and exposes through ``Rom.metadatum``, covering the facet
columns, the rating average, the gamelist date wrapper, and the quoted-string
date that the old view silently truncated to ``0``.
"""

from handler.database import db_rom_handler
from models.rom import Rom


def _reload(rom: Rom) -> Rom:
    reloaded = db_rom_handler.get_rom(rom.id)
    assert reloaded is not None
    return reloaded


class TestGeneratedMetadata:
    def test_igdb_derivations(self, rom: Rom):
        db_rom_handler.update_rom(
            rom.id,
            {
                "igdb_metadata": {
                    "genres": ["Action", "RPG"],
                    "franchises": ["Zelda"],
                    "game_modes": ["Single player"],
                    "total_rating": "80",
                    "first_release_date": "1569369600",
                    "age_ratings": [{"rating": "E"}, {"rating": "T"}],
                    "player_count": "4",
                },
            },
        )

        meta = _reload(rom).metadatum
        assert meta.genres == ["Action", "RPG"]
        assert meta.franchises == ["Zelda"]
        assert meta.game_modes == ["Single player"]
        assert meta.age_ratings == ["E", "T"]
        assert meta.player_count == "4"
        assert meta.average_rating == 80.0
        # Quoted-string epoch seconds -> ms. The old view truncated this to 0.
        assert meta.first_release_date == 1569369600000

    def test_rating_average_across_providers(self, rom: Rom):
        db_rom_handler.update_rom(
            rom.id,
            {
                "igdb_metadata": {"total_rating": "84"},
                "ss_metadata": {"ss_score": "8"},  # * 10 -> 80
            },
        )

        meta = _reload(rom).metadatum
        assert meta.average_rating == 82.0

    def test_precedence_falls_through_to_gamelist_date(self, rom: Rom):
        # No earlier provider supplies first_release_date, so the gamelist
        # branch (parsed through the immutable UTC wrapper) wins.
        db_rom_handler.update_rom(
            rom.id,
            {"gamelist_metadata": {"first_release_date": "20200101T000000"}},
        )

        meta = _reload(rom).metadatum
        assert meta.first_release_date == 1577836800000  # 2020-01-01T00:00:00Z

    def test_empty_metadata_yields_defaults(self, rom: Rom):
        meta = _reload(rom).metadatum
        assert meta.genres == []
        assert meta.franchises == []
        assert meta.age_ratings == []
        assert meta.player_count == "1"
        assert meta.first_release_date is None
        assert meta.average_rating is None
