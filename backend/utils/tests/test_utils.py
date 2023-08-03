from utils import (
    parse_tags,
    get_file_name_with_no_tags as gfnwt,
    get_file_extension as gfe,
)


def test_parse_tags():
    file_name = "Super Mario Bros. (World).nes"
    assert parse_tags(file_name) == ("World", "", [])

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert parse_tags(file_name) == ("World", "A", [])

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert parse_tags(file_name) == ("USA", "A", ["Beta"])

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert parse_tags(file_name) == ("USA", "", ["Beta"])

    file_name = "Super Mario Bros. (CH) [!].nes"
    assert parse_tags(file_name) == ("China", "", [])

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert parse_tags(file_name) == ("Taiwan", "1.2", [])

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert parse_tags(file_name) == ("Spain", "A", [])


def test_get_file_name_with_no_tags():
    file_name = "Super Mario Bros. (World).nes"
    assert gfnwt(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert gfnwt(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert gfnwt(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert gfnwt(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (U) [!].nes"
    assert gfnwt(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert gfnwt(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert gfnwt(file_name) == "Super Mario Bros."


def test_get_file_extension():
    rom = {"file_name": "Super Mario Bros. (World).nes", "multi": False}
    assert gfe(rom) == "nes"

    rom = {"file_name": "Super Mario Bros. (World).nes", "multi": True}
    assert gfe(rom) == ""
