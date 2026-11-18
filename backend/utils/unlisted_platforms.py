"""Platforms no metadata provider lists, named by hand.

Batocera and RetroBat give each source port, engine and app a system of its own.
"""

from collections.abc import Mapping
from typing import Final, NamedTuple, cast

from utils.platform_slugs import UniversalPlatformSlug as UPS


class UnlistedPlatform(NamedTuple):
    name: str
    # The platform the original game shipped on, whose provider entries a title
    # search falls back to. None when the port has no single original.
    host: UPS | None = None


UNLISTED_PLATFORMS: Final[dict[UPS, UnlistedPlatform]] = {
    UPS._2SHIP: UnlistedPlatform("2 Ship 2 Harkinian", UPS.N64),
    UPS.ABUSE: UnlistedPlatform("Abuse", UPS.DOS),
    UPS.BENNUGD: UnlistedPlatform("BennuGD"),
    UPS.BSTONE: UnlistedPlatform("Blake Stone", UPS.DOS),
    UPS.BSYNDROME: UnlistedPlatform("Bermuda Syndrome", UPS.DOS),
    UPS.CANNONBALL: UnlistedPlatform("Cannonball", UPS.ARCADE),
    UPS.CATACOMB: UnlistedPlatform("CatacombGL", UPS.DOS),
    UPS.CAVESTORY: UnlistedPlatform("Cave Story", UPS.WIN),
    UPS.CDOGS: UnlistedPlatform("C-Dogs SDL", UPS.DOS),
    UPS.CGENIUS: UnlistedPlatform("Commander Genius", UPS.DOS),
    UPS.CORSIXTH: UnlistedPlatform("CorsixTH", UPS.DOS),
    UPS.CTVBOY: UnlistedPlatform("Gakken Compact Vision TV Boy"),
    UPS.DEVILUTIONX: UnlistedPlatform("DevilutionX", UPS.WIN),
    UPS.DINOTHAWR: UnlistedPlatform("Dinothawr"),
    UPS.DOOM3: UnlistedPlatform("Doom 3", UPS.WIN),
    UPS.DUSKLIGHT: UnlistedPlatform("DuskLight", UPS.NGC),
    UPS.DXX_REBIRTH: UnlistedPlatform("DXX-Rebirth", UPS.DOS),
    UPS.ECWOLF: UnlistedPlatform("ECWolf", UPS.DOS),
    UPS.EDUKE32: UnlistedPlatform("EDuke32", UPS.DOS),
    UPS.ETLEGACY: UnlistedPlatform("ET: Legacy", UPS.WIN),
    UPS.FALLOUT1_CE: UnlistedPlatform("Fallout Community Edition", UPS.WIN),
    UPS.FALLOUT2_CE: UnlistedPlatform("Fallout 2 Community Edition", UPS.WIN),
    UPS.FPINBALL: UnlistedPlatform("Future Pinball"),
    UPS.FURY: UnlistedPlatform("Ion Fury", UPS.WIN),
    UPS.GAMETANK: UnlistedPlatform("GameTank"),
    UPS.GEMRB: UnlistedPlatform("GemRB", UPS.WIN),
    UPS.GHOSTSHIP: UnlistedPlatform("Ghostship", UPS.N64),
    UPS.GONG: UnlistedPlatform("Gong"),
    UPS.HALFLIFE: UnlistedPlatform("Half-Life", UPS.WIN),
    UPS.HCL: UnlistedPlatform("Hydra Castle Labyrinth", UPS.WIN),
    UPS.HURRICAN: UnlistedPlatform("Hurrican", UPS.WIN),
    UPS.IKEMEN: UnlistedPlatform("IKEMEN GO", UPS.MUGEN),
    UPS.JAZZ2: UnlistedPlatform("Jazz Jackrabbit 2", UPS.WIN),
    UPS.JKDF2: UnlistedPlatform("Jedi Knight: Dark Forces II", UPS.WIN),
    UPS.JKNIGHT: UnlistedPlatform("Jedi Knight: Jedi Academy", UPS.WIN),
    UPS.KARAOKE: UnlistedPlatform("Karaoke"),
    UPS.LOVE: UnlistedPlatform("LÖVE"),
    UPS.LOWRESNX: UnlistedPlatform("LowRes NX"),
    UPS.LUTRO: UnlistedPlatform("Lutro"),
    UPS.MOHAA: UnlistedPlatform("Medal of Honor: Allied Assault", UPS.WIN),
    UPS.MRBOOM: UnlistedPlatform("Mr.Boom", UPS.DOS),
    UPS.ODCOMMANDER: UnlistedPlatform("OD-Commander"),
    UPS.OPENGOAL: UnlistedPlatform("OpenGOAL", UPS.PS2),
    UPS.OPENJAZZ: UnlistedPlatform("OpenJazz", UPS.DOS),
    UPS.OPENLARA: UnlistedPlatform("OpenLara", UPS.WIN),
    UPS.P2000T: UnlistedPlatform("Philips P2000T"),
    UPS.PDARK: UnlistedPlatform("Perfect Dark", UPS.N64),
    UPS.PINBALLFX: UnlistedPlatform("Pinball FX", UPS.WIN),
    UPS.PINBALLFX2: UnlistedPlatform("Pinball FX2", UPS.WIN),
    UPS.PINBALLFX3: UnlistedPlatform("Pinball FX3", UPS.WIN),
    UPS.PINBALLM: UnlistedPlatform("Pinball M", UPS.WIN),
    UPS.PORTS: UnlistedPlatform("Ports"),
    UPS.POWERBOMBERMAN: UnlistedPlatform("Power Bomberman", UPS.WIN),
    UPS.PYGAME: UnlistedPlatform("Pygame"),
    UPS.PYXEL: UnlistedPlatform("Pyxel"),
    UPS.QUAKE: UnlistedPlatform("Quake", UPS.DOS),
    UPS.QUAKE2: UnlistedPlatform("Quake II", UPS.WIN),
    UPS.QUAKE3: UnlistedPlatform("Quake III", UPS.WIN),
    UPS.RAZE: UnlistedPlatform("Raze", UPS.DOS),
    UPS.RECOMP: UnlistedPlatform("Recompilations", UPS.N64),
    UPS.REMINISCENCE: UnlistedPlatform("REminiscence", UPS.DOS),
    UPS.ROTT: UnlistedPlatform("Rise of the Triad", UPS.DOS),
    UPS.RTCW: UnlistedPlatform("Return to Castle Wolfenstein", UPS.WIN),
    UPS.RX78: UnlistedPlatform("Bandai RX-78"),
    UPS.SDLPOP: UnlistedPlatform("SDLPoP", UPS.DOS),
    UPS.SEGAAI: UnlistedPlatform("Sega AI Computer"),
    UPS.SOH: UnlistedPlatform("Ship of Harkinian", UPS.N64),
    UPS.SOLARUS: UnlistedPlatform("Solarus"),
    UPS.SONIC3_AIR: UnlistedPlatform("Sonic 3 A.I.R.", UPS.GENESIS),
    UPS.SONIC_MANIA: UnlistedPlatform("Sonic Mania", UPS.WIN),
    UPS.SONICRETRO: UnlistedPlatform("Sonic Retro Engine", UPS.WIN),
    UPS.STARSHIP: UnlistedPlatform("Starship", UPS.N64),
    UPS.SUPERBROSWAR: UnlistedPlatform("Super Mario War", UPS.WIN),
    UPS.THEFORCEENGINE: UnlistedPlatform("The Force Engine", UPS.DOS),
    UPS.THEXTECH: UnlistedPlatform("TheXTech", UPS.WIN),
    UPS.TRAIDER: UnlistedPlatform("Tomb Raider I, II & III", UPS.WIN),
    UPS.TVC: UnlistedPlatform("Videoton TV-Computer"),
    UPS.TYRIAN: UnlistedPlatform("Tyrian", UPS.DOS),
    UPS.UQM: UnlistedPlatform("The Ur-Quan Masters", UPS.DOS),
    UPS.VGMPLAY: UnlistedPlatform("VGMPlay"),
    UPS.VIRCON32: UnlistedPlatform("Vircon32"),
    UPS.XRICK: UnlistedPlatform("xrick", UPS.DOS),
    UPS.ZACCARIAPINBALL: UnlistedPlatform("Zaccaria Pinball", UPS.WIN),
}


def host_fallbacks[T: Mapping[str, object]](
    platforms: Mapping[UPS, T],
) -> dict[UPS, T]:
    """A provider's host entry, under the port's name, for each port it doesn't list."""
    fallbacks: dict[UPS, T] = {}
    for slug, platform in UNLISTED_PLATFORMS.items():
        if platform.host is None or platform.host not in platforms:
            continue
        if slug in platforms:
            continue
        # The host's other names would make the port searchable as the host.
        entry = {
            key: value
            for key, value in platforms[platform.host].items()
            if key != "alternative_names"
        }
        fallbacks[slug] = cast(T, {**entry, "name": platform.name})
    return fallbacks
