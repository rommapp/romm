"""Maps the core ids RomM's web player matches saves on (e.g. "snes9x") to RetroArch's folder names (e.g. "Snes9x")."""

from utils.arcade_platforms import ARCADE_SET_PLATFORMS, MAME_SHORTNAME_PLATFORMS
from utils.platform_slugs import UniversalPlatformSlug as UPS

# The table follows github.com/Covin90/romm-retroarch-sync.

RETROARCH_DIR_BY_ROMM_EMULATOR: dict[str, str] = {
    # SNES
    "snes9x": "Snes9x",
    "bsnes": "bsnes",
    "mesen-s": "Mesen-S",
    # NES
    "nestopia": "Nestopia",
    "fceumm": "FCEUmm",
    "mesen": "Mesen",
    # PlayStation
    "mednafen_psx": "Beetle PSX",
    "mednafen_psx_hw": "Beetle PSX HW",
    "beetle_psx": "Beetle PSX",
    "beetle_psx_hw": "Beetle PSX HW",
    "pcsx_rearmed": "PCSX-ReARMed",
    "swanstation": "SwanStation",
    # Game Boy
    "gambatte": "Gambatte",
    "sameboy": "SameBoy",
    "tgbdual": "TGB Dual",
    "mgba": "mGBA",
    "vba_next": "VBA Next",
    "vbam": "VBA-M",
    # Genesis / Mega Drive
    "genesis_plus_gx": "Genesis Plus GX",
    "blastem": "BlastEm",
    "picodrive": "PicoDrive",
    # Nintendo 64
    "mupen64plus_next": "Mupen64Plus-Next",
    "parallel_n64": "ParaLLEl N64",
    # Saturn
    "mednafen_saturn": "Beetle Saturn",
    "beetle_saturn": "Beetle Saturn",
    "kronos": "Kronos",
    # Arcade / Neo Geo
    "mame": "MAME",
    "fbneo": "FBNeo",
    "fbalpha": "FB Alpha",
    # PlayStation 2 / GameCube
    "pcsx2": "PCSX2",
    "play": "Play!",
    "dolphin": "Dolphin",
    # Dreamcast
    "flycast": "Flycast",
    "redream": "Redream",
    # Atari
    "stella": "Stella",
    # PC Engine
    "mednafen_pce": "Beetle PCE",
    "mednafen_pce_fast": "Beetle PCE Fast",
    "beetle_pce": "Beetle PCE",
    "beetle_pce_fast": "Beetle PCE Fast",
    # Other common cores
    "dosbox_pure": "DOSBox-Pure",
    "scummvm": "ScummVM",
    "ppsspp": "PPSSPP",
    "desmume": "DeSmuME",
    "melonds": "melonDS",
    "citra": "Citra",
}


# Reversed so the first core listed for a shared folder wins, which is the
# `mednafen_*` id the web player (EmulatorJS) stores for the Beetle cores.
ROMM_EMULATOR_BY_RETROARCH_DIR: dict[str, str] = {
    dir_name: emulator
    for emulator, dir_name in reversed(RETROARCH_DIR_BY_ROMM_EMULATOR.items())
}


ROMM_EMULATORS_BY_RETROARCH_DIR: dict[str, frozenset[str]] = {
    dir_name: frozenset(
        emulator
        for emulator, emulator_dir in RETROARCH_DIR_BY_ROMM_EMULATOR.items()
        if emulator_dir == dir_name
    )
    for dir_name in ROMM_EMULATOR_BY_RETROARCH_DIR
}


def to_romm_emulator(retroarch_dir_name: str) -> str:
    """RomM's `emulator` for a RetroArch folder name, kept verbatim when unknown."""
    return ROMM_EMULATOR_BY_RETROARCH_DIR.get(retroarch_dir_name, retroarch_dir_name)


def to_retroarch_dir_name(romm_emulator: str) -> str:
    """RetroArch's folder name for a RomM `emulator`, unchanged when unknown."""
    return RETROARCH_DIR_BY_ROMM_EMULATOR.get(romm_emulator, romm_emulator)


def retroarch_aliases(romm_emulator: str | None) -> tuple[str | None, ...]:
    """Every `emulator` that syncs through the same RetroArch folder as this one, itself included."""
    if not romm_emulator:
        return (romm_emulator,)
    dir_name = to_retroarch_dir_name(romm_emulator)
    return tuple(
        sorted(
            {romm_emulator, dir_name}
            | ROMM_EMULATORS_BY_RETROARCH_DIR.get(dir_name, frozenset())
        )
    )


_SNES = frozenset({UPS.SNES, UPS.SFAM, UPS.SATELLAVIEW, UPS.SUFAMI_TURBO})
_NES = frozenset({UPS.NES, UPS.FAMICOM, UPS.FDS})
_GB = frozenset({UPS.GB, UPS.GBC})
_FINALBURN = ARCADE_SET_PLATFORMS | {UPS.NEOGEOAES, UPS.NEOGEOMVS}

# What each core folder runs, so a game name several platforms share resolves
# to the copy that core could have played.
PLATFORMS_BY_RETROARCH_DIR: dict[str, frozenset[str]] = {
    "Snes9x": _SNES,
    "bsnes": _SNES,
    "Mesen-S": _SNES,
    "Nestopia": _NES,
    "FCEUmm": _NES,
    "Mesen": _NES,
    "Beetle PSX": frozenset({UPS.PSX}),
    "Beetle PSX HW": frozenset({UPS.PSX}),
    "PCSX-ReARMed": frozenset({UPS.PSX}),
    "SwanStation": frozenset({UPS.PSX}),
    "Gambatte": _GB,
    "SameBoy": _GB,
    "TGB Dual": _GB,
    "mGBA": _GB | {UPS.GBA},
    "VBA Next": frozenset({UPS.GBA}),
    "VBA-M": _GB | {UPS.GBA},
    "Genesis Plus GX": frozenset(
        {UPS.GENESIS, UPS.SMS, UPS.GAMEGEAR, UPS.SEGACD, UPS.SG1000}
    ),
    "BlastEm": frozenset({UPS.GENESIS}),
    "PicoDrive": frozenset({UPS.GENESIS, UPS.SMS, UPS.SEGACD, UPS.SEGA32}),
    "Mupen64Plus-Next": frozenset({UPS.N64}),
    "ParaLLEl N64": frozenset({UPS.N64}),
    "Beetle Saturn": frozenset({UPS.SATURN}),
    "Kronos": frozenset({UPS.SATURN}),
    "MAME": MAME_SHORTNAME_PLATFORMS,
    "FBNeo": _FINALBURN,
    "FB Alpha": _FINALBURN,
    "PCSX2": frozenset({UPS.PS2}),
    "Play!": frozenset({UPS.PS2}),
    "Dolphin": frozenset({UPS.NGC, UPS.WII}),
    "Flycast": frozenset({UPS.DC}),
    "Redream": frozenset({UPS.DC}),
    "Stella": frozenset({UPS.ATARI2600}),
    "Beetle PCE": frozenset({UPS.TG16, UPS.TURBOGRAFX_CD, UPS.SUPERGRAFX}),
    "Beetle PCE Fast": frozenset({UPS.TG16, UPS.TURBOGRAFX_CD}),
    "DOSBox-Pure": frozenset({UPS.DOS}),
    "ScummVM": frozenset({UPS.SCUMMVM}),
    "PPSSPP": frozenset({UPS.PSP}),
    "DeSmuME": frozenset({UPS.NDS}),
    "melonDS": frozenset({UPS.NDS}),
    "Citra": frozenset({UPS.N3DS}),
}


def core_platforms(romm_emulator: str | None) -> frozenset[str]:
    """The platform slugs an `emulator`'s core runs, empty when unknown."""
    if not romm_emulator:
        return frozenset()
    return PLATFORMS_BY_RETROARCH_DIR.get(
        to_retroarch_dir_name(romm_emulator), frozenset()
    )
