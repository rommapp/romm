import enum
import json
import os
import re
import unicodedata
from itertools import batched
from typing import Final

from handler.redis_handler import async_cache, sync_cache
from logger.logger import log
from tasks.update_switch_titledb import (
    SWITCH_PRODUCT_ID_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
    update_switch_titledb_task,
)


def conditionally_set_cache(
    index_key: str, filename: str, parent_dir: str = os.path.dirname(__file__)
) -> None:
    fixtures_path = os.path.join(parent_dir, "fixtures")
    if not sync_cache.exists(index_key):
        index_data = json.loads(open(os.path.join(fixtures_path, filename)).read())
        with sync_cache.pipeline() as pipe:
            for data_batch in batched(index_data.items(), 2000):
                data_map = {k: json.dumps(v) for k, v in dict(data_batch).items()}
                pipe.hset(index_key, mapping=data_map)
            pipe.execute()


# These are loaded in cache in update_switch_titledb_task
SWITCH_TITLEDB_REGEX: Final = re.compile(r"(70[0-9]{12})")
SWITCH_PRODUCT_ID_REGEX: Final = re.compile(r"(0100[0-9A-F]{12})")


# No regex needed for MAME
MAME_XML_KEY: Final = "romm:mame_xml"
conditionally_set_cache(MAME_XML_KEY, "mame_index.json")

# PS2 OPL
PS2_OPL_REGEX: Final = re.compile(r"^([A-Z]{4}_\d{3}\.\d{2})\..*$")
PS2_OPL_KEY: Final = "romm:ps2_opl_index"
conditionally_set_cache(PS2_OPL_KEY, "ps2_opl_index.json")

# Sony serial codes for PS1, PS2, and PSP
SONY_SERIAL_REGEX: Final = re.compile(r".*([a-zA-Z]{4}-\d{5}).*$")

PS1_SERIAL_INDEX_KEY: Final = "romm:ps1_serial_index"
conditionally_set_cache(PS1_SERIAL_INDEX_KEY, "ps1_serial_index.json")

PS2_SERIAL_INDEX_KEY: Final = "romm:ps2_serial_index"
conditionally_set_cache(PS2_SERIAL_INDEX_KEY, "ps2_serial_index.json")

PSP_SERIAL_INDEX_KEY: Final = "romm:psp_serial_index"
conditionally_set_cache(PSP_SERIAL_INDEX_KEY, "psp_serial_index.json")


class MetadataHandler:
    @staticmethod
    def normalize_search_term(search_term: str) -> str:
        return (
            search_term.replace("\u2122", "")  # Remove trademark symbol
            .replace("\u00ae", "")  # Remove registered symbol
            .replace("\u00a9", "")  # Remove copywrite symbol
            .replace("\u2120", "")  # Remove service mark symbol
            .strip()  # Remove leading and trailing spaces
        )

    @staticmethod
    def _normalize_cover_url(url: str) -> str:
        return url if not url else f"https:{url.replace('https:', '')}"

    # This is expensive, so it should be used sparingly
    @staticmethod
    def _normalize_exact_match(name: str) -> str:
        name = (
            name.lower()  # Convert to lower case,
            .replace("_", " ")  # Replace underscores with spaces
            .replace("'", "")  # Remove single quotes
            .replace('"', "")  # Remove double quotes
            .strip()  # Remove leading and trailing spaces
        )

        # Remove leading and trailing articles
        name = re.sub(r"^(a|an|the)\b", "", name)
        name = re.sub(r",\b(a|an|the)\b", "", name)

        # Remove special characters and punctuation
        converted_name = "".join(re.findall(r"\w+", name))

        # Convert to normal form
        normalized_name = unicodedata.normalize("NFD", converted_name)

        # Remove accents
        canonical_form = "".join(
            [c for c in normalized_name if not unicodedata.combining(c)]
        )

        return canonical_form

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
            log.warning("Fetching the Switch titleID index file...")
            await update_switch_titledb_task.run(force=True)

            if not (await async_cache.exists(SWITCH_TITLEDB_INDEX_KEY)):
                log.error("Could not fetch the Switch titleID index file")
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
            log.warning("Fetching the Switch productID index file...")
            await update_switch_titledb_task.run(force=True)

            if not (await async_cache.exists(SWITCH_PRODUCT_ID_KEY)):
                log.error("Could not fetch the Switch productID index file")
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
                    }
                    # Leave other keys unchanged
                    else values[key]
                )
            )
            for key in values
        }


class UniversalPlatformSlug(enum.StrEnum):
    _1292APVS = "1292apvs"
    _3DO = "3do"
    _3DS = "3ds"
    ABC80 = "abc80"
    ACORNARCHIMEDES = "acornarchimedes"
    ACORNELECTRON = "acornelectron"
    ADVISION = "advision"
    AIRCONSOLE = "airconsole"
    ALICE3290 = "alice3290"
    ALTAIR680 = "altair680"
    ALTAIR8800 = "altair8800"
    AMAZONALEXA = "amazonalexa"
    AMAZONFIRETV = "amazonfiretv"
    AMICO = "amico"
    AMIGA = "amiga"
    AMIGACD32 = "amigacd32"
    AMSTRADCPC = "amstradcpc"
    AMSTRADPCW = "amstradpcw"
    ANDROID = "android"
    ANTSTREAM = "antstream"
    APF = "apf"
    APPLE = "apple"
    APPLE2 = "apple2"
    APPLE2GS = "apple2gs"
    AQUARIUS = "aquarius"
    ARCADE = "arcade"
    ARCADIA = "arcadia"
    ARDUBOY = "arduboy"
    ASTRAL2000 = "astral2000"
    ASTROCADE = "astrocade"
    ATARI2600 = "atari2600"
    ATARI5200 = "atari5200"
    ATARI7800 = "atari7800"
    ATARI8BIT = "atari8bit"
    ATARIST = "atarist"
    ATARIVCS = "atarivcs"
    ATOM = "atom"
    AY38500 = "ay38500"
    AY38603 = "ay38603"
    AY38605 = "ay38605"
    AY38606 = "ay38606"
    AY38607 = "ay38607"
    AY38610 = "ay38610"
    AY38710 = "ay38710"
    AY38760 = "ay38760"
    BADA = "bada"
    BBCMICRO = "bbcmicro"
    BEOS = "beos"
    BLACKBERRY = "blackberry"
    BLACKNUT = "blacknut"
    BLURAY = "bluray"
    BREW = "brew"
    BROWSER = "browser"
    BUBBLE = "bubble"
    C128 = "c128"
    C16 = "c16"
    C16PLUS4 = "c16plus4"
    C20 = "c20"
    C64 = "c64"
    CAMPLYNX = "camplynx"
    CASIOCALC = "casiocalc"
    CDI = "cdi"
    CDTV = "cdtv"
    CHAMPION2711 = "champion2711"
    CHANNELF = "channelf"
    CLICKSTART = "clickstart"
    COCO = "coco"
    COLECOADAM = "colecoadam"
    COLECOVISION = "colecovision"
    COLOURGENIE = "colourgenie"
    COMPUCOLOR = "compucolor"
    COMPUCOLOR2 = "compucolor2"
    COMPUCORPCALC = "compucorpcalc"
    COSMAC = "cosmac"
    CPET = "cpet"
    CPLUS4 = "cplus4"
    CPM = "cpm"
    CREATIVISION = "creativision"
    CYBERVISION = "cybervision"
    DANGEROS = "dangeros"
    DEDICATEDCONSOLE = "dedicatedconsole"
    DEDICATEDHANDHELD = "dedicatedhandheld"
    DIDJ = "didj"
    DIGIBLAST = "digiblast"
    DOJA = "doja"
    DOS = "dos"
    DRAGON32 = "dragon32"
    DREAMCAST = "dreamcast"
    DSI = "dsi"
    DVD = "dvd"
    ECV = "ecv"
    EGPC = "egpc"
    ELEKTOR = "elektor"
    ENTERPRISE = "enterprise"
    EVERCADE = "evercade"
    EXELVISION = "exelvision"
    EXEN = "exen"
    EXIDYSORCERER = "exidysorcerer"
    FAMICOM = "famicom"
    FDS = "fds"
    FIREOS = "fireos"
    FM7 = "fm7"
    FMTOWNS = "fmtowns"
    FREEBOX = "freebox"
    GALAKSIJA = "galaksija"
    GAMATE = "gamate"
    GAMEANDWATCH = "gameandwatch"
    GAMECOM = "gamecom"
    GAMEGEAR = "gamegear"
    GAMESTICK = "gamestick"
    GAMEWAVE = "gamewave"
    GB = "gb"
    GBA = "gba"
    GBC = "gbc"
    GCLUSTER = "gcluster"
    GEARVR = "gearvr"
    GIMINI = "gimini"
    GIZMONDO = "gizmondo"
    GLOUD = "gloud"
    GLULX = "glulx"
    GNEX = "gnex"
    GP2X = "gp2x"
    GP2XWIZ = "gp2xwiz"
    GP32 = "gp32"
    GVM = "gvm"
    GX4000 = "gx4000"
    HDDVD = "hddvd"
    HEATHKITH11 = "heathkith11"
    HEATHZENITH = "heathzenith"
    HITACHIS1 = "hitachis1"
    HP2100 = "hp2100"
    HP3000 = "hp3000"
    HP9800 = "hp9800"
    HPCALC = "hpcalc"
    HUGO = "hugo"
    HYPERNEOGEO64 = "hyper-neo-geo-64"
    HYPERSCAN = "hyperscan"
    IBM5100 = "ibm5100"
    IDEALCOMPUTER = "idealcomputer"
    IIRCADE = "iircade"
    PDS1 = "pds1"
    INTEL8008 = "intel8008"
    INTEL8080 = "intel8080"
    INTEL8086 = "intel8086"
    INTELLIVISION = "intellivision"
    INTERACTM1 = "interactm1"
    INTERTONV2000 = "intertonv2000"
    IOS = "ios"
    IPAD = "ipad"
    IPHONE = "iphone"
    IPOD = "ipod"
    J2ME = "j2me"
    JAGUAR = "jaguar"
    JAGUARCD = "jaguarcd"
    JOLT = "jolt"
    JUPITERACE = "jupiterace"
    KAIOS = "kaios"
    KIM1 = "kim1"
    KINDLE = "kindle"
    LASER200 = "laser200"
    LASERACTIVE = "laseractive"
    LCDGAMES = "lcdgames"
    LEAPSTER = "leapster"
    LEAPSTEREXPLORER = "leapsterexplorer"
    LEAPTV = "leaptv"
    LEGACYPC = "legacypc"
    LINUX = "linux"
    LOOPY = "loopy"
    LUNA = "luna"
    LYNX = "lynx"
    MAC = "mac"
    MACINTOSH = "macintosh"
    MAEMO = "maemo"
    MAINFRAME = "mainframe"
    MATSUSHITAPANASONICJR = "matsushitapanasonicjr"
    MEEGO = "meego"
    MEGADRIVE = "megadrive"
    MEGADUCK = "megaduck"
    MEMOTECHMTX = "memotechmtx"
    MERITUM = "meritum"
    MICROBEE = "microbee"
    MICROMIND = "micromind"
    MICROTAN65 = "microtan65"
    MICROVISION = "microvision"
    MOBILE = "mobile"
    MOPHUN = "mophun"
    MOS6502 = "mos6502"
    MOTOROLA6800 = "motorola6800"
    MOTOROLA68K = "motorola68k"
    MRE = "mre"
    MSX = "msx"
    MSX2 = "msx2"
    MZ2200 = "mz2200"
    N64 = "n64"
    N64DD = "n64dd"
    NASCOM = "nascom"
    NDS = "nds"
    NEOGEOAES = "neogeoaes"
    NEOGEOCD = "neogeocd"
    NEOGEOMVS = "neogeomvs"
    NEOGEOX = "neogeox"
    NES = "nes"
    NEW3DS = "new3ds"
    NEWBRAIN = "newbrain"
    NEWTON = "newton"
    NGAGE = "ngage"
    NGAGE2 = "ngage2"
    NGC = "ngc"
    NGP = "ngp"
    NGPC = "ngpc"
    NORTHSTAR = "northstar"
    NOVAL760 = "noval760"
    NUON = "nuon"
    OCULUSGO = "oculusgo"
    OCULUSQUEST = "oculusquest"
    OCULUSRIFT = "oculusrift"
    OCULUSVR = "oculusvr"
    ODYSSEY = "odyssey"
    ODYSSEY2 = "odyssey2"
    OHIOSCI = "ohiosci"
    ONLIVE = "onlive"
    OOPARTS = "ooparts"
    ORAO = "orao"
    ORIC = "oric"
    OS2 = "os2"
    OUYA = "ouya"
    PALMOS = "palmos"
    PANASONICJUNGLE = "panasonicjungle"
    PANASONICM2 = "panasonicm2"
    PANDORA = "pandora"
    PC50 = "pc50"
    PC60 = "pc60"
    PC8000 = "pc8000"
    PC88 = "pc88"
    PC98 = "pc98"
    PCBOOTER = "pcbooter"
    PCENGINE = "pcengine"
    PCENGINECD = "pcenginecd"
    PCFX = "pcfx"
    PDP1 = "pdp1"
    PDP10 = "pdp10"
    PDP11 = "pdp11"
    PEBBLE = "pebble"
    PET = "pet"
    PHOTOCD = "photocd"
    PICO = "pico"
    PICO8 = "pico8"
    PICOBEENA = "picobeena"
    PIPPIN = "pippin"
    PLATO = "plato"
    PLAYDATE = "playdate"
    PLAYDIA = "playdia"
    PLEXARCADE = "plexarcade"
    PLUGNPLAY = "plugnplay"
    POCKETSTATION = "pocketstation"
    POKEMINI = "pokemini"
    POKITTO = "pokitto"
    POLY88 = "poly88"
    PS2 = "ps2"
    PS3 = "ps3"
    PS4 = "ps4"
    PS5 = "ps5"
    PSNOW = "psnow"
    PSP = "psp"
    PSVITA = "psvita"
    PSVR = "psvr"
    PSVR2 = "psvr2"
    PSX = "psx"
    PV1000 = "pv1000"
    QUEST2 = "quest2"
    QUEST3 = "quest3"
    RCASTUDIO2 = "rcastudio2"
    RM380Z = "rm380z"
    ROKU = "roku"
    RZONE = "rzone"
    SAMCOUPE = "samcoupe"
    SATELLAVIEW = "satellaview"
    SATURN = "saturn"
    SCMP = "scmp"
    SCV = "scv"
    SD200 = "sd200"
    SEGA32X = "sega32x"
    SEGACD = "segacd"
    SEGACD32X = "segacd32x"
    SERIESXS = "seriesxs"
    SFAM = "sfam"
    SG1000 = "sg1000"
    SGB = "sgb"
    SIGNETICS2650 = "signetics2650"
    SINCLAIRQL = "sinclairql"
    SKVM = "skvm"
    SMC777 = "smc777"
    SMS = "sms"
    SNES = "snes"
    SOCRATES = "socrates"
    SOL20 = "sol20"
    SORDM5 = "sordm5"
    SPECTRAVIDEO = "spectravideo"
    SRI500 = "sri500"
    STADIA = "stadia"
    STEAMVR = "steamvr"
    SUFAMI = "sufami"
    SUPERACAN = "superacan"
    SUPERGRAFX = "supergrafx"
    SUPERVISION = "supervision"
    SUPERVISION8000 = "supervision8000"
    SURESHOTHD = "sureshothd"
    SWANCRYSTAL = "swancrystal"
    SWITCH = "switch"
    SWITCH2 = "switch2"
    SWTPC6800 = "swtpc6800"
    SYMBIAN = "symbian"
    TADS = "tads"
    TATUNGEINSTEIN = "tatungeinstein"
    TEKTRONIX4050 = "tektronix4050"
    TELESPIEL = "telespiel"
    TELSTAR = "telstar"
    TEREBIKKO = "terebikko"
    TERMINAL = "terminal"
    THOMSONMO = "thomsonmo"
    THOMSONTO = "thomsonto"
    TI99 = "ti99"
    TIKI100 = "tiki100"
    TIM = "tim"
    TIMEX2068 = "timex2068"
    TICALC = "ticalc"
    TIZEN = "tizen"
    TOMAHAWKF1 = "tomahawkf1"
    TRITON = "triton"
    TRS80 = "trs80"
    TRS80MC10 = "trs80mc10"
    TRS80MODEL100 = "trs80model100"
    TUTOR = "tutor"
    TVOS = "tvos"
    UZEBOX = "uzebox"
    VC = "vc"
    VC4000 = "vc4000"
    VECTREX = "vectrex"
    VERSATILE = "versatile"
    VFLASH = "vflash"
    VG5000 = "vg5000"
    VIDEOBRAIN = "videobrain"
    VIDEOPACPLUS = "videopacplus"
    VIRTUALBOY = "virtualboy"
    VIS = "vis"
    VISIONOS = "visionos"
    VMU = "vmu"
    VSMILE = "vsmile"
    WANG2200 = "wang2200"
    WASM4 = "wasm4"
    WATCHOS = "watchos"
    WEBOS = "webos"
    WII = "wii"
    WIIU = "wiiu"
    WIN = "win"
    WIN3X = "win3x"
    WINDOWS = "windows"
    WINDOWSAPPS = "windowsapps"
    WINDOWSMOBILE = "windowsmobile"
    WINDOWSMX = "windowsmx"
    WINPHONE = "winphone"
    WIPI = "wipi"
    WSWAN = "wswan"
    WSWANC = "wswanc"
    X1 = "x1"
    X55 = "x55"
    X68000 = "x68000"
    XAVIXPORT = "xavixport"
    XBOX = "xbox"
    XBOX360 = "xbox360"
    XBOXCLOUDGAMING = "xboxcloudgaming"
    XBOXONE = "xboxone"
    XEROXALTO = "xerox-alto"
    Z80 = "z80"
    Z8000 = "z8000"
    ZAURUS = "zaurus"
    ZEEBO = "zeebo"
    ZMACHINE = "zmachine"
    ZOD = "zod"
    ZODIAC = "zodiac"
    ZUNE = "zune"
    ZX80 = "zx80"
    ZX81 = "zx81"
    ZXS = "zxs"
    ZXSNEXT = "zxsnext"
