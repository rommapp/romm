from tests.factories import make_rom

from handler.scan.merge import keep_base_fields
from models.platform import Platform


def test_the_stored_placeholder_name_is_replaced(platform: Platform):
    # The stored placeholder differs from the title derived from the filename.
    rom = make_rom(
        platform,
        "celeste.p8",
        fs_stem="celeste.p8",
        fs_extension="png",
    )
    rom_attrs = {"fs_name": rom.fs_name, "name": "Celeste"}

    keep_base_fields(rom_attrs, rom)

    assert rom_attrs["name"] == "Celeste"


def test_a_name_the_user_set_is_kept(platform: Platform):
    rom = make_rom(platform, "My Celeste", fs_stem="celeste.p8", fs_extension="png")
    rom_attrs = {"fs_name": rom.fs_name, "name": "Celeste"}

    keep_base_fields(rom_attrs, rom)

    assert rom_attrs["name"] == "My Celeste"
