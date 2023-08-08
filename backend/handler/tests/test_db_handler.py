from handler.db_handler import DBHandler
from models.platform import Platform
from models.rom import Rom

dbh = DBHandler()


def test_platforms():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform"
    )
    dbh.add_platform(platform)

    platforms = dbh.get_platforms()
    assert len(platforms) == 1 # type: ignore

    platform = dbh.get_platform("test_platform_slug")
    assert platform.name == "test_platform" # type: ignore

    dbh.purge_platforms(["test_platform_slug"])
    platforms = dbh.get_platforms()
    assert len(platforms) == 0 # type: ignore


def test_roms(rom):
    dbh.add_rom(
        Rom(
            r_name="test_rom_2",
            r_slug="test_rom_slug_2",
            p_name="test_platform",
            p_slug="test_platform_slug",
            file_name="test_rom_2",
            file_name_no_tags="test_rom_2",
        )
    )

    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms("test_platform_slug")).all() # type: ignore
        assert len(roms) == 2

    rom = dbh.get_rom(roms[0].id)
    assert rom.file_name == "test_rom" # type: ignore

    dbh.update_rom(roms[1].id, {"file_name": "test_rom_2_updated"})
    rom_2 = dbh.get_rom(roms[1].id)
    assert rom_2.file_name == "test_rom_2_updated" # type: ignore

    dbh.delete_rom(rom.id)  # type: ignore

    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms(rom.p_slug)).all() # type: ignore
        assert len(roms) == 1

    dbh.purge_roms(rom_2.p_slug, [rom_2.r_slug]) # type: ignore

    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms("test_platform_slug")).all() # type: ignore
        assert len(roms) == 0


def test_utils(rom):
    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms("test_platform_slug")).all() # type: ignore
        assert dbh.rom_exists("test_platform_slug", "test_rom") == roms[0].id
