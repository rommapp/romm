"""Maps RomM's `emulator` values (lowercase libretro core ids, e.g. "snes9x") to
RetroArch's save/state folder names (e.g. "Snes9x") and back.

RomM's web player matches saves on the core id, while RetroArch looks for the
exact folder name. The table follows github.com/Covin90/romm-retroarch-sync.
"""

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


def to_romm_emulator(retroarch_dir_name: str) -> str:
    """RomM's `emulator` for a RetroArch folder name, kept verbatim when unknown."""
    return ROMM_EMULATOR_BY_RETROARCH_DIR.get(retroarch_dir_name, retroarch_dir_name)


def to_retroarch_dir_name(romm_emulator: str) -> str:
    """RetroArch's folder name for a RomM `emulator`, unchanged when unknown."""
    return RETROARCH_DIR_BY_ROMM_EMULATOR.get(romm_emulator, romm_emulator)
