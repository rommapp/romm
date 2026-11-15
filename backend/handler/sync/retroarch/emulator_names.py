"""Maps the core ids RomM's web player matches saves on (e.g. "snes9x") to RetroArch's folder names (e.g. "Snes9x")."""

from collections import defaultdict

from utils.arcade_platforms import ARCADE_SET_PLATFORMS, MAME_SHORTNAME_PLATFORMS
from utils.emulatorjs_cores import (
    EJS_CORES_BY_PLATFORM,
    EJS_NIGHTLY_CORES_BY_PLATFORM,
)
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
    "fbneo": "FinalBurn Neo",
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
    "dosbox_pure": "DOSBox-pure",
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

# What RetroArch runs a core on beyond the platforms the web player offers it for.
RETROARCH_PLATFORMS_BY_ROMM_EMULATOR: dict[str, frozenset[str]] = {
    "snes9x": _SNES,
    "bsnes": _SNES,
    "mesen-s": _SNES,
    "mesen": _NES,
    "mednafen_psx": frozenset({UPS.PSX}),
    "swanstation": frozenset({UPS.PSX}),
    "sameboy": _GB,
    "tgbdual": _GB,
    "vba_next": frozenset({UPS.GBA}),
    "vbam": _GB | {UPS.GBA},
    "genesis_plus_gx": frozenset({UPS.SG1000}),
    "blastem": frozenset({UPS.GENESIS}),
    "picodrive": frozenset(
        {UPS.GENESIS, UPS.SMS, UPS.SEGACD32, UPS.PICO, UPS.SEGA_PICO}
    ),
    "mupen64plus_next": frozenset({UPS.N64DD}),
    "mednafen_saturn": frozenset({UPS.SATURN}),
    "kronos": frozenset({UPS.SATURN, UPS.STV}),
    "mame": MAME_SHORTNAME_PLATFORMS,
    "fbneo": _FINALBURN,
    "fbalpha": _FINALBURN,
    "pcsx2": frozenset({UPS.PS2}),
    "play": frozenset({UPS.PS2}),
    "dolphin": frozenset({UPS.NGC, UPS.WII}),
    "flycast": frozenset({UPS.DC, UPS.NAOMI, UPS.NAOMI2, UPS.NAOMIGD, UPS.ATOMISWAVE}),
    "redream": frozenset({UPS.DC}),
    "stella": frozenset({UPS.ATARI2600}),
    "mednafen_pce_fast": frozenset({UPS.TG16, UPS.TURBOGRAFX_CD}),
    "scummvm": frozenset({UPS.SCUMMVM}),
    "ppsspp": frozenset({UPS.PSP_MINIS}),
    "citra": frozenset({UPS.N3DS, UPS.NEW_NINTENDON3DS}),
}


def _platforms_by_romm_emulator() -> dict[str, frozenset[str]]:
    platforms: defaultdict[str, set[str]] = defaultdict(set)
    for cores_by_platform in (EJS_CORES_BY_PLATFORM, EJS_NIGHTLY_CORES_BY_PLATFORM):
        for platform, cores in cores_by_platform.items():
            for core in cores:
                platforms[core].add(platform)
    for core, extra in RETROARCH_PLATFORMS_BY_ROMM_EMULATOR.items():
        platforms[core] |= extra
    return {core: frozenset(slugs) for core, slugs in platforms.items()}


PLATFORMS_BY_ROMM_EMULATOR = _platforms_by_romm_emulator()


def core_platforms(romm_emulator: str | None) -> frozenset[str]:
    """The platform slugs the core an `emulator` names runs, across its aliases, empty when unknown."""
    return frozenset().union(
        *(
            PLATFORMS_BY_ROMM_EMULATOR.get(alias, frozenset())
            for alias in retroarch_aliases(romm_emulator)
            if alias
        )
    )
