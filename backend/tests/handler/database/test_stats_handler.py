"""Checks for the Server Stats per-platform breakdowns.

Both breakdowns aggregate from the narrow `roms_facets` mirror (migration 0100,
extended with the provider match ids) rather than scanning the multi-gigabyte
`roms` table. The mirror is trigger-maintained, so these tests write ROMs
through the normal handler and assert the breakdowns read the mirrored values.
"""

from handler.database import db_platform_handler, db_rom_handler, db_stats_handler
from models.platform import Platform
from models.rom import Rom


def _add_platform(slug: str) -> Platform:
    return db_platform_handler.add_platform(
        Platform(name=slug, slug=slug, fs_slug=slug)
    )


def _add_rom(platform: Platform, fs_name: str, **columns) -> Rom:
    """Insert a ROM on `platform`, letting the facet triggers mirror it."""
    rom = Rom(
        platform_id=platform.id,
        name=fs_name,
        slug=fs_name,
        fs_name=f"{fs_name}.zip",
        fs_name_no_tags=fs_name,
        fs_name_no_ext=fs_name,
        fs_extension="zip",
        fs_path=f"{platform.slug}/roms",
        **columns,
    )
    return db_rom_handler.add_rom(rom)


class TestRegionBreakdown:
    def test_counts_regions_per_platform(self):
        platform_a = _add_platform("platform_a")
        platform_b = _add_platform("platform_b")
        _add_rom(platform_a, "a1", regions=["USA", "Japan"])
        _add_rom(platform_a, "a2", regions=["USA"])
        _add_rom(platform_b, "b1", regions=["Europe"])

        breakdown = db_stats_handler.get_region_breakdown_by_platform()

        assert breakdown[platform_a.id] == [
            {"region": "USA", "count": 2},
            {"region": "Japan", "count": 1},
        ]
        assert breakdown[platform_b.id] == [{"region": "Europe", "count": 1}]

    def test_empty_regions_are_omitted(self):
        platform = _add_platform("platform_empty")
        _add_rom(platform, "no_region", regions=[])

        breakdown = db_stats_handler.get_region_breakdown_by_platform()

        assert platform.id not in breakdown

    def test_hidden_platforms_are_excluded(self):
        platform_a = _add_platform("platform_a")
        platform_b = _add_platform("platform_b")
        _add_rom(platform_a, "a1", regions=["USA"])
        _add_rom(platform_b, "b1", regions=["Europe"])

        breakdown = db_stats_handler.get_region_breakdown_by_platform(
            hidden_platform_ids=[platform_b.id]
        )

        assert platform_a.id in breakdown
        assert platform_b.id not in breakdown

    def test_hidden_roms_are_excluded(self):
        platform = _add_platform("platform_a")
        _add_rom(platform, "a1", regions=["USA"])
        hidden = _add_rom(platform, "a2", regions=["USA"])

        breakdown = db_stats_handler.get_region_breakdown_by_platform(
            hidden_rom_ids=[hidden.id]
        )

        assert breakdown[platform.id] == [{"region": "USA", "count": 1}]


class TestMetadataCoverage:
    def test_counts_matched_sources_per_platform(self):
        platform_a = _add_platform("platform_a")
        platform_b = _add_platform("platform_b")
        _add_rom(platform_a, "a1", igdb_id=1, ss_id=2)
        _add_rom(platform_a, "a2", igdb_id=3)
        _add_rom(platform_b, "b1", moby_id=5)

        coverage = db_stats_handler.get_metadata_coverage_by_platform()

        assert {"source": "igdb", "matched": 2} in coverage[platform_a.id]
        assert {"source": "ss", "matched": 1} in coverage[platform_a.id]
        assert coverage[platform_b.id] == [{"source": "moby", "matched": 1}]

    def test_string_id_sources_are_counted(self):
        """flashpoint/gamelist/libretro ids are strings, not integers."""
        platform = _add_platform("platform_a")
        _add_rom(platform, "a1", flashpoint_id="abc", libretro_id="snes")

        coverage = db_stats_handler.get_metadata_coverage_by_platform()

        assert {"source": "flashpoint", "matched": 1} in coverage[platform.id]
        assert {"source": "libretro", "matched": 1} in coverage[platform.id]

    def test_unmatched_sources_are_omitted(self):
        platform = _add_platform("platform_a")
        _add_rom(platform, "a1", igdb_id=1)

        coverage = db_stats_handler.get_metadata_coverage_by_platform()

        sources = {item["source"] for item in coverage[platform.id]}
        assert sources == {"igdb"}

    def test_hidden_platforms_are_excluded(self):
        platform_a = _add_platform("platform_a")
        platform_b = _add_platform("platform_b")
        _add_rom(platform_a, "a1", igdb_id=1)
        _add_rom(platform_b, "b1", igdb_id=2)

        coverage = db_stats_handler.get_metadata_coverage_by_platform(
            hidden_platform_ids=[platform_b.id]
        )

        assert platform_a.id in coverage
        assert platform_b.id not in coverage

    def test_hidden_roms_are_excluded(self):
        platform = _add_platform("platform_a")
        _add_rom(platform, "a1", igdb_id=1)
        hidden = _add_rom(platform, "a2", igdb_id=2)

        coverage = db_stats_handler.get_metadata_coverage_by_platform(
            hidden_rom_ids=[hidden.id]
        )

        assert coverage[platform.id] == [{"source": "igdb", "matched": 1}]
