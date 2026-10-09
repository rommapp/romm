"""The member names a neutral save unit may hold, per platform.

Units named after the game (cards, folders, title saves) get only the archive
check every upload passes.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

from models.assets import SaveShape
from utils.platform_slugs import UniversalPlatformSlug as UPS


class NeutralUnitRejected(ValueError):
    """A unit labelled neutral that doesn't hold the platform's neutral form."""


@dataclass(frozen=True)
class _Form:
    allowed: re.Pattern[str]
    # At least one present member must match this.
    primary: re.Pattern[str]


def _names(*names: str) -> re.Pattern[str]:
    return re.compile("|".join(re.escape(name) for name in names))


_BATTERY = _Form(_names("save.sram"), _names("save.sram"))
_CLOCKED = _Form(_names("save.sram", "clock.rtc"), _names("save.sram"))
_RAW = _Form(_names("save.raw"), _names("save.raw"))
_BACKUP_RAM = _Form(_names("backup.ram", "cart.ram"), _names("backup.ram", "cart.ram"))
_N64_CHIPS = _names("eeprom", "pak1", "pak2", "pak3", "pak4", "sram", "flash")

NEUTRAL_FORMS: Final[dict[str, _Form]] = {
    UPS.NES: _BATTERY,
    UPS.FAMICOM: _BATTERY,
    UPS.SNES: _BATTERY,
    UPS.SFAM: _BATTERY,
    UPS.GENESIS: _BATTERY,
    UPS.SMS: _BATTERY,
    UPS.GAMEGEAR: _BATTERY,
    UPS.SEGA32: _BATTERY,
    UPS.GB: _CLOCKED,
    UPS.GBC: _CLOCKED,
    UPS.GBA: _CLOCKED,
    UPS.N64: _Form(_N64_CHIPS, _N64_CHIPS),
    UPS.NDS: _RAW,
    UPS.JAGUAR: _RAW,
    UPS.LYNX: _RAW,
    UPS.NEO_GEO_POCKET: _RAW,
    UPS.NEO_GEO_POCKET_COLOR: _RAW,
    UPS.WONDERSWAN: _RAW,
    UPS.WONDERSWAN_COLOR: _RAW,
    UPS.POKEMON_MINI: _RAW,
    UPS.SEGACD: _BACKUP_RAM,
    UPS.SATURN: _BACKUP_RAM,
    UPS.DC: _Form(
        re.compile(r"vmu_[A-D][1-2]\.bin"), re.compile(r"vmu_[A-D][1-2]\.bin")
    ),
}

# Platforms with no neutral form defined yet; they sync natively.
NO_NEUTRAL_FORM: Final = frozenset({UPS.FDS, UPS.ARCADE})


def check_neutral_unit(
    platform_slug: str, shape: SaveShape, members: Collection[str]
) -> None:
    """Refuse a neutral unit whose members aren't the platform's neutral names.

    Args:
        members: the archive's file entries, or the raw part's file name for a
            `SINGLE` unit.

    Raises:
        NeutralUnitRejected: with the reason a client can show.
    """
    if platform_slug in NO_NEUTRAL_FORM:
        raise NeutralUnitRejected(
            f"{platform_slug} has no neutral form yet; push it as native"
        )
    form = NEUTRAL_FORMS.get(platform_slug)
    if form is None:
        return
    strays = sorted(name for name in members if not form.allowed.fullmatch(name))
    if strays:
        raise NeutralUnitRejected(
            f"{', '.join(strays)} isn't a neutral member name for {platform_slug}"
        )
    if not any(form.primary.fullmatch(name) for name in members):
        raise NeutralUnitRejected(f"the unit holds no save for {platform_slug}")
    if shape == SaveShape.SINGLE and len(members) != 1:
        raise NeutralUnitRejected("a SINGLE unit holds exactly one member")
