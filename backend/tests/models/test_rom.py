from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom


def test_rom(rom: Rom):
    assert rom.fs_path == "test_platform_slug/roms"
    assert rom.full_path == "test_platform_slug/roms/test_rom.zip"


def test_rom_defaults_to_non_physical(rom: Rom):
    assert rom.is_physical is False
    assert rom.upc is None


def test_physical_rom_round_trips(platform: Platform):
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Sonic the Hedgehog",
            fs_name="Sonic the Hedgehog",
            fs_path=f"{platform.slug}/roms/.physical",
            fs_size_bytes=0,
            is_physical=True,
            upc="012345678905",
        )
    )

    stored = db_rom_handler.get_rom(rom.id)
    assert stored is not None
    assert stored.is_physical is True
    assert stored.upc == "012345678905"


def test_rom_with_libretro_match_is_identified(rom: Rom):
    rom.libretro_id = "abc123"

    assert rom.is_unidentified is False
    assert rom.is_identified is True
