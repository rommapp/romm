"""Arcade platform groupings shared by the providers, the player and the feeds."""

from collections.abc import Iterable, Mapping
from typing import Final

from utils.platform_slugs import UniversalPlatformSlug as UPS

# Platforms whose games are MAME or FinalBurn romsets.
ARCADE_SET_PLATFORMS: Final = frozenset(
    {UPS.ARCADE, UPS.MAME, UPS.MAME_ADVMAME, UPS.FBNEO, UPS.FBA}
)

# Set platforms a browser emulator runs. None ships an AdvanceMAME core.
PLAYABLE_ARCADE_SET_PLATFORMS: Final = ARCADE_SET_PLATFORMS - {UPS.MAME_ADVMAME}

# Every arcade platform. A provider without a platform of its own for one
# uses its Arcade entry instead.
ARCADE_PLATFORMS: Final = ARCADE_SET_PLATFORMS | {
    UPS.ATOMISWAVE,
    UPS.CHIHIRO,
    UPS.DAPHNE,
    UPS.DICE,
    UPS.GAELCO,
    UPS.HIKARU,
    UPS.LINDBERGH,
    UPS.MODEL2,
    UPS.MODEL3,
    UPS.NAMCO2X6,
    UPS.NAMCO3XX,
    UPS.NAOMI,
    UPS.NAOMI2,
    UPS.NAOMIGD,
    UPS.SINGE,
    UPS.STV,
    UPS.TRIFORCE,
    UPS.TYPE_X,
}

# Platforms whose filenames are MAME shortnames: the set platforms, the boards
# MAME runs, and Neo Geo. Daphne and Singe sets are named differently.
MAME_SHORTNAME_PLATFORMS: Final = ARCADE_SET_PLATFORMS | {
    UPS.ATOMISWAVE,
    UPS.GAELCO,
    UPS.HIKARU,
    UPS.MODEL2,
    UPS.MODEL3,
    UPS.NAMCO2X6,
    UPS.NAOMI,
    UPS.NAOMI2,
    UPS.NAOMIGD,
    UPS.NEOGEOAES,
    UPS.NEOGEOMVS,
    UPS.STV,
}


def arcade_fallbacks[T](
    platforms: Mapping[UPS, T], slugs: Iterable[UPS] = ARCADE_PLATFORMS
) -> dict[UPS, T]:
    """A provider's Arcade entry for each of `slugs` it has no entry of its own for."""
    return {slug: platforms[UPS.ARCADE] for slug in slugs if slug not in platforms}
