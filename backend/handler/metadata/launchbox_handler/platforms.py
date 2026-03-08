from typing import TypedDict

from ..base_handler import UniversalPlatformSlug as UPS
from .types import LaunchboxPlatform


class SlugToLaunchboxId(TypedDict):
    id: int
    name: str


LAUNCHBOX_PLATFORM_LIST: dict[UPS, SlugToLaunchboxId] = {
    UPS.VECTOR_06C: {"id": 199, "name": "Vector-06C"},
    UPS._3DO: {"id": 1, "name": "3DO Interactive Multiplayer"},
    UPS.N3DS: {"id": 24, "name": "Nintendo 3DS"},
    UPS.N64DD: {"id": 194, "name": "Nintendo 64DD"},
    UPS.ACORN_ARCHIMEDES: {"id": 74, "name": "Acorn Archimedes"},
    UPS.ACORN_ELECTRON: {"id": 65, "name": "Acorn Electron"},
    UPS.ACPC: {"id": 3, "name": "Amstrad CPC"},
    UPS.ACTION_MAX: {"id": 154, "name": "WoW Action Max"},
    UPS.ADVENTURE_VISION: {
        "id": 67,
        "name": "Entex Adventure Vision",
    },
    UPS.ALICE_3290: {"id": 189, "name": "Matra and Hachette Alice"},
    UPS.AMIGA: {"id": 2, "name": "Commodore Amiga"},
    UPS.AMIGA_CD32: {"id": 119, "name": "Commodore Amiga CD32"},
    UPS.AMSTRAD_GX4000: {"id": 109, "name": "Amstrad GX4000"},
    UPS.ANDROID: {"id": 4, "name": "Android"},
    UPS.APF: {"id": 68, "name": "APF Imagination Machine"},
    UPS.APPLE_IIGS: {"id": 112, "name": "Apple IIGS"},
    UPS.APPLEII: {"id": 110, "name": "Apple II"},
    UPS.ARCADE: {"id": 5, "name": "Arcade"},
    UPS.ARCADIA_2001: {"id": 79, "name": "Emerson Arcadia 2001"},
    UPS.ASTROCADE: {"id": 77, "name": "Bally Astrocade"},
    UPS.ATARI_JAGUAR_CD: {"id": 10, "name": "Atari Jaguar CD"},
    UPS.ATARI_ST: {"id": 76, "name": "Atari ST"},
    UPS.ATARI_XEGS: {"id": 12, "name": "Atari XEGS"},
    UPS.ATARI2600: {"id": 6, "name": "Atari 2600"},
    UPS.ATARI5200: {"id": 7, "name": "Atari 5200"},
    UPS.ATARI7800: {"id": 8, "name": "Atari 7800"},
    UPS.ATARI800: {"id": 102, "name": "Atari 800"},
    UPS.ATMOS: {"id": 64, "name": "Oric Atmos"},
    UPS.ATOM: {"id": 107, "name": "Acorn Atom"},
    UPS.BBCMICRO: {"id": 59, "name": "BBC Microcomputer System"},
    UPS.BK: {"id": 131, "name": "Elektronika BK"},
    UPS.BK_01: {"id": 175, "name": "Apogee BK-01"},
    UPS.BROWSER: {"id": 85, "name": "Web Browser"},
    UPS.C_PLUS_4: {"id": 121, "name": "Commodore Plus 4"},
    UPS.C128: {"id": 118, "name": "Commodore 128"},
    UPS.C64: {"id": 14, "name": "Commodore 64"},
    UPS.CAMPUTERS_LYNX: {"id": 61, "name": "Camputers Lynx"},
    UPS.CASIO_LOOPY: {"id": 114, "name": "Casio Loopy"},
    UPS.CASIO_PV_1000: {"id": 115, "name": "Casio PV-1000"},
    UPS.COLECOADAM: {"id": 117, "name": "Coleco Adam"},
    UPS.COLECOVISION: {"id": 13, "name": "ColecoVision"},
    UPS.COLOUR_GENIE: {"id": 73, "name": "EACA EG2000 Colour Genie"},
    UPS.COMMODORE_CDTV: {"id": 120, "name": "Commodore CDTV"},
    UPS.CPET: {"id": 180, "name": "Commodore PET"},
    UPS.CREATIVISION: {"id": 152, "name": "VTech CreatiVision"},
    UPS.DC: {"id": 40, "name": "Sega Dreamcast"},
    UPS.DOS: {"id": 83, "name": "MS-DOS"},
    UPS.DRAGON_32_SLASH_64: {"id": 66, "name": "Dragon 32/64"},
    UPS.ENTERPRISE: {"id": 72, "name": "Enterprise"},
    UPS.EPOCH_GAME_POCKET_COMPUTER: {
        "id": 132,
        "name": "Epoch Game Pocket Computer",
    },
    UPS.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 81,
        "name": "Epoch Super Cassette Vision",
    },
    UPS.EXELVISION: {"id": 183, "name": "Exelvision EXL 100"},
    UPS.EXIDY_SORCERER: {"id": 184, "name": "Exidy Sorcerer"},
    UPS.FAIRCHILD_CHANNEL_F: {
        "id": 58,
        "name": "Fairchild Channel F",
    },
    UPS.FAMICOM: {"id": 27, "name": "Nintendo Famicom"},
    UPS.FDS: {"id": 157, "name": "Nintendo Famicom Disk System"},
    UPS.FM_7: {"id": 186, "name": "Fujitsu FM-7"},
    UPS.FM_TOWNS: {"id": 124, "name": "Fujitsu FM Towns Marty"},
    UPS.G_AND_W: {"id": 166, "name": "Nintendo Game & Watch"},
    UPS.GAME_DOT_COM: {"id": 63, "name": "Tiger Game.com"},
    UPS.GAME_WAVE: {"id": 216, "name": "GameWave"},
    UPS.GAMEGEAR: {"id": 41, "name": "Sega Game Gear"},
    UPS.GB: {"id": 28, "name": "Nintendo Game Boy"},
    UPS.GBA: {"id": 29, "name": "Nintendo Game Boy Advance"},
    UPS.GBC: {"id": 30, "name": "Nintendo Game Boy Color"},
    UPS.GENESIS: {"id": 42, "name": "Sega Genesis"},
    UPS.GP32: {"id": 135, "name": "GamePark GP32"},
    UPS.HARTUNG: {"id": 136, "name": "Hartung Game Master"},
    UPS.HIKARU: {"id": 208, "name": "Sega Hikaru"},
    UPS.HRX: {"id": 187, "name": "Hector HRX"},
    UPS.HYPERSCAN: {"id": 171, "name": "Mattel HyperScan"},
    UPS.INTELLIVISION: {"id": 15, "name": "Mattel Intellivision"},
    UPS.IOS: {"id": 16, "name": "Apple iOS"},
    UPS.JAGUAR: {"id": 9, "name": "Atari Jaguar"},
    UPS.JUPITER_ACE: {"id": 70, "name": "Jupiter Ace"},
    UPS.LINUX: {"id": 218, "name": "Linux"},
    UPS.LYNX: {"id": 11, "name": "Atari Lynx"},
    UPS.MAC: {"id": 17, "name": "Apple Mac OS"},
    UPS.AQUARIUS: {"id": 69, "name": "Mattel Aquarius"},
    UPS.MEGA_DUCK_SLASH_COUGAR_BOY: {"id": 127, "name": "Mega Duck"},
    UPS.MODEL1: {"id": 104, "name": "Sega Model 1"},
    UPS.MODEL2: {"id": 88, "name": "Sega Model 2"},
    UPS.MODEL3: {"id": 94, "name": "Sega Model 3"},
    UPS.MSX: {"id": 82, "name": "Microsoft MSX"},
    UPS.MSX2: {"id": 190, "name": "Microsoft MSX2"},
    UPS.MSX2PLUS: {"id": 191, "name": "Microsoft MSX2+"},
    UPS.MTX512: {"id": 60, "name": "Memotech MTX512"},
    UPS.MUGEN: {"id": 138, "name": "MUGEN"},
    UPS.MULTIVISION: {"id": 197, "name": "Othello Multivision"},
    UPS.N64: {"id": 25, "name": "Nintendo 64"},
    UPS.NDS: {"id": 26, "name": "Nintendo DS"},
    UPS.NEO_GEO_CD: {"id": 167, "name": "SNK Neo Geo CD"},
    UPS.NEO_GEO_POCKET: {"id": 21, "name": "SNK Neo Geo Pocket"},
    UPS.NEO_GEO_POCKET_COLOR: {
        "id": 22,
        "name": "SNK Neo Geo Pocket Color",
    },
    UPS.NEOGEOAES: {"id": 23, "name": "SNK Neo Geo AES"},
    UPS.NEOGEOMVS: {"id": 210, "name": "SNK Neo Geo MVS"},
    UPS.NES: {"id": 27, "name": "Nintendo Entertainment System"},
    UPS.NGAGE: {"id": 213, "name": "Nokia N-Gage"},
    UPS.NGC: {"id": 31, "name": "Nintendo GameCube"},
    UPS.NUON: {"id": 126, "name": "Nuon"},
    UPS.ODYSSEY: {"id": 78, "name": "Magnavox Odyssey"},
    UPS.ODYSSEY_2: {
        "id": 57,
        "name": "Magnavox Odyssey 2",
    },
    UPS.OPENBOR: {"id": 139, "name": "OpenBOR"},
    UPS.OUYA: {"id": 35, "name": "Ouya"},
    UPS.PC_8800_SERIES: {"id": 192, "name": "NEC PC-8801"},
    UPS.PC_9800_SERIES: {"id": 193, "name": "NEC PC-9801"},
    UPS.PC_FX: {"id": 161, "name": "NEC PC-FX"},
    UPS.PEGASUS: {"id": 174, "name": "Aamber Pegasus"},
    UPS.PHILIPS_CD_I: {"id": 37, "name": "Philips CD-i"},
    UPS.PHILIPS_VG_5000: {"id": 140, "name": "Philips VG 5000"},
    UPS.PICO: {"id": 220, "name": "PICO-8"},
    UPS.PINBALL: {"id": 151, "name": "Pinball"},
    UPS.POCKETSTATION: {"id": 203, "name": "Sony PocketStation"},
    UPS.POKEMON_MINI: {"id": 195, "name": "Nintendo Pokemon Mini"},
    UPS.PS2: {"id": 48, "name": "Sony Playstation 2"},
    UPS.PS3: {"id": 49, "name": "Sony Playstation 3"},
    UPS.PS4: {"id": 50, "name": "Sony Playstation 4"},
    UPS.PS5: {"id": 219, "name": "Sony Playstation 5"},
    UPS.PSP: {"id": 52, "name": "Sony PSP"},
    UPS.PSP_MINIS: {"id": 202, "name": "Sony PSP Minis"},
    UPS.PSVITA: {"id": 51, "name": "Sony Playstation Vita"},
    UPS.PSX: {"id": 47, "name": "Sony Playstation"},
    UPS.RCA_STUDIO_II: {"id": 142, "name": "RCA Studio II"},
    UPS.SAM_COUPE: {"id": 71, "name": "SAM Coupé"},
    UPS.SATELLAVIEW: {"id": 168, "name": "Nintendo Satellaview"},
    UPS.SATURN: {"id": 45, "name": "Sega Saturn"},
    UPS.SC3000: {"id": 145, "name": "Sega SC-3000"},
    UPS.SCUMMVM: {"id": 143, "name": "ScummVM"},
    UPS.SEGA_PICO: {"id": 105, "name": "Sega Pico"},
    UPS.SEGA32: {"id": 38, "name": "Sega 32X"},
    UPS.SEGACD: {"id": 39, "name": "Sega CD"},
    UPS.SEGACD32: {"id": 173, "name": "Sega CD 32X"},
    UPS.SERIES_X_S: {"id": 222, "name": "Microsoft Xbox Series X/S"},
    UPS.SFAM: {"id": 53, "name": "Super Famicom"},
    UPS.SG1000: {"id": 80, "name": "Sega SG-1000"},
    UPS.SHARP_MZ_80B20002500: {"id": 205, "name": "Sharp MZ-2500"},
    UPS.SHARP_X68000: {"id": 128, "name": "Sharp X68000"},
    UPS.SMS: {"id": 43, "name": "Sega Master System"},
    UPS.SNES: {
        "id": 53,
        "name": "Super Nintendo Entertainment System",
    },
    UPS.SOCRATES: {"id": 198, "name": "VTech Socrates"},
    UPS.SORD_M5: {"id": 148, "name": "Sord M5"},
    UPS.SPECTRAVIDEO: {"id": 201, "name": "Spectravideo"},
    UPS.STV: {"id": 146, "name": "Sega ST-V"},
    UPS.SUPER_VISION_8000: {
        "id": 223,
        "name": "Bandai Super Vision 8000",
    },
    UPS.SUPERGRAFX: {"id": 162, "name": "PC Engine SuperGrafx"},
    UPS.SWITCH: {"id": 211, "name": "Nintendo Switch"},
    UPS.SWITCH_2: {"id": 224, "name": "Nintendo Switch 2"},
    UPS.SYSTEM_32: {"id": 93, "name": "Namco System 22"},
    UPS.SYSTEM16: {"id": 97, "name": "Sega System 16"},
    UPS.SYSTEM32: {"id": 96, "name": "Sega System 32"},
    UPS.TG16: {"id": 54, "name": "NEC TurboGrafx-16"},
    UPS.TI_994A: {"id": 149, "name": "Texas Instruments TI 99/4A"},
    UPS.TOMY_TUTOR: {"id": 200, "name": "Tomy Tutor"},
    UPS.TRS_80: {"id": 129, "name": "Tandy TRS-80"},
    UPS.TRS_80_COLOR_COMPUTER: {
        "id": 164,
        "name": "TRS-80 Color Computer",
    },
    UPS.TURBOGRAFX_CD: {"id": 163, "name": "NEC TurboGrafx-CD"},
    UPS.TYPE_X: {"id": 169, "name": "Taito Type X"},
    UPS.VC_4000: {"id": 137, "name": "Interton VC 4000"},
    UPS.VECTREX: {"id": 125, "name": "GCE Vectrex"},
    UPS.VIC_20: {"id": 122, "name": "Commodore VIC-20"},
    UPS.VIDEOPAC_G7400: {"id": 141, "name": "Philips Videopac+"},
    UPS.VIRTUALBOY: {"id": 32, "name": "Nintendo Virtual Boy"},
    UPS.VMU: {"id": 144, "name": "Sega Dreamcast VMU"},
    UPS.VSMILE: {"id": 221, "name": "VTech V.Smile"},
    UPS.SUPERVISION: {"id": 153, "name": "Watara Supervision"},
    UPS.WII: {"id": 33, "name": "Nintendo Wii"},
    UPS.WIIU: {"id": 34, "name": "Nintendo Wii U"},
    UPS.WIN: {"id": 84, "name": "Windows"},
    UPS.WIN3X: {"id": 212, "name": "Windows 3.X"},
    UPS.WONDERSWAN: {"id": 55, "name": "WonderSwan"},
    UPS.WONDERSWAN_COLOR: {"id": 56, "name": "WonderSwan Color"},
    UPS.X1: {"id": 204, "name": "Sharp X1"},
    UPS.XAVIXPORT: {"id": 170, "name": "XaviXPORT"},
    UPS.XBOX: {"id": 18, "name": "Microsoft Xbox"},
    UPS.XBOX360: {"id": 19, "name": "Microsoft Xbox 360"},
    UPS.XBOXONE: {"id": 20, "name": "Microsoft Xbox One"},
    UPS.ZINC: {"id": 155, "name": "ZiNc"},
    UPS.ZOD: {"id": 75, "name": "Tapwave Zodiac"},
    UPS.ZX81: {"id": 147, "name": "Sinclair ZX-81"},
    UPS.ZXS: {"id": 46, "name": "Sinclair ZX Spectrum"},
}

# Reverse lookup: LaunchBox platform ID → UPS slug
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v["id"]: k for k, v in LAUNCHBOX_PLATFORM_LIST.items()
}


def get_platform(slug: str) -> LaunchboxPlatform:
    slug_clean = slug.strip().lower()
    resolved: UPS | None = None
    for candidate in (
        slug_clean,
        slug_clean.replace("-", ""),
        slug_clean.replace("_", ""),
        slug_clean.replace("-", "").replace("_", ""),
    ):
        if not candidate:
            continue
        try:
            ups = UPS(candidate)
        except ValueError:
            continue
        if ups in LAUNCHBOX_PLATFORM_LIST:
            resolved = ups
            break

    if resolved is None:
        return LaunchboxPlatform(slug=slug_clean, launchbox_id=None)

    platform = LAUNCHBOX_PLATFORM_LIST[resolved]

    return LaunchboxPlatform(
        slug=slug_clean,
        launchbox_id=platform["id"],
        name=platform["name"],
    )
