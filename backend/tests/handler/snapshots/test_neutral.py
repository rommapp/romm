import pytest

from handler.snapshots.neutral import NeutralUnitRejected, check_neutral_unit
from models.assets import SaveShape


@pytest.mark.parametrize(
    "platform,shape,members",
    [
        ("gb", SaveShape.SINGLE, ["save.sram"]),
        ("gb", SaveShape.SINGLE, ["Pokemon Red.srm"]),
        ("gbc", SaveShape.SINGLE, ["Pokemon Crystal.srm"]),
        ("gbc", SaveShape.MULTI, ["save.sram", "clock.rtc"]),
        ("snes", SaveShape.SINGLE, ["save.sram"]),
        ("n64", SaveShape.MULTI, ["eeprom", "pak1"]),
        ("nds", SaveShape.SINGLE, ["save.raw"]),
        ("nds", SaveShape.SINGLE, ["Mario Kart DS.srm"]),
        ("saturn", SaveShape.MULTI, ["backup.ram", "cart.ram"]),
        ("dc", SaveShape.MULTI, ["vmu_A1.bin", "vmu_B2.bin"]),
        ("psx", SaveShape.SINGLE, ["anything.mcd"]),
        ("genesis", SaveShape.SINGLE, ["Sonic The Hedgehog 3 (USA).srm"]),
        ("genesis", SaveShape.SINGLE, ["save.sram"]),
        ("sega32", SaveShape.SINGLE, ["36 Great Holes (Europe).srm"]),
        ("sms", SaveShape.SINGLE, ["Phantasy Star (USA, Europe).srm"]),
        ("gamegear", SaveShape.SINGLE, ["Defenders of Oasis (USA, Europe).srm"]),
        ("gamegear", SaveShape.MULTI, ["save.sram"]),
    ],
)
def test_a_platforms_neutral_names_pass(
    platform: str, shape: SaveShape, members: list[str]
):
    check_neutral_unit(platform, shape, members)


@pytest.mark.parametrize(
    "platform,shape,members",
    [
        ("gb", SaveShape.MULTI, ["Pokemon Red.srm", "clock.rtc"]),
        ("nds", SaveShape.SINGLE, ["Mario Kart DS.dsv"]),
        ("nds", SaveShape.MULTI, ["Mario Kart DS.srm"]),
        ("snes", SaveShape.SINGLE, ["Game.srm"]),
        ("gba", SaveShape.MULTI, ["save.sram", "Pokemon.rtc"]),
        ("gb", SaveShape.SINGLE, ["clock.rtc"]),
        ("snes", SaveShape.MULTI, ["save.sram", "clock.rtc"]),
        ("gb", SaveShape.SINGLE, ["save.sram", "clock.rtc"]),
        ("dc", SaveShape.MULTI, ["vmu_E1.bin"]),
        ("fds", SaveShape.SINGLE, ["save.sram"]),
        ("arcade", SaveShape.SINGLE, ["nvram"]),
        ("genesis", SaveShape.SINGLE, ["Sonic.sav"]),
        ("genesis", SaveShape.MULTI, ["Sonic.srm"]),
        ("gamegear", SaveShape.MULTI, ["save.sram", "clock.rtc"]),
        ("sms", SaveShape.SINGLE, ["Game.srm", "save.sram"]),
        ("nes", SaveShape.SINGLE, ["Zelda.srm"]),
    ],
)
def test_other_names_are_refused(platform: str, shape: SaveShape, members: list[str]):
    with pytest.raises(NeutralUnitRejected):
        check_neutral_unit(platform, shape, members)
