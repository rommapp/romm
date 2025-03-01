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


UNIVERSAL_PLATFORM_SLUGS: Final = [
    "1292apvs",
    "3do",
    "3ds",
    "abc80",
    "acornarchimedes",
    "acornelectron",
    "advision",
    "airconsole",
    "alice3290",
    "altair680",
    "altair8800",
    "amazonalexa",
    "amazonfiretv",
    "amico",
    "amiga",
    "amigacd32",
    "amstradcpc",
    "amstradpcw",
    "android",
    "antstream",
    "apf",
    "apple",
    "apple2",
    "apple2gs",
    "aquarius",
    "arcade",
    "arcadia",
    "arduboy",
    "astral2000",
    "astrocade",
    "atari2600",
    "atari5200",
    "atari7800",
    "atari8bit",
    "atarist",
    "atarivcs",
    "atom",
    "ay38500",
    "ay38603",
    "ay38605",
    "ay38606",
    "ay38607",
    "ay38610",
    "ay38710",
    "ay38760",
    "bada",
    "bbcmicro",
    "beos",
    "blackberry",
    "blacknut",
    "bluray",
    "brew",
    "browser",
    "bubble",
    "c128",
    "c16",
    "c16plus4",
    "c20",
    "c64",
    "camplynx",
    "casiopc",
    "cdi",
    "cdtv",
    "champion2711",
    "channelf",
    "clickstart",
    "coco",
    "colecoadam",
    "colecovision",
    "colour-genie",
    "colourgenie",
    "compucolor",
    "compucolor2",
    "compucorppc",
    "cosmac",
    "cpet",
    "cplus4",
    "cpm",
    "creativision",
    "cybervision",
    "dangeros",
    "dedicatedconsole",
    "dedicatedhandheld",
    "didj",
    "digiblast",
    "doja",
    "dos",
    "dragon32",
    "dreamcast",
    "dsi",
    "dvd",
    "ecv",
    "egpc",
    "elektor-tv-games-computer",
    "enterprise",
    "evercade",
    "exelvision",
    "exen",
    "exidysorcerer",
    "famicom",
    "fds",
    "fireos",
    "fm7",
    "fmtowns",
    "freebox",
    "galaksija",
    "gamate",
    "gameandwatch",
    "gamecom",
    "gamegear",
    "gamestick",
    "gamewave",
    "gb",
    "gba",
    "gbc",
    "gcluster",
    "gearvr",
    "gimini",
    "gizmondo",
    "gloud",
    "glulx",
    "gnex",
    "gp2x",
    "gp2xwiz",
    "gp32",
    "gvm",
    "gx4000",
    "hddvd",
    "heathkith11",
    "heathzenith",
    "hitachis1",
    "hp2100",
    "hp3000",
    "hp9800",
    "hppc",
    "hugo",
    "hyper-neo-geo-64",
    "hyperscan",
    "ibm5100",
    "idealcomputer",
    "iircade",
    "imlac-pds1",
    "intel8008",
    "intel8080",
    "intel8086",
    "intellivision",
    "interactm1",
    "intertonv2000",
    "ios",
    "ipad",
    "iphone",
    "ipod",
    "j2me",
    "jaguar",
    "jaguarcd",
    "jolt",
    "jupiterace",
    "kaios",
    "kim1",
    "kindle",
    "laser200",
    "laseractive",
    "lcdgames",
    "leapster",
    "leapsterexplorer",
    "leaptv",
    "legacypc",
    "linux",
    "loopy",
    "luna",
    "lynx",
    "mac",
    "macintosh",
    "maemo",
    "mainframe",
    "matsushitapanasonicjr",
    "meego",
    "megadrive",
    "megaduck",
    "memotechmtx",
    "meritum",
    "microbee",
    "micromind",
    "microtan65",
    "microvision",
    "mobile",
    "mophun",
    "mos6502",
    "motorola6800",
    "motorola68k",
    "mre",
    "msx",
    "msx2",
    "mz2200",
    "n64",
    "n64dd",
    "nascom",
    "nds",
    "neogeoaes",
    "neogeocd",
    "neogeomvs",
    "neogeox",
    "nes",
    "new3ds",
    "newbrain",
    "newton",
    "ngage",
    "ngage2",
    "ngc",
    "ngp",
    "ngpc",
    "northstar",
    "noval760",
    "nuon",
    "oculusgo",
    "oculusquest",
    "oculusrift",
    "oculusvr",
    "odyssey",
    "odyssey2",
    "ohiosci",
    "onlive",
    "ooparts",
    "orao",
    "oric",
    "os2",
    "ouya",
    "palmos",
    "panasonicjungle",
    "panasonicm2",
    "pandora",
    "pc50",
    "pc60",
    "pc8000",
    "pc88",
    "pc98",
    "pcbooter",
    "pcengine",
    "pcenginecd",
    "pcfx",
    "pdp1",
    "pdp10",
    "pdp11",
    "pebble",
    "pet",
    "photocd",
    "pico",
    "pico8",
    "picobeena",
    "pippin",
    "plato",
    "playdate",
    "playdia",
    "plexarcade",
    "plugnplay",
    "pocketstation",
    "pokemini",
    "pokitto",
    "poly88",
    "ps2",
    "ps3",
    "ps4",
    "ps5",
    "psnow",
    "psp",
    "psvita",
    "psvr",
    "psvr2",
    "psx",
    "pv1000",
    "quest2",
    "quest3",
    "rcastudio2",
    "rm380z",
    "roku",
    "rzone",
    "samcoupe",
    "satellaview",
    "saturn",
    "scmp",
    "scv",
    "sd200",
    "sega32x",
    "segacd",
    "segacd32x",
    "seriesxs",
    "sfam",
    "sg1000",
    "signetics2650",
    "sinclairql",
    "skvm",
    "smc777",
    "sms",
    "snes",
    "socrates",
    "sol20",
    "sordm5",
    "spectravideo",
    "sri500",
    "stadia",
    "steamvr",
    "superacan",
    "supergrafx",
    "supervision",
    "supervision8000",
    "sureshothd",
    "swancrystal",
    "switch",
    "switch2",
    "swtpc6800",
    "symbian",
    "tads",
    "tatungeinstein",
    "tektronix4050",
    "telespiel",
    "telstar-arcade",
    "terebikko",
    "terminal",
    "thomsonmo",
    "thomsonto",
    "ti99",
    "tiki100",
    "tim",
    "timex2068",
    "tipc",
    "tizen",
    "tomahawk-f1",
    "triton",
    "trs80",
    "trs80mc10",
    "trs80model100",
    "tutor",
    "tvos",
    "uzebox",
    "vc",
    "vc4000",
    "vectrex",
    "versatile",
    "vflash",
    "vg5000",
    "videobrain",
    "videopacplus",
    "virtualboy",
    "vis",
    "visionos",
    "vmu",
    "vsmile",
    "wang2200",
    "watchos",
    "webos",
    "wii",
    "wiiu",
    "win",
    "win3x",
    "windows",
    "windowsapps",
    "windowsmobile",
    "windowsmx",
    "winphone",
    "wipi",
    "wswan",
    "wswanc",
    "x1",
    "x55",
    "x68000",
    "xavixport",
    "xbox",
    "xbox360",
    "xboxcloudgaming",
    "xboxone",
    "xerox-alto",
    "z80",
    "z8000",
    "zaurus",
    "zeebo",
    "zmachine",
    "zod",
    "zodiac",
    "zune",
    "zx80",
    "zx81",
    "zxs",
    "zxsnext",
]

OLD_SLUGS_TO_NEW_MAP = {
    "1292-advanced-programmable-video-system": "1292apvs",
    "64dd": "n64dd",
    "abc-80": "abc80",
    "acorn-archimedes": "acornarchimedes",
    "acorn-electron": "acornelectron",
    "acpc": "amstradcpc",
    "adventure-vision": "advision",
    "alice-3290": "alice3290",
    "altair-680": "altair680",
    "altair-8800": "altair8800",
    "amazon-alexa": "amazonalexa",
    "amazon-fire-tv": "amazonfiretv",
    "amiga-cd32": "amigacd32",
    "amstrad-pcw": "amstradpcw",
    "apple-i": "apple",
    "apple-iigs": "apple2gs",
    "apple-pippin": "pippin",
    "appleii": "apple2",
    "arcadia-2001": "arcadia",
    "astral-2000": "astral2000",
    "atari-2600": "atari2600",
    "atari-5200": "atari5200",
    "atari-7800": "atari7800",
    "atari-8-bit": "atari8bit",
    "atari-jaguar-cd": "jaguarcd",
    "atari-st": "atarist",
    "atari-vcs": "atarivcs",
    "ay-3-8500": "ay38500",
    "ay-3-8603": "ay38603",
    "ay-3-8605": "ay38605",
    "ay-3-8606": "ay38606",
    "ay-3-8607": "ay38607",
    "ay-3-8610": "ay38610",
    "ay-3-8710": "ay38710",
    "ay-3-8760": "ay38760",
    "bally-astrocade": "astrocade",
    "bbc-micro": "bbcmicro",
    "blu-ray-disc-player": "bluray",
    "blu-ray-player": "bluray",
    "c-plus-4": "cplus4",
    "camputers-lynx": "camplynx",
    "casio-loopy": "loopy",
    "casio-programmable-calculator": "",
    "casio-pv-1000": "",
    "cd-i": "",
    "cdccyber70": "",
    "champion-2711": "",
    "channel-f": "",
    "commodore-16-plus4": "",
    "commodore-cdtv": "",
    "compal-80": "",
    "compucolor-i": "",
    "compucolor-ii": "",
    "compucorp-programmable-calculator": "",
    "cpc": "",
    "danger-os": "",
    "dc": "",
    "dedicated-console": "",
    "dedicated-handheld": "",
    "donner30": "",
    "dragon-32-slash-64": "",
    "dragon-3264": "",
    "dvd-player": "",
    "ecd-micromind": "",
    "edsac--1": "",
    "electron": "",
    "epoch-cassette-vision": "",
    "epoch-game-pocket-computer": "",
    "epoch-super-cassette-vision": "",
    "exidy-sorcerer": "",
    "fairchild-channel-f": "",
    "fire-os": "",
    "fm-7": "",
    "fm-towns": "",
    "fred-cosmac": "",
    "g-and-w": "",
    "g-cluster": "",
    "game-com": "",
    "game-dot-com": "",
    "game-gear": "",
    "game-wave": "",
    "gameboy": "",
    "gameboy-advance": "",
    "gameboy-color": "",
    "gamecube": "",
    "gear-vr": "",
    "genesis": "",
    "genesis-slash-megadrive": "",
    "gp2x-wiz": "",
    "handheld-electronic-lcd": "",
    "hd-dvd-player": "",
    "heathkit-h11": "",
    "hitachi-s1": "",
    "hp-9800": "",
    "hp-programmable-calculator": "",
    "ibm-5100": "",
    "ideal-computer": "",
    "intel-8008": "",
    "intel-8080": "",
    "intel-8086": "",
    "intellivision-amico": "",
    "interact-model-one": "",
    "interton-video-2000": "",
    "ipod-classic": "",
    "jupiter-ace": "",
    "kim-1": "",
    "leapfrog-explorer": "",
    "leapster-explorer-slash-leadpad-explorer": "",
    "legacy-computer": "",
    "matsushitapanasonic-jr": "",
    "mattel-aquarius": "",
    "mega-duck-slash-cougar-boy": "",
    "memotech-mtx": "",
    "meta-quest-2": "",
    "meta-quest-3": "",
    "microtan-65": "",
    "microvision--1": "",
    "mobile-custom": "",
    "mos-technology-6502": "",
    "motorola-6800": "",
    "motorola-68k": "",
    "nec-pc-6000-series": "",
    "neo-geo": "",
    "neo-geo-cd": "",
    "neo-geo-pocket": "",
    "neo-geo-pocket-color": "",
    "neo-geo-x": "",
    "new-nintendo-3ds": "",
    "nimrod": "",
    "nintendo-ds": "",
    "nintendo-dsi": "",
    "nintendo-playstation": "",
    "noval-760": "",
    "oculus-go": "",
    "oculus-quest": "",
    "oculus-rift": "",
    "odyssey--1": "",
    "odyssey-2": "",
    "odyssey-2-slash-videopac-g7000": "",
    "ohio-scientific": "",
    "onlive-game-system": "",
    "palm-os": "",
    "panasonic-jungle": "",
    "panasonic-m2": "",
    "pc-50x-family": "",
    "pc-6001": "",
    "pc-8000": "",
    "pc-8800-series": "",
    "pc-9800-series": "",
    "pc-booter": "",
    "pc-fx": "",
    "pdp-8--1": "",
    "philips-cd-i": "",
    "philips-vg-5000": "",
    "plato--1": "",
    "playstation": "",
    "playstation-4": "",
    "playstation-5": "",
    "playstation-now": "",
    "plex-arcade": "",
    "plug-and-play": "",
    "pokemon-mini": "",
    "poly-88": "",
    "ps": "",
    "ps-vita": "",
    "ps4--1": "",
    "r-zone": "",
    "rca-studio-ii": "",
    "research-machines-380z": "",
    "sam-coupe": "",
    "sd-200270290": "",
    "sdssigma7": "",
    "sega-32x": "",
    "sega-cd": "",
    "sega-master-system": "",
    "sega-pico": "",
    "sega-saturn": "",
    "sega32": "",
    "series-x": "",
    "sg-1000": "",
    "sharp-mz-2200": "",
    "sharp-mz-80b20002500": "",
    "sharp-mz-80k7008001500": "",
    "sharp-x1": "",
    "sharp-x68000": "",
    "sharp-zaurus": "",
    "signetics-2650": "",
    "sinclair-ql": "",
    "sinclair-zx81": "",
    "sk-vm": "",
    "smc-777": "",
    "sol-20": "",
    "sord-m5": "",
    "sri-5001000": "",
    "super-acan": "",
    "super-vision-8000": "",
    "sure-shot-hd": "",
    "swtpc-6800": "",
    "taito-x-55": "",
    "tatung-einstein": "",
    "tektronix-4050": "",
    "tele-spiel": "",
    "terebikko-slash-see-n-say-video-phone": "",
    "thomson-mo": "",
    "thomson-mo5": "",
    "thomson-to": "",
    "ti-99": "",
    "ti-994a": "",
    "ti-programmable-calculator": "",
    "tiki-100": "",
    "timex-sinclair-2068": "",
    "tomy-tutor": "",
    "trs-80": "",
    "trs-80-coco": "",
    "trs-80-color-computer": "",
    "trs-80-mc-10": "",
    "trs-80-model-100": "",
    "turbo-grafx": "",
    "turbografx-16-slash-pc-engine-cd": "",
    "turbografx-cd": "",
    "turbografx16--1": "",
    "vc-4000": "",
    "vic-20": "",
    "videopac-g7400": "",
    "virtual-boy": "",
    "visual-memory-unit-slash-visual-memory-system": "",
    "watara-slash-quickshot-supervision": "",
    "wii-u": "",
    "windows-apps": "",
    "windows-mobile": "",
    "windows-phone": "",
    "wonderswan": "",
    "wonderswan-color": "",
    "xbox-one": "",
    "xbox-series": "",
    "z-machine": "",
    "zilog-z8000": "",
    "zx-spectrum": "",
    "zx-spectrum-next": "",
}
