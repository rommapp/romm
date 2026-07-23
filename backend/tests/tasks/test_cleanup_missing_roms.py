from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom
from tasks.manual.cleanup_missing_roms import cleanup_missing_roms_task


def _add_rom(platform: Platform, fs_name: str, **extra) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=fs_name,
            fs_name=fs_name,
            fs_name_no_tags=fs_name,
            fs_name_no_ext=fs_name,
            fs_extension="",
            fs_path=f"{platform.slug}/roms",
            **extra,
        )
    )


async def test_cleanup_deletes_missing_roms_but_never_virtual_ones(
    platform: Platform,
):
    missing_rom = _add_rom(platform, "missing_rom", missing_from_fs=True)
    virtual_rom = _add_rom(
        platform, "virtual_rom", missing_from_fs=True, is_virtual=True
    )
    present_rom = _add_rom(platform, "present_rom")

    stats = await cleanup_missing_roms_task.run(platform_id=platform.id)

    assert stats["roms_deleted"] == 1
    assert db_rom_handler.get_rom(missing_rom.id) is None
    assert db_rom_handler.get_rom(virtual_rom.id) is not None
    assert db_rom_handler.get_rom(present_rom.id) is not None
