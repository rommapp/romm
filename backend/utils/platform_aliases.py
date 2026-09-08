from __future__ import annotations

from typing import TYPE_CHECKING, Final

from utils.platform_slugs import UniversalPlatformSlug as UPS

if TYPE_CHECKING:
    from config.config_manager import Config

# Folder names used by Batocera, RetroBat and ES-DE that differ from RomM slugs.
PLATFORM_FS_ALIASES: Final[dict[str, UPS]] = {
    "adam": UPS.COLECOADAM,
    "advision": UPS.ADVENTURE_VISION,
    "amiga1200": UPS.AMIGA,
    "amiga4000": UPS.AMIGA,
    "amiga500": UPS.AMIGA,
    "amiga600": UPS.AMIGA,
    "amigacd32": UPS.AMIGA_CD32,
    "amigacdtv": UPS.AMIGA_CD32,
    "amstradcpc": UPS.ACPC,
    "apfm1000": UPS.APF,
    "apple2": UPS.APPLEII,
    "apple2gs": UPS.APPLE_IIGS,
    "arcadia": UPS.ARCADIA_2001,
    "archimedes": UPS.ACORN_ARCHIMEDES,
    "astrocde": UPS.ASTROCADE,
    "atarijaguar": UPS.JAGUAR,
    "atarijaguarcd": UPS.ATARI_JAGUAR_CD,
    "atarilynx": UPS.LYNX,
    "atarist": UPS.ATARI_ST,
    "atarixe": UPS.ATARI_XEGS,
    "atomiswave": UPS.ARCADE,
    "bbc": UPS.BBCMICRO,
    "c20": UPS.VIC_20,
    "camplynx": UPS.CAMPUTERS_LYNX,
    "cdi": UPS.PHILIPS_CD_I,
    "cdimono1": UPS.PHILIPS_CD_I,
    "cdtv": UPS.COMMODORE_CDTV,
    "channelf": UPS.FAIRCHILD_CHANNEL_F,
    "coco": UPS.TRS_80_COLOR_COMPUTER,
    "consolearcade": UPS.ARCADE,
    "cplus4": UPS.C_PLUS_4,
    "cps": UPS.ARCADE,
    "crvision": UPS.CREATIVISION,
    "dragon32": UPS.DRAGON_32_SLASH_64,
    "dreamcast": UPS.DC,
    "easyrpg": UPS.RPG_MAKER,
    "electron": UPS.ACORN_ELECTRON,
    "fba": UPS.ARCADE,
    "fbneo": UPS.ARCADE,
    "flash": UPS.BROWSER,
    "fm7": UPS.FM_7,
    "fmtowns": UPS.FM_TOWNS,
    "gameandwatch": UPS.G_AND_W,
    "gamecom": UPS.GAME_DOT_COM,
    "gamecube": UPS.NGC,
    "gamepock": UPS.EPOCH_GAME_POCKET_COMPUTER,
    "gb2players": UPS.GB,
    "gba2players": UPS.GBA,
    "gbc2players": UPS.GBC,
    "gc": UPS.NGC,
    "gmaster": UPS.HARTUNG,
    "gx4000": UPS.AMSTRAD_GX4000,
    "gzdoom": UPS.DOOM,
    "jaguarcd": UPS.ATARI_JAGUAR_CD,
    "lcdgames": UPS.HANDHELD_ELECTRONIC_LCD,
    "lindbergh": UPS.MODEL2,
    "macintosh": UPS.MAC,
    "mame": UPS.ARCADE,
    "mame-advmame": UPS.ARCADE,
    "mark3": UPS.SMS,
    "mastersystem": UPS.SMS,
    "megacd": UPS.SEGACD,
    "megacdjp": UPS.SEGACD,
    "megadrive": UPS.GENESIS,
    "megadrive-msu": UPS.GENESIS,
    "megadrivejp": UPS.GENESIS,
    "megaduck": UPS.MEGA_DUCK_SLASH_COUGAR_BOY,
    "msu-md": UPS.GENESIS,
    "msx1": UPS.MSX,
    "msx2+": UPS.MSX2PLUS,
    "msxturbor": UPS.MSX_TURBO,
    "mz2500": UPS.SHARP_MZ_80B20002500,
    "mz700": UPS.SHARP_MZ_80K7008001500,
    "mz800": UPS.SHARP_MZ_80K7008001500,
    "mz80k": UPS.SHARP_MZ_80K7008001500,
    "n3ds": UPS.N3DS,
    "n64dd": UPS.N64DD,
    "namco22": UPS.ARCADE,
    "namco2x6": UPS.ARCADE,
    "naomi": UPS.ARCADE,
    "naomi2": UPS.ARCADE,
    "naomigd": UPS.ARCADE,
    "neogeo": UPS.NEOGEOAES,
    "neogeocd": UPS.NEO_GEO_CD,
    "ngp": UPS.NEO_GEO_POCKET,
    "ngpc": UPS.NEO_GEO_POCKET_COLOR,
    "odyssey2": UPS.ODYSSEY_2,
    "oricatmos": UPS.ATMOS,
    "palm": UPS.PALM_OS,
    "pc": UPS.WIN,
    "pc88": UPS.PC_8800_SERIES,
    "pc98": UPS.PC_9800_SERIES,
    "pcengine": UPS.TG16,
    "pcenginecd": UPS.TURBOGRAFX_CD,
    "pcfx": UPS.PC_FX,
    "pcw": UPS.AMSTRAD_PCW,
    "pet": UPS.CPET,
    "plugnplay": UPS.PLUG_AND_PLAY,
    "pokemini": UPS.POKEMON_MINI,
    "prboom": UPS.DOOM,
    "ps": UPS.PSX,
    "ps3-psn": UPS.PS3,
    "pspminis": UPS.PSP_MINIS,
    "pv1000": UPS.CASIO_PV_1000,
    "samcoupe": UPS.SAM_COUPE,
    "scv": UPS.EPOCH_SUPER_CASSETTE_VISION,
    "sega32x": UPS.SEGA32,
    "segastv": UPS.STV,
    "sfc": UPS.SFAM,
    "sg-1000": UPS.SG1000,
    "sgb": UPS.GBC,
    "sgb-msu1": UPS.GBC,
    "snes-msu1": UPS.SNES,
    "sufami": UPS.SUFAMI_TURBO,
    "supracan": UPS.SUPER_ACAN,
    "tg-cd": UPS.TURBOGRAFX_CD,
    "thomson": UPS.THOMSON_MO5,
    "ti99": UPS.TI_99,
    "tic80": UPS.TIC_80,
    "triforce": UPS.ARCADE,
    "tutor": UPS.TOMY_TUTOR,
    "vc4000": UPS.VC_4000,
    "vic20": UPS.VIC_20,
    "videopac": UPS.VIDEOPAC_G7400,
    "videopacplus": UPS.VIDEOPAC_G7400,
    "vpinball": UPS.PINBALL,
    "wasm4": UPS.WASM_4,
    "wiiware": UPS.WII,
    "windows": UPS.WIN,
    "windows3x": UPS.WIN3X,
    "windows9x": UPS.WIN9X,
    "wonderswancolor": UPS.WONDERSWAN_COLOR,
    "wswan": UPS.WONDERSWAN,
    "wswanc": UPS.WONDERSWAN_COLOR,
    "x68000": UPS.SHARP_X68000,
    "xegs": UPS.ATARI_XEGS,
    "zmachine": UPS.Z_MACHINE,
    "zxspectrum": UPS.ZXS,
}


def _unambiguous_folders() -> dict[str, str]:
    folders_by_slug: dict[UPS, list[str]] = {}
    for fs_slug, slug in PLATFORM_FS_ALIASES.items():
        folders_by_slug.setdefault(slug, []).append(fs_slug)

    return {
        slug.value: folders[0]
        for slug, folders in folders_by_slug.items()
        if len(folders) == 1
    }


# Only a slug reached by exactly one folder name can be resolved back to it.
PLATFORM_SLUG_FOLDERS: Final[dict[str, str]] = _unambiguous_folders()


def resolve_platform_slug(fs_slug: str, config: Config) -> str:
    """Resolve a platform folder name to a RomM platform slug."""
    key = fs_slug.lower()
    bound = config.PLATFORMS_BINDING.get(key) or config.PLATFORMS_VERSIONS.get(key)
    if bound:
        return bound
    if key in UPS:
        return key
    alias = PLATFORM_FS_ALIASES.get(key)
    return alias.value if alias else fs_slug


def resolve_fs_slug(slug: str, config: Config) -> str | None:
    """Resolve a RomM platform slug back to the folder name it came from.

    Returns:
        The folder name, or None when no folder maps to the slug or several
        alias folders collapse onto it.
    """
    for mapping in (config.PLATFORMS_BINDING, config.PLATFORMS_VERSIONS):
        for fs_slug, bound in mapping.items():
            if bound == slug:
                return fs_slug
    return PLATFORM_SLUG_FOLDERS.get(slug)
