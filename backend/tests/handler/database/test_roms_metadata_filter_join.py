"""Filtering on a `roms_metadata` field while grouping ROMs by title.

The dedup window that grouping materializes is derived from the query the
metadata filters were already applied to, so the join to `roms_metadata` has to
be in place before them. Without it the window filters on a table it never
joined: the database cross-joins `roms` against `roms_metadata` (a view over
`roms`), the window ranks the whole library instead of the matching ROMs, and
the version of a game that did match the filter drops out of the gallery.
"""

import warnings

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import SAWarning
from sqlalchemy.sql.compiler import FROM_LINTING

from handler.database import db_rom_handler
from handler.database.rom_filters import ROM_FILTER_SPECS, RomFilterParams
from models.platform import Platform
from models.rom import Rom

# Derived from the registry, so registering a filter that reads `roms_metadata`
# extends this coverage instead of silently going untested.
METADATA_FILTERS = [
    {spec.name: ["any-value"]} for spec in ROM_FILTER_SPECS if spec.needs_metadata_join
]


def _make_rom(platform: Platform, fs_name: str, **fields) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=fs_name,
            slug=fs_name,
            fs_name=f"{fs_name}.zip",
            fs_name_no_tags=fs_name,
            fs_name_no_ext=fs_name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    return db_rom_handler.update_rom(rom.id, fields)


def _cartesian_warnings(statement) -> list[str]:
    """Every cartesian-product lint the statement compiles with."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        statement.compile(dialect=mysql.dialect(), linting=FROM_LINTING)
    return [
        str(warning.message)
        for warning in caught
        if issubclass(warning.category, SAWarning)
        and "cartesian product" in str(warning.message)
    ]


class TestGroupedMetadataFilterJoin:
    @pytest.mark.parametrize("filters", METADATA_FILTERS, ids=lambda f: next(iter(f)))
    def test_grouped_query_joins_what_it_filters_on(self, filters: dict):
        query, _ = db_rom_handler.get_roms_query()
        grouped = db_rom_handler.filter_roms(
            query=query,
            filters=RomFilterParams(group_by_meta_id=True, **filters),
        )

        assert not _cartesian_warnings(grouped)

    def test_group_keeps_the_version_that_matches_the_filter(self, platform: Platform):
        # `fs_name_no_ext` breaks ties in the window, so the version that misses
        # the filter is the one the window would rank first.
        _make_rom(
            platform,
            "a_version",
            igdb_id=1234,
            igdb_metadata={"genres": ["Action"]},
        )
        _make_rom(
            platform,
            "b_version",
            igdb_id=1234,
            igdb_metadata={"genres": ["Shooter"]},
        )

        roms = db_rom_handler.get_roms_scalar(genres=["Shooter"], group_by_meta_id=True)

        assert [rom.name for rom in roms] == ["b_version"]
