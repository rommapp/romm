from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.database import db_rom_handler
from handler.scan.sources import ScanType
from models.rom import Rom


def _with_key(rom: Rom, key: str, *, custom: bool) -> Rom:
    updated = db_rom_handler.update_rom(
        rom.id, {"name_sort_key": key, "name_sort_key_custom": custom}
    )
    return updated


async def test_a_rescan_rederives_a_key_that_is_not_custom():
    platform = add_n64_platform()
    rom = _with_key(
        add_rom(platform, "Die Hard Arcade.z64", "Die Hard Arcade"),
        "hard arcade",
        custom=False,
    )

    scanned = await run_scan(
        platform, rom, scan_type=ScanType.UPDATE, metadata_sources=[]
    )

    assert scanned.name_sort_key == "die hard arcade"
    assert not scanned.name_sort_key_custom


async def test_a_rescan_keeps_a_custom_key():
    platform = add_n64_platform()
    rom = _with_key(
        add_rom(platform, "Die Hard Arcade.z64", "Die Hard Arcade"),
        "hard arcade",
        custom=True,
    )

    scanned = await run_scan(
        platform, rom, scan_type=ScanType.UPDATE, metadata_sources=[]
    )

    assert scanned.name_sort_key == "hard arcade"
    assert scanned.name_sort_key_custom
