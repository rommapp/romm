import pytest

from handler.snapshots.neutral import NeutralUnitRejected, check_neutral_unit
from models.assets import SaveShape


@pytest.mark.parametrize(
    "platform,shape,members",
    [
        ("gb", SaveShape.SINGLE, ["save.sram"]),
        ("gbc", SaveShape.MULTI, ["save.sram", "clock.rtc"]),
        ("snes", SaveShape.SINGLE, ["save.sram"]),
        ("n64", SaveShape.MULTI, ["eeprom", "pak1"]),
        ("nds", SaveShape.SINGLE, ["save.raw"]),
        ("saturn", SaveShape.MULTI, ["backup.ram", "cart.ram"]),
        ("dc", SaveShape.MULTI, ["vmu_A1.bin", "vmu_B2.bin"]),
        ("psx", SaveShape.SINGLE, ["anything.mcd"]),
    ],
)
def test_a_platforms_neutral_names_pass(
    platform: str, shape: SaveShape, members: list[str]
):
    check_neutral_unit(platform, shape, members)


@pytest.mark.parametrize(
    "platform,shape,members",
    [
        ("gb", SaveShape.SINGLE, ["Pokemon Red.srm"]),
        ("gba", SaveShape.MULTI, ["save.sram", "Pokemon.rtc"]),
        ("gb", SaveShape.SINGLE, ["clock.rtc"]),
        ("snes", SaveShape.MULTI, ["save.sram", "clock.rtc"]),
        ("gb", SaveShape.SINGLE, ["save.sram", "clock.rtc"]),
        ("dc", SaveShape.MULTI, ["vmu_E1.bin"]),
        ("fds", SaveShape.SINGLE, ["save.sram"]),
        ("arcade", SaveShape.SINGLE, ["nvram"]),
    ],
)
def test_other_names_are_refused(platform: str, shape: SaveShape, members: list[str]):
    with pytest.raises(NeutralUnitRejected):
        check_neutral_unit(platform, shape, members)
