"""Tests for the materialized `roms_metadata` and `virtual_collections` tables.

Both used to be SQL views re-derived on every query; they are now real tables
maintained at write time (issue #3768). These tests cover that the per-rom
facet row is populated on add/update, removed on delete (FK cascade), and that
the virtual_collections rebuild reproduces the old aggregation.
"""

from tests.conftest import session as session_factory

from handler.database import db_collection_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomMetadata


def _add_rom(platform: Platform, slug: str, **attrs) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=slug,
            slug=slug,
            fs_name=f"{slug}.zip",
            fs_name_no_tags=slug,
            fs_name_no_ext=slug,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            **attrs,
        )
    )


def _metadata(rom_id: int) -> RomMetadata | None:
    with session_factory.begin() as s:
        return s.get(RomMetadata, rom_id)


def test_add_rom_populates_materialized_metadata(platform: Platform):
    rom = _add_rom(
        platform,
        "materialized_rom",
        igdb_metadata={"genres": ["RPG"], "franchises": ["Zelda"]},
        regions=["USA"],
        tags=["Proto"],
    )

    md = _metadata(rom.id)
    assert md is not None
    assert md.genres == ["RPG"]
    assert md.franchises == ["Zelda"]
    # Denormalized rom columns are copied so facet queries never read `roms`.
    assert md.regions == ["USA"]
    assert md.tags == ["Proto"]
    assert md.platform_id == platform.id


def test_add_rom_eager_metadatum_is_present(platform: Platform):
    rom = _add_rom(platform, "eager_rom", igdb_metadata={"genres": ["Action"]})
    # `Rom.metadatum` is eager-joined; it must resolve right after add_rom.
    assert rom.metadatum is not None
    assert rom.metadatum.genres == ["Action"]


def test_update_rom_refreshes_materialized_metadata(platform: Platform):
    rom = _add_rom(platform, "update_rom", igdb_metadata={"genres": ["RPG"]})
    before = _metadata(rom.id)
    assert before is not None
    assert before.genres == ["RPG"]

    db_rom_handler.update_rom(rom.id, {"igdb_metadata": {"genres": ["Puzzle"]}})

    after = _metadata(rom.id)
    assert after is not None
    assert after.genres == ["Puzzle"]


def test_delete_rom_cascades_materialized_metadata(platform: Platform):
    rom = _add_rom(platform, "delete_rom", igdb_metadata={"genres": ["RPG"]})
    assert _metadata(rom.id) is not None

    db_rom_handler.delete_rom(rom.id)

    assert _metadata(rom.id) is None


def test_rebuild_virtual_collections_reproduces_aggregation(platform: Platform):
    # Three roms sharing a genre cross the ">2" membership threshold.
    for index in range(3):
        _add_rom(platform, f"vc_rom_{index}", igdb_metadata={"genres": ["Shooter"]})
    # Two roms sharing another genre stay below the threshold.
    for index in range(2):
        _add_rom(platform, f"vc_sparse_{index}", igdb_metadata={"genres": ["Sparse"]})

    db_collection_handler.rebuild_virtual_collections()

    collections = db_collection_handler.get_virtual_collections(type="genre")
    names = {c.name for c in collections}
    assert "Shooter" in names
    assert "Sparse" not in names

    shooter = next(c for c in collections if c.name == "Shooter")
    assert len(shooter.rom_ids) == 3
