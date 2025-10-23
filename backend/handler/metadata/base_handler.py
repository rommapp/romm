import abc
import enum
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from strsimpy.jaro_winkler import JaroWinkler

from handler.redis_handler import async_cache
from logger.logger import log
from tasks.scheduled.update_switch_titledb import (
    SWITCH_PRODUCT_ID_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
)

jarowinkler = JaroWinkler()


METADATA_FIXTURES_DIR: Final = Path(__file__).parent / "fixtures"

# These are loaded in cache in update_switch_titledb_task
SWITCH_TITLEDB_REGEX: Final = re.compile(r"(70[0-9]{12})")
SWITCH_PRODUCT_ID_REGEX: Final = re.compile(r"(0100[0-9A-F]{12})")


# No regex needed for MAME
MAME_XML_KEY: Final = "romm:mame_xml"

# PS2 OPL
PS2_OPL_REGEX: Final = re.compile(r"^([A-Z]{4}_\d{3}\.\d{2})\..*$")
PS2_OPL_KEY: Final = "romm:ps2_opl_index"

# Sony serial codes for PS1, PS2, PS3 and PSP
SONY_SERIAL_REGEX: Final = re.compile(r".*([a-zA-Z]{4}-\d{5}).*$")

PS1_SERIAL_INDEX_KEY: Final = "romm:ps1_serial_index"
PS2_SERIAL_INDEX_KEY: Final = "romm:ps2_serial_index"
PSP_SERIAL_INDEX_KEY: Final = "romm:psp_serial_index"

LEADING_ARTICLE_PATTERN = re.compile(r"^(a|an|the)\b", re.IGNORECASE)
COMMA_ARTICLE_PATTERN = re.compile(r",\s(a|an|the)\b(?=\s*[^\w\s]|$)", re.IGNORECASE)
NON_WORD_SPACE_PATTERN = re.compile(r"[^\w\s]")
MULTIPLE_SPACE_PATTERN = re.compile(r"\s+")


class BaseRom(TypedDict):
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    url_manual: NotRequired[str]


# This caches results to avoid repeated normalization of the same search term
@lru_cache(maxsize=1024)
def _normalize_search_term(
    name: str, remove_articles: bool = True, remove_punctuation: bool = True
) -> str:
    # Lower and replace underscores with spaces
    name = name.lower().replace("_", " ")

    # Remove articles (combined if possible)
    if remove_articles:
        name = LEADING_ARTICLE_PATTERN.sub("", name)
        name = COMMA_ARTICLE_PATTERN.sub("", name)

    # Remove punctuation and normalize spaces in one step
    if remove_punctuation:
        name = NON_WORD_SPACE_PATTERN.sub(" ", name)
        name = MULTIPLE_SPACE_PATTERN.sub(" ", name)

    # Unicode normalization and accent removal
    if any(ord(c) > 127 for c in name):  # Only if non-ASCII chars present
        normalized = unicodedata.normalize("NFD", name)
        name = "".join(c for c in normalized if not unicodedata.combining(c))

    return name.strip()


class MetadataHandler(abc.ABC):
    SEARCH_TERM_SPLIT_PATTERN = re.compile(r"[\:\-\/]")
    SEARCH_TERM_NORMALIZER = re.compile(r"\s*[:-]\s*")

    @classmethod
    @abc.abstractmethod
    def is_enabled(cls) -> bool:
        """Return whether this metadata handler is enabled."""

    def normalize_cover_url(self, url: str) -> str:
        return url if not url else f"https:{url.replace('https:', '')}"

    def normalize_search_term(
        self, name: str, remove_articles: bool = True, remove_punctuation: bool = True
    ) -> str:
        return _normalize_search_term(name, remove_articles, remove_punctuation)

    def find_best_match(
        self,
        search_term: str,
        game_names: list[str],
        min_similarity_score: float = 0.75,
        split_game_name: bool = False,
    ) -> tuple[str | None, float]:
        """
        Find the best matching game name from a list of candidates.

        Args:
            search_term: The search term to match
            game_names: List of game names to check against
            min_similarity_score: Minimum similarity score to consider a match

        Returns:
            Tuple of (best_match_name, similarity_score) or (None, 0.0) if no good match
        """
        if not game_names:
            return None, 0.0

        best_match = None
        best_score = 0.0
        search_term_normalized = self.normalize_search_term(search_term)

        for game_name in game_names:
            game_name_normalized = self.normalize_search_term(game_name)

            # If the game name is split, normalize the last term
            if split_game_name and re.search(self.SEARCH_TERM_SPLIT_PATTERN, game_name):
                game_name_normalized = self.normalize_search_term(
                    re.split(self.SEARCH_TERM_SPLIT_PATTERN, game_name)[-1]
                )

            score = jarowinkler.similarity(search_term_normalized, game_name_normalized)
            if score > best_score:
                best_score = score
                best_match = game_name

                # Early exit for perfect match
                if score == 1.0:
                    break

        if best_score >= min_similarity_score:
            return best_match, best_score

        return None, 0.0

    async def _ps2_opl_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        index_entry = await async_cache.hget(PS2_OPL_KEY, serial_code)
        if index_entry:
            index_entry = json.loads(index_entry)
            search_term = index_entry["Name"]  # type: ignore

        return search_term

    async def _sony_serial_format(self, index_key: str, serial_code: str) -> str | None:
        index_entry = await async_cache.hget(index_key, serial_code)
        if index_entry:
            index_entry = json.loads(index_entry)
            return index_entry["title"]

        return None

    async def _ps1_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(PS1_SERIAL_INDEX_KEY, serial_code)
            or search_term
        )

    async def _ps2_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(PS2_SERIAL_INDEX_KEY, serial_code)
            or search_term
        )

    async def _psp_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(PSP_SERIAL_INDEX_KEY, serial_code)
            or search_term
        )

    async def _switch_titledb_format(
        self, match: re.Match[str], search_term: str
    ) -> tuple[str, dict | None]:
        title_id = match.group(1)

        if not (await async_cache.exists(SWITCH_TITLEDB_INDEX_KEY)):
            log.error("Could not find the Switch titleID index file in cache")
            return search_term, None

        index_entry = await async_cache.hget(SWITCH_TITLEDB_INDEX_KEY, title_id)
        if index_entry:
            index_entry = json.loads(index_entry)
            return index_entry["name"], index_entry

        return search_term, None

    async def _switch_productid_format(
        self, match: re.Match[str], search_term: str
    ) -> tuple[str, dict | None]:
        product_id = match.group(1)

        # Game updates have the same product ID as the main application, except with bitmask 0x800 set
        product_id = list(product_id)
        product_id[-3] = "0"
        product_id = "".join(product_id)

        if not (await async_cache.exists(SWITCH_PRODUCT_ID_KEY)):
            log.error("Could not find the Switch productID index file in cache")
            return search_term, None

        index_entry = await async_cache.hget(SWITCH_PRODUCT_ID_KEY, product_id)
        if index_entry:
            index_entry = json.loads(index_entry)
            return index_entry["name"], index_entry

        return search_term, None

    async def _mame_format(self, search_term: str) -> str:
        from handler.filesystem import fs_rom_handler

        index_entry = await async_cache.hget(MAME_XML_KEY, search_term)
        if index_entry:
            index_entry = json.loads(index_entry)
            search_term = fs_rom_handler.get_file_name_with_no_tags(
                index_entry.get("description", search_term)
            )

        return search_term

    def _mask_sensitive_values(self, values: dict[str, str]) -> dict[str, str]:
        """
        Mask sensitive values (headers or params), leaving only the first 3 and last 3 characters of the token.
        This is valid for a dictionary with any of the following keys:
            - "Authorization" (Bearer token)
            - "Client-ID"
            - "Client-Secret"
            - "client_id"
            - "client_secret"
            - "api_key"
            - "ssid"
            - "sspassword"
            - "devid"
            - "devpassword"
            - "y" (RA API key)
        """
        return {
            key: (
                f"Bearer {values[key].split(' ')[1][:2]}***{values[key].split(' ')[1][-2:]}"
                if key == "Authorization" and values[key].startswith("Bearer ")
                else (
                    f"{values[key][:2]}***{values[key][-2:]}"
                    if key
                    in {
                        "Client-ID",
                        "Client-Secret",
                        "client_id",
                        "client_secret",
                        "api_key",
                        "ssid",
                        "sspassword",
                        "devid",
                        "devpassword",
                        "y",
                    }
                    # Leave other keys unchanged
                    else values[key]
                )
            )
            for key in values
        }


class UniversalPlatformSlug(enum.StrEnum):
    _3DO = "3do"
    ABC_80 = "abc-80"
    ACORN_ARCHIMEDES = "acorn-archimedes"
    ACORN_ELECTRON = "acorn-electron"
    ACPC = "acpc"
    ACTION_MAX = "action-max"
    ADVANCED_PICO_BEENA = "advanced-pico-beena"
    ADVENTURE_VISION = "adventure-vision"
    AIRCONSOLE = "airconsole"
    ALICE_3290 = "alice-3290"
    ALTAIR_680 = "altair-680"
    ALTAIR_8800 = "altair-8800"
    AMAZON_ALEXA = "amazon-alexa"
    AMAZON_FIRE_TV = "amazon-fire-tv"
    AMIGA = "amiga"
    AMIGA_CD = "amiga-cd"
    AMIGA_CD32 = "amiga-cd32"
    AMSTRAD_GX4000 = "amstrad-gx4000"
    AMSTRAD_PCW = "amstrad-pcw"
    ANALOGUEELECTRONICS = "analogueelectronics"
    ANDROID = "android"
    ANTSTREAM = "antstream"
    APF = "apf"
    APPLE = "apple"
    APPLE_IIGS = "apple-iigs"
    APPLE_LISA = "apple-lisa"
    APPLE_PIPPIN = "apple-pippin"
    APPLEII = "appleii"
    APPLEIII = "appleiii"
    APVS = "1292-advanced-programmable-video-system"
    AQUARIUS = "aquarius"
    ARCADE = "arcade"
    ARCADIA_2001 = "arcadia-2001"
    ARDUBOY = "arduboy"
    ASTRAL_2000 = "astral-2000"
    ASTROCADE = "astrocade"
    ATARI_JAGUAR_CD = "atari-jaguar-cd"
    ATARI_ST = "atari-st"
    ATARI_VCS = "atari-vcs"
    ATARI_XEGS = "atari-xegs"
    ATARI2600 = "atari2600"
    ATARI5200 = "atari5200"
    ATARI7800 = "atari7800"
    ATARI800 = "atari800"
    ATARI8BIT = "atari8bit"
    ATMOS = "atmos"
    ATOM = "atom"
    AY_3_8500 = "ay-3-8500"
    AY_3_8603 = "ay-3-8603"
    AY_3_8605 = "ay-3-8605"
    AY_3_8606 = "ay-3-8606"
    AY_3_8607 = "ay-3-8607"
    AY_3_8610 = "ay-3-8610"
    AY_3_8710 = "ay-3-8710"
    AY_3_8760 = "ay-3-8760"
    BADA = "bada"
    BBCMICRO = "bbcmicro"
    BEENA = "beena"
    BEOS = "beos"
    BIT_90 = "bit-90"
    BK = "bk"
    BK_01 = "bk-01"
    BLACK_POINT = "black-point"
    BLACKBERRY = "blackberry"
    BLACKNUT = "blacknut"
    BLU_RAY_PLAYER = "blu-ray-player"
    BREW = "brew"
    BROWSER = "browser"
    BUBBLE = "bubble"
    C_PLUS_4 = "c-plus-4"
    C128 = "c128"
    C16 = "c16"
    C64 = "c64"
    CALL_A_COMPUTER = "call-a-computer"
    CAMPUTERS_LYNX = "camputers-lynx"
    CASIO_CFX_9850 = "casio-cfx-9850"
    CASIO_FP_1000 = "casio-fp-1000"
    CASIO_LOOPY = "casio-loopy"
    CASIO_PB_1000 = "casio-pb-1000"
    CASIO_PROGRAMMABLE_CALCULATOR = "casio-programmable-calculator"
    CASIO_PV_1000 = "casio-pv-1000"
    CASIO_PV_2000 = "casio-pv-2000"
    CDCCYBER70 = "cdccyber70"
    CHAMPION_2711 = "champion-2711"
    CLICKSTART = "clickstart"
    COLECOADAM = "colecoadam"
    COLECOVISION = "colecovision"
    COLOUR_GENIE = "colour-genie"
    COMMANDER_X16 = "commander-x16"
    COMMODORE_CDTV = "commodore-cdtv"
    COMPAL_80 = "compal-80"
    COMPUCOLOR_I = "compucolor-i"
    COMPUCOLOR_II = "compucolor-ii"
    COMPUCORP_PROGRAMMABLE_CALCULATOR = "compucorp-programmable-calculator"
    CPET = "cpet"
    CPM = "cpm"
    CREATIVISION = "creativision"
    CYBERVISION = "cybervision"
    DANGER_OS = "danger-os"
    DAYDREAM = "daydream"
    DC = "dc"
    DEDICATED_CONSOLE = "dedicated-console"
    DEDICATED_HANDHELD = "dedicated-handheld"
    DIDJ = "didj"
    DIGIBLAST = "digiblast"
    DOJA = "doja"
    DONNER30 = "donner30"
    DOS = "dos"
    DRAGON_32_SLASH_64 = "dragon-32-slash-64"
    DVD_PLAYER = "dvd-player"
    E_READER_SLASH_CARD_E_READER = "e-reader-slash-card-e-reader"
    ECD_MICROMIND = "ecd-micromind"
    EDSAC = "edsac"
    ELEKTOR = "elektor"
    ENTERPRISE = "enterprise"
    EPOCH_CASSETTE_VISION = "epoch-cassette-vision"
    EPOCH_GAME_POCKET_COMPUTER = "epoch-game-pocket-computer"
    EPOCH_SUPER_CASSETTE_VISION = "epoch-super-cassette-vision"
    EVERCADE = "evercade"
    EXCALIBUR_64 = "excalibur-64"
    EXELVISION = "exelvision"
    EXEN = "exen"
    EXIDY_SORCERER = "exidy-sorcerer"
    FAIRCHILD_CHANNEL_F = "fairchild-channel-f"
    FAMICOM = "famicom"
    FDS = "fds"
    FM_7 = "fm-7"
    FM_TOWNS = "fm-towns"
    FRED_COSMAC = "fred-cosmac"
    FREEBOX = "freebox"
    G_AND_W = "g-and-w"
    G_CLUSTER = "g-cluster"
    GALAKSIJA = "galaksija"
    GAMATE = "gamate"
    GAME_DOT_COM = "game-dot-com"
    GAME_WAVE = "game-wave"
    GAMEGEAR = "gamegear"
    GAMESTICK = "gamestick"
    GB = "gb"
    GBA = "gba"
    GBC = "gbc"
    GEAR_VR = "gear-vr"
    GENESIS = "genesis"
    GIMINI = "gimini"
    GIZMONDO = "gizmondo"
    GLOUD = "gloud"
    GLULX = "glulx"
    GNEX = "gnex"
    GP2X = "gp2x"
    GP2X_WIZ = "gp2x-wiz"
    GP32 = "gp32"
    GT40 = "gt40"
    GVM = "gvm"
    HANDHELD_ELECTRONIC_LCD = "handheld-electronic-lcd"
    HARTUNG = "hartung"
    HD_DVD_PLAYER = "hd-dvd-player"
    HEATHKIT_H11 = "heathkit-h11"
    HEATHZENITH = "heathzenith"
    HIKARU = "hikaru"
    HITACHI_S1 = "hitachi-s1"
    HP_9800 = "hp-9800"
    HP_PROGRAMMABLE_CALCULATOR = "hp-programmable-calculator"
    HP2100 = "hp2100"
    HP3000 = "hp3000"
    HRX = "hrx"
    HUGO = "hugo"
    HYPER_NEO_GEO_64 = "hyper-neo-geo-64"
    HYPERSCAN = "hyperscan"
    IBM_5100 = "ibm-5100"
    IDEAL_COMPUTER = "ideal-computer"
    IIRCADE = "iircade"
    IMLAC_PDS1 = "imlac-pds1"
    INTEL_8008 = "intel-8008"
    INTEL_8080 = "intel-8080"
    INTEL_8086 = "intel-8086"
    INTELLIVISION = "intellivision"
    INTELLIVISION_AMICO = "intellivision-amico"
    INTERACT_MODEL_ONE = "interact-model-one"
    INTERTON_VC_4000 = "interton-vc-4000"
    INTERTON_VIDEO_2000 = "interton-video-2000"
    IOS = "ios"
    IPAD = "ipad"
    IPOD_CLASSIC = "ipod-classic"
    J2ME = "j2me"
    JAGUAR = "jaguar"
    JOLT = "jolt"
    JUPITER_ACE = "jupiter-ace"
    KAIOS = "kaios"
    KIM_1 = "kim-1"
    KINDLE = "kindle"
    LASER200 = "laser200"
    LASERACTIVE = "laseractive"
    LEAPFROG_EXPLORER = "leapfrog-explorer"
    LEAPSTER = "leapster"
    LEAPSTER_EXPLORER_SLASH_LEADPAD_EXPLORER = (
        "leapster-explorer-slash-leadpad-explorer"
    )
    LEAPTV = "leaptv"
    LEGACY_COMPUTER = "legacy-computer"
    LINUX = "linux"
    LUNA = "luna"
    LYNX = "lynx"
    MAC = "mac"
    MAEMO = "maemo"
    MAINFRAME = "mainframe"
    MATSUSHITAPANASONIC_JR = "matsushitapanasonic-jr"
    MEEGO = "meego"
    MEGA_DUCK_SLASH_COUGAR_BOY = "mega-duck-slash-cougar-boy"
    MEMOTECH_MTX = "memotech-mtx"
    MERITUM = "meritum"
    META_QUEST_2 = "meta-quest-2"
    META_QUEST_3 = "meta-quest-3"
    MICROBEE = "microbee"
    MICROCOMPUTER = "microcomputer"
    MICROTAN_65 = "microtan-65"
    MICROVISION = "microvision"
    MOBILE = "mobile"
    MOBILE_CUSTOM = "mobile-custom"
    MODEL1 = "model1"
    MODEL2 = "model2"
    MODEL3 = "model3"
    MOPHUN = "mophun"
    MOS_TECHNOLOGY_6502 = "mos-technology-6502"
    MOTOROLA_6800 = "motorola-6800"
    MOTOROLA_68K = "motorola-68k"
    MRE = "mre"
    MSX = "msx"
    MSX_TURBO = "msx-turbo"
    MSX2 = "msx2"
    MSX2PLUS = "msx2plus"
    MTX512 = "mtx512"
    MUGEN = "mugen"
    MULTIVISION = "multivision"
    N3DS = "3ds"
    N64 = "n64"
    N64DD = "64dd"
    NASCOM = "nascom"
    NDS = "nds"
    NEC_PC_6000_SERIES = "nec-pc-6000-series"
    NEO_GEO_CD = "neo-geo-cd"
    NEO_GEO_POCKET = "neo-geo-pocket"
    NEO_GEO_POCKET_COLOR = "neo-geo-pocket-color"
    NEO_GEO_X = "neo-geo-x"
    NEOGEOAES = "neogeoaes"
    NEOGEOMVS = "neogeomvs"
    NES = "nes"
    NEW_NINTENDON3DS = "new-nintendo-3ds"
    NEWBRAIN = "newbrain"
    NEWTON = "newton"
    NGAGE = "ngage"
    NGAGE2 = "ngage2"
    NGC = "ngc"
    NIMROD = "nimrod"
    NINTENDO_DSI = "nintendo-dsi"
    NORTHSTAR = "northstar"
    NOVAL_760 = "noval-760"
    NUON = "nuon"
    OCULUS_GO = "oculus-go"
    OCULUS_QUEST = "oculus-quest"
    OCULUS_RIFT = "oculus-rift"
    OCULUS_VR = "oculus-vr"
    ODYSSEY = "odyssey"
    ODYSSEY_2 = "odyssey-2"
    OHIO_SCIENTIFIC = "ohio-scientific"
    ONLIVE_GAME_SYSTEM = "onlive-game-system"
    OOPARTS = "ooparts"
    OPENBOR = "openbor"
    ORAO = "orao"
    ORIC = "oric"
    OS2 = "os2"
    OUYA = "ouya"
    PALM_OS = "palm-os"
    PALMTEX = "palmtex"
    PANASONIC_JUNGLE = "panasonic-jungle"
    PANASONIC_M2 = "panasonic-m2"
    PANDORA = "pandora"
    PC_50X_FAMILY = "pc-50x-family"
    PC_6001 = "pc-6001"
    PC_8000 = "pc-8000"
    PC_8800_SERIES = "pc-8800-series"
    PC_9800_SERIES = "pc-9800-series"
    PC_BOOTER = "pc-booter"
    PC_FX = "pc-fx"
    PC_JR = "pc-jr"
    PDP_7 = "pdp-7"
    PDP_8 = "pdp-8"
    PDP1 = "pdp1"
    PDP10 = "pdp10"
    PDP11 = "pdp11"
    PEBBLE = "pebble"
    PEGASUS = "pegasus"
    PHILIPS_CD_I = "philips-cd-i"
    PHILIPS_VG_5000 = "philips-vg-5000"
    PHOTOCD = "photocd"
    PICO = "pico"
    PINBALL = "pinball"
    PIPPIN = "pippin"
    PLATO = "plato"
    PLAYDATE = "playdate"
    PLAYDIA = "playdia"
    PLAYSTATION_NOW = "playstation-now"
    PLEX_ARCADE = "plex-arcade"
    PLUG_AND_PLAY = "plug-and-play"
    POCKET_CHALLENGE_V2 = "pocket-challenge-v2"
    POCKET_CHALLENGE_W = "pocket-challenge-w"
    POCKETSTATION = "pocketstation"
    POKEMON_MINI = "pokemon-mini"
    POKITTO = "pokitto"
    POLY_88 = "poly-88"
    POLYMEGA = "polymega"
    PS2 = "ps2"
    PS3 = "ps3"
    PS4 = "ps4"
    PS5 = "ps5"
    PSP = "psp"
    PSP_MINIS = "psp-minis"
    PSVITA = "psvita"
    PSVR = "psvr"
    PSVR2 = "psvr2"
    PSX = "psx"
    R_ZONE = "r-zone"
    RCA_STUDIO_II = "rca-studio-ii"
    RESEARCH_MACHINES_380Z = "research-machines-380z"
    ROKU = "roku"
    SAM_COUPE = "sam-coupe"
    SATELLAVIEW = "satellaview"
    SATURN = "saturn"
    SC3000 = "sc3000"
    SCMP = "scmp"
    SCUMMVM = "scummvm"
    SD_200270290 = "sd-200270290"
    SDSSIGMA7 = "sdssigma7"
    SEGA_PICO = "sega-pico"
    SEGA32 = "sega32"
    SEGACD = "segacd"
    SEGACD32 = "segacd32"
    SERIES_X_S = "series-x-s"
    SFAM = "sfam"
    SG1000 = "sg1000"
    SHARP_MZ_2200 = "sharp-mz-2200"
    SHARP_MZ_80B20002500 = "sharp-mz-80b20002500"
    SHARP_MZ_80K7008001500 = "sharp-mz-80k7008001500"
    SHARP_X68000 = "sharp-x68000"
    SHARP_ZAURUS = "sharp-zaurus"
    SIGNETICS_2650 = "signetics-2650"
    SINCLAIR_QL = "sinclair-ql"
    SK_VM = "sk-vm"
    SMC_777 = "smc-777"
    SMS = "sms"
    SNES = "snes"
    SOCRATES = "socrates"
    SOL_20 = "sol-20"
    SORD_M5 = "sord-m5"
    SPECTRAVIDEO = "spectravideo"
    SRI_5001000 = "sri-5001000"
    STADIA = "stadia"
    STEAM_VR = "steam-vr"
    STV = "stv"
    SUFAMI_TURBO = "sufami-turbo"
    SUPER_ACAN = "super-acan"
    SUPER_NES_CD_ROM_SYSTEM = "super-nes-cd-rom-system"
    SUPER_VISION_8000 = "super-vision-8000"
    SUPERGRAFX = "supergrafx"
    SUPERVISION = "supervision"
    SURE_SHOT_HD = "sure-shot-hd"
    SWANCRYSTAL = "swancrystal"
    SWITCH = "switch"
    SWITCH_2 = "switch-2"
    SWTPC_6800 = "swtpc-6800"
    SYMBIAN = "symbian"
    SYSTEM_32 = "system-32"
    SYSTEM16 = "system16"
    SYSTEM32 = "system32"
    TADS = "tads"
    TAITO_X_55 = "taito-x-55"
    TANDY_VIS = "tandy-vis"
    TATUNG_EINSTEIN = "tatung-einstein"
    TEKTRONIX_4050 = "tektronix-4050"
    TELE_SPIEL = "tele-spiel"
    TELSTAR_ARCADE = "telstar-arcade"
    TEREBIKKO_SLASH_SEE_N_SAY_VIDEO_PHONE = "terebikko-slash-see-n-say-video-phone"
    TERMINAL = "terminal"
    TG16 = "tg16"
    THOMSON_MO5 = "thomson-mo5"
    THOMSON_TO = "thomson-to"
    TI_82 = "ti-82"
    TI_83 = "ti-83"
    TI_99 = "ti-99"
    TI_994A = "ti-994a"
    TI_PROGRAMMABLE_CALCULATOR = "ti-programmable-calculator"
    TIKI_100 = "tiki-100"
    TIM = "tim"
    TIMEX_SINCLAIR_2068 = "timex-sinclair-2068"
    TIZEN = "tizen"
    TOMAHAWK_F1 = "tomahawk-f1"
    TOMY_TUTOR = "tomy-tutor"
    TOMY_TUTOR_SLASH_PYUTA_SLASH_GRANDSTAND_TUTOR = (
        "tomy-tutor-slash-pyuta-slash-grandstand-tutor"
    )
    TRITON = "triton"
    TRS_80 = "trs-80"
    TRS_80_COLOR_COMPUTER = "trs-80-color-computer"
    TRS_80_MC_10 = "trs-80-mc-10"
    TRS_80_MODEL_100 = "trs-80-model-100"
    TURBOGRAFX_CD = "turbografx-cd"
    TVOS = "tvos"
    TYPE_X = "type-x"
    UZEBOX = "uzebox"
    VC = "vc"
    VC_4000 = "vc-4000"
    VECTOR_06C = "06c"
    VECTREX = "vectrex"
    VERSATILE = "versatile"
    VFLASH = "vflash"
    VIC_20 = "vic-20"
    VIDEOBRAIN = "videobrain"
    VIDEOPAC_G7400 = "videopac-g7400"
    VIRTUALBOY = "virtualboy"
    VIS = "vis"
    VISIONOS = "visionos"
    VISUAL_MEMORY_UNIT_SLASH_VISUAL_MEMORY_SYSTEM = (
        "visual-memory-unit-slash-visual-memory-system"
    )
    VMU = "vmu"
    VSMILE = "vsmile"
    WANG2200 = "wang2200"
    WASM_4 = "wasm-4"
    WATCHOS = "watchos"
    WEBOS = "webos"
    WII = "wii"
    WIIU = "wiiu"
    WIN = "win"
    WIN3X = "win3x"
    WINDOWS_APPS = "windows-apps"
    WINDOWS_MIXED_REALITY = "windows-mixed-reality"
    WINDOWS_MOBILE = "windows-mobile"
    WINPHONE = "winphone"
    WIPI = "wipi"
    WONDERSWAN = "wonderswan"
    WONDERSWAN_COLOR = "wonderswan-color"
    X1 = "x1"
    XAVIXPORT = "xavixport"
    XBOX = "xbox"
    XBOX360 = "xbox360"
    XBOXCLOUDGAMING = "xboxcloudgaming"
    XBOXONE = "xboxone"
    XEROX_ALTO = "xerox-alto"
    Z_MACHINE = "z-machine"
    Z80 = "z80"
    Z88 = "z88"
    ZEEBO = "zeebo"
    ZILOG_Z8000 = "zilog-z8000"
    ZINC = "zinc"
    ZOD = "zod"
    ZODIAC = "zodiac"
    ZUNE = "zune"
    ZX_SPECTRUM_NEXT = "zx-spectrum-next"
    ZX80 = "zx80"
    ZX81 = "zx81"
    ZXS = "zxs"
