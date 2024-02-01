from handler import fs_rom_handler


def test_parse_tags():
    file_name = "Super Mario Bros. (World).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["World"], "", [], [])

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["World"], "A", [], [])

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["USA"], "A", [], ["Beta"])

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["USA"], "", [], ["Beta"])

    file_name = "Super Mario Bros. (CH) [!].nes"
    assert fs_rom_handler.parse_tags(file_name) == (["China"], "", [], ["!"])

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["Taiwan"], "1.2", [], [])

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["Spain"], "A", [], [])

    file_name = "Super Metroid (Japan, USA) (En,Ja).zip"
    assert fs_rom_handler.parse_tags(file_name) == (["Japan", "USA"], "", ["English", "Japanese"], [])


def test_get_file_name_with_no_tags():
    file_name = "Super Mario Bros. (World).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (U) [!].nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "007 - Agent Under Fire.nkit.iso"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "007 - Agent Under Fire"

    file_name = "Jimmy Houston's Bass Tournament U.S.A..zip"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Jimmy Houston's Bass Tournament U.S.A."

    # This is expected behavior, since the regex is aggressive
    file_name = "Battle Stadium D.O.N.zip"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Battle Stadium D.O.N"


def test_get_file_name_with_no_extension():
    file_name = "Super Mario Bros. (World).nes"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Super Mario Bros. (World)"

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Super Mario Bros. (W) (Rev A)"

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Super Mario Bros. (USA) (Rev A) (Beta)"

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Super Mario Bros. (U) (Beta)"

    file_name = "Super Mario Bros. (U) [!].nes"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Super Mario Bros. (U) [!]"

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Super Mario Bros. (reg-T) (rev-1.2)"

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Super Mario Bros. (Reg S) (Rev A)"

    file_name = "007 - Agent Under Fire.nkit.iso"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "007 - Agent Under Fire"

    file_name = "Jimmy Houston's Bass Tournament U.S.A..zip"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Jimmy Houston's Bass Tournament U.S.A."

    file_name = "Battle Stadium D.O.N.zip"
    assert fs_rom_handler.get_file_name_with_no_extension(file_name) == "Battle Stadium D.O.N"

def test_get_file_extension():
    assert fs_rom_handler.parse_file_extension("Super Mario Bros. (World).nes") == "nes"
    assert fs_rom_handler.parse_file_extension("007 - Agent Under Fire.nkit.iso") == "nkit.iso"
