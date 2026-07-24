"""Translates between RomM's `emulator` field convention (lowercase libretro
core identifier, e.g. "snes9x") and RetroArch's actual local save/state
directory name (its display name, e.g. "Snes9x"). These are not the same
string, and naively round-tripping one as the other has two failure modes:

- Writing RetroArch's raw folder name straight into `emulator` stores a save
  RomM's own web player can never select again -- `EmulatorJS.vue` filters
  saves by an exact match against the lowercase libretro core id, and
  `_EJS_CORES_MAP` in the frontend confirms that convention is RomM-wide, not
  cloud-sync-specific.
- Handing that raw value back out unchanged in the manifest can point
  RetroArch at a folder its own local install never uses (it's case- and
  spacing-sensitive), so the file silently never resolves as "already
  synced" and keeps re-appearing as a diff.

The table mirrors the community romm-retroarch-sync project
(github.com/Covin90/romm-retroarch-sync), which had already solved this
exact problem for the cores below. Anything outside the table round-trips
unchanged on the way back out to RetroArch rather than guessing at a casing
or spacing that hasn't been verified against a real install.
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
    "beetle_psx": "Beetle PSX",
    "beetle_psx_hw": "Beetle PSX HW",
    "pcsx_rearmed": "PCSX-ReARMed",
    "swanstation": "SwanStation",
    "mednafen_psx": "Beetle PSX",
    "mednafen_psx_hw": "Beetle PSX HW",
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
    "beetle_saturn": "Beetle Saturn",
    "kronos": "Kronos",
    "mednafen_saturn": "Beetle Saturn",
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
    "beetle_pce": "Beetle PCE",
    "beetle_pce_fast": "Beetle PCE Fast",
    "mednafen_pce": "Beetle PCE",
    "mednafen_pce_fast": "Beetle PCE Fast",
    # Other common cores
    "dosbox_pure": "DOSBox-Pure",
    "scummvm": "ScummVM",
    "ppsspp": "PPSSPP",
    "desmume": "DeSmuME",
    "melonds": "melonDS",
    "citra": "Citra",
}


def to_romm_emulator(retroarch_dir_name: str) -> str:
    """RetroArch's local directory name (e.g. "Snes9x") -> RomM's `emulator`
    convention (e.g. "snes9x"). A plain, universally-safe normalization --
    RomM's own convention is always lowercase with underscores, so this
    never needs a lookup table."""
    return retroarch_dir_name.lower().replace(" ", "_").replace("-", "_")


def to_retroarch_dir_name(romm_emulator: str) -> str:
    """RomM's `emulator` value -> RetroArch's local directory name. Cores
    outside the table round-trip unchanged: guessing at a casing or spacing
    that hasn't been verified against a real RetroArch install risks
    inventing a folder that's just as wrong as the untranslated one."""
    return RETROARCH_DIR_BY_ROMM_EMULATOR.get(romm_emulator.lower(), romm_emulator)
