import json
from typing import NotRequired, TypedDict

import httpx
from config import HASHEOUS_API_ENABLED
from fastapi import HTTPException, status
from logger.logger import log
from utils.context import ctx_httpx_client

from .base_hander import MetadataHandler


class HasheousMetadata(TypedDict):
    tosec_match: bool
    mame_arcade_match: bool
    mame_mess_match: bool
    nointro_match: bool
    redump_match: bool
    whdload_match: bool
    ra_match: bool
    fbneo_match: bool


class HasheousPlatform(TypedDict):
    slug: str
    hasheous_id: int | None
    name: NotRequired[str]
    igdb_id: NotRequired[str | None]
    tgdb_id: NotRequired[int | None]
    ra_id: NotRequired[int | None]


class HasheousRom(TypedDict):
    hasheous_id: int | None
    igdb_id: NotRequired[int | None]
    tgdb_id: NotRequired[int | None]
    ra_id: NotRequired[int | None]
    name: NotRequired[str]
    url_cover: NotRequired[str]
    hasheous_metadata: NotRequired[HasheousMetadata]


class HasheousHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = "https://hasheous.org/api/v1/Lookup"
        self.platform_endpoint = f"{self.BASE_URL}/Platforms"
        self.games_endpoint = f"{self.BASE_URL}/ByHash"

    async def _request(
        self, url: str, params: dict, data: dict, timeout: int = 120
    ) -> dict:
        httpx_client = ctx_httpx_client.get()

        try:
            log.debug(
                "API request: URL=%s, Params=%s, Data=%s, Timeout=%s",
                url,
                params,
                data,
                timeout,
            )
            print(
                f"API request: URL={url}, Params={params}, Data={data}, Timeout={timeout}"
            )
            res = await httpx_client.post(
                url,
                params=params,
                json=data,
                timeout=timeout,
                headers={"Content-Type": "application/json-patch+json"},
            )

            res.raise_for_status()
            return res.json()
        except httpx.NetworkError as exc:
            log.critical("Connection error: can't connect to Hasheous")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Hasheous, check your internet connection",
            ) from exc
        except json.decoder.JSONDecodeError as exc:
            # Log the error and return an empty list if the response is not valid JSON
            log.error(exc)
            return {}
        except httpx.TimeoutException:
            pass

        return {}

    def get_platform(self, slug: str) -> HasheousPlatform:
        platform = HASHEOUS_PLATFORM_LIST.get(slug, None)

        import ipdb

        ipdb.set_trace()

        if not platform:
            return HasheousPlatform(hasheous_id=None, slug=slug)

        return HasheousPlatform(
            hasheous_id=platform["id"],
            slug=slug,
            name=platform["name"],
            igdb_id=platform["igdb_id"],
            tgdb_id=platform["tgdb_id"],
            ra_id=platform["ra_id"],
        )

    # async def _build_platforms(self) -> None:
    #     from .igdb_handler import IGDB_PLATFORMS_BY_SLUG

    #     if not HASHEOUS_API_ENABLED:
    #         return

    #     platforms = await self._request(
    #         self.platform_endpoint,
    #         params={
    #             "PageSize": 500,
    #         },
    #     )

    #     iplats = {}
    #     mplats = {}

    #     for platform in platforms["objects"]:
    #         metadata = platform["metadata"]

    #         igdb_id = None
    #         tgdb_id = None
    #         ra_id = None

    #         for meta in metadata:
    #             if meta["source"] == "IGDB":
    #                 igdb_id = meta["id"]
    #             elif meta["source"] == "TheGamesDB":
    #                 tgdb_id = meta["immutableId"]
    #             elif meta["source"] == "RetroAchievements":
    #                 ra_id = meta["immutableId"]

    #         platform_data = {
    #             "id": platform["id"],
    #             "name": platform["name"],
    #             "igdb_id": igdb_id,
    #             "tgdb_id": int(tgdb_id) if tgdb_id else None,
    #             "ra_id": int(ra_id) if ra_id else None,
    #         }

    #         if igdb_id in IGDB_PLATFORMS_BY_SLUG:
    #             iplats[igdb_id] = platform_data
    #         else:
    #             mplats[platform["id"]] = platform_data

    async def get_rom(self, rom_attrs: dict) -> HasheousRom:
        if not HASHEOUS_API_ENABLED:
            return HasheousRom(hasheous_id=None)

        md5_hash = rom_attrs.get("md5_hash")
        sha1_hash = rom_attrs.get("sha1_hash")
        crc_hash = rom_attrs.get("crc_hash")

        if not (md5_hash or sha1_hash or crc_hash):
            log.warning(
                "No hashes provided for Hasheous lookup. "
                "At least one of md5_hash, sha1_hash, or crc_hash is required."
            )
            return HasheousRom(hasheous_id=None)

        data = {}
        if md5_hash:
            data["mD5"] = md5_hash
        if sha1_hash:
            data["shA1"] = sha1_hash
        if crc_hash:
            data["crc"] = crc_hash

        hasheous_game = await self._request(
            self.games_endpoint,
            params={
                "returnAllSources": "true",
                "returnFields": "Signatures, Metadata, Attributes",
            },
            data=data,
        )

        if not hasheous_game:
            return HasheousRom(hasheous_id=None)

        import ipdb

        ipdb.set_trace()

        metadata = hasheous_game.get("metadata", [])
        attributes = hasheous_game.get("attributes", [])
        signatures = hasheous_game.get("signatures", {}).keys()

        igdb_id = None
        tgdb_id = None
        ra_id = None

        for meta in metadata:
            if meta["source"] == "IGDB":
                igdb_id = meta["immutableId"]
            elif meta["source"] == "TheGamesDB":
                tgdb_id = meta["immutableId"]
            elif meta["source"] == "RetroAchievements":
                ra_id = meta["immutableId"]

        url_cover = ""
        for attr in attributes:
            if attr["attributeName"] == "Logo":
                url_cover = f"https://hasheous.org{attr['link']}"
                break

        return HasheousRom(
            hasheous_id=hasheous_game["id"],
            name=hasheous_game.get("name", ""),
            igdb_id=igdb_id,
            tgdb_id=int(tgdb_id) if tgdb_id else None,
            ra_id=int(ra_id) if ra_id else None,
            url_cover=url_cover,
            hasheous_metadata=HasheousMetadata(
                tosec_match="TOSEC" in signatures,
                mame_arcade_match="MAMEArcade" in signatures,
                mame_mess_match="MAMEMess" in signatures,
                nointro_match="NoIntros" in signatures,
                redump_match="Redump" in signatures,
                whdload_match="WHDLoad" in signatures,
                ra_match="RetroAchievements" in signatures,
                fbneo_match="FBNeo" in signatures,
            ),
        )


class SlugToHasheousId(TypedDict):
    id: int
    name: str
    igdb_id: str | None
    tgdb_id: int | None
    ra_id: int | None


HASHEOUS_PLATFORM_LIST: dict[str, SlugToHasheousId] = {
    "3do": {
        "id": 161825,
        "name": "3DO Interactive Multiplayer",
        "igdb_id": "3do",
        "tgdb_id": None,
        "ra_id": 43,
    },
    "3ds": {
        "id": 62,
        "name": "Nintendo 3DS",
        "igdb_id": "3ds",
        "tgdb_id": None,
        "ra_id": 62,
    },
    "64dd": {
        "id": 65,
        "name": "Nintendo 64DD",
        "igdb_id": "64dd",
        "tgdb_id": None,
        "ra_id": None,
    },
    "acorn-archimedes": {
        "id": 24,
        "name": "Acorn Archimedes",
        "igdb_id": "acorn-archimedes",
        "tgdb_id": None,
        "ra_id": None,
    },
    "acorn-electron": {
        "id": 25,
        "name": "Acorn Electron",
        "igdb_id": "acorn-electron",
        "tgdb_id": None,
        "ra_id": None,
    },
    "acpc": {
        "id": 28,
        "name": "Amstrad CPC",
        "igdb_id": "acpc",
        "tgdb_id": None,
        "ra_id": 37,
    },
    "action-max": {
        "id": 232983,
        "name": "Action Max",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "adventure-vision": {
        "id": 234388,
        "name": "Entex Adventure Vision",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "altair-8800": {
        "id": 234456,
        "name": "MITS Altair 8800",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "amiga": {
        "id": 3,
        "name": "Commodore Amiga",
        "igdb_id": "amiga",
        "tgdb_id": None,
        "ra_id": 35,
    },
    "amiga-cd32": {
        "id": 161823,
        "name": "Commodore CD32",
        "igdb_id": "amiga-cd32",
        "tgdb_id": None,
        "ra_id": None,
    },
    "amstrad-gx4000": {
        "id": 61540,
        "name": "Amstrad GX4000",
        "igdb_id": "amstrad-gx4000",
        "tgdb_id": None,
        "ra_id": None,
    },
    "amstrad-pcw": {
        "id": 29,
        "name": "Amstrad PCW",
        "igdb_id": "amstrad-pcw",
        "tgdb_id": None,
        "ra_id": None,
    },
    "apf": {
        "id": 61738,
        "name": "APF Imagination Machine",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "apple": {
        "id": 61885,
        "name": "Apple I",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "apple-iigs": {
        "id": 21,
        "name": "Apple IIGS",
        "igdb_id": "apple-iigs",
        "tgdb_id": None,
        "ra_id": None,
    },
    "apple-lisa": {
        "id": 69659,
        "name": "Apple Lisa",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "apple-pippin": {
        "id": 22,
        "name": "Apple Pippin",
        "igdb_id": "apple-pippin",
        "tgdb_id": None,
        "ra_id": None,
    },
    "apple2": {
        "id": 20,
        "name": "Apple II",
        "igdb_id": "appleii",
        "tgdb_id": None,
        "ra_id": 38,
    },
    "apple2gs": {
        "id": 21,
        "name": "Apple IIGS",
        "igdb_id": "apple-iigs",
        "tgdb_id": None,
        "ra_id": None,
    },
    "apple3": {
        "id": 63154,
        "name": "Apple III",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "appleii": {
        "id": 20,
        "name": "Apple II",
        "igdb_id": "appleii",
        "tgdb_id": None,
        "ra_id": 38,
    },
    "appleiii": {
        "id": 63154,
        "name": "Apple III",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "aquarius": {
        "id": 51,
        "name": "Mattel Aquarius",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "arcade": {
        "id": 178,
        "name": "Arcade",
        "igdb_id": "arcade",
        "tgdb_id": None,
        "ra_id": 27,
    },
    "arduboy": {
        "id": 244294,
        "name": "Arduboy",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "astrocade": {
        "id": 31,
        "name": "Bally Astrocade",
        "igdb_id": "astrocade",
        "tgdb_id": None,
        "ra_id": None,
    },
    "atari-st": {
        "id": 15,
        "name": "Atari ST/STE",
        "igdb_id": "atari-st",
        "tgdb_id": None,
        "ra_id": 36,
    },
    "atari2600": {
        "id": 12,
        "name": "Atari 2600",
        "igdb_id": "atari2600",
        "tgdb_id": None,
        "ra_id": 25,
    },
    "atari5200": {
        "id": 17,
        "name": "Atari 5200",
        "igdb_id": "atari5200",
        "tgdb_id": None,
        "ra_id": 50,
    },
    "atari7800": {
        "id": 16,
        "name": "Atari 7800",
        "igdb_id": "atari7800",
        "tgdb_id": None,
        "ra_id": 51,
    },
    "atari8bit": {
        "id": 18,
        "name": "Atari 8-bit",
        "igdb_id": "atari8bit",
        "tgdb_id": None,
        "ra_id": None,
    },
    "atom": {
        "id": 55099,
        "name": "Acorn Atom",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "bbcmicro": {
        "id": 26,
        "name": "BBC Micro",
        "igdb_id": "bbcmicro",
        "tgdb_id": None,
        "ra_id": None,
    },
    "beena": {
        "id": 82,
        "name": "Sega Advanced Pico Beena",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "bit-90": {
        "id": 97614,
        "name": "Bit Corporation BIT 90",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "c-plus-4": {
        "id": 7,
        "name": "Commodore Plus/4",
        "igdb_id": "c-plus-4",
        "tgdb_id": None,
        "ra_id": None,
    },
    "c128": {
        "id": 8,
        "name": "Commodore 128",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "c16": {
        "id": 6,
        "name": "Commodore 16",
        "igdb_id": "c16",
        "tgdb_id": None,
        "ra_id": None,
    },
    "c64": {
        "id": 5,
        "name": "Commodore MAX",
        "igdb_id": "c64",
        "tgdb_id": None,
        "ra_id": None,
    },
    "camputers-lynx": {
        "id": 97720,
        "name": "Camputers Lynx",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "casio-cfx-9850": {
        "id": 97839,
        "name": "Casio CFX-9850",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "casio-fp-1000": {
        "id": 98757,
        "name": "Casio FP-1000 & FP-1100",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "casio-loopy": {
        "id": 37,
        "name": "Casio Loopy",
        "igdb_id": "casio-loopy",
        "tgdb_id": None,
        "ra_id": None,
    },
    "casio-pb-1000": {
        "id": 98771,
        "name": "Casio PB-1000",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "casio-pv-1000": {
        "id": 98793,
        "name": "Casio PV-1000",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "casio-pv-2000": {
        "id": 98811,
        "name": "Casio PV-2000",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "colecovision": {
        "id": 39,
        "name": "ColecoVision",
        "igdb_id": "colecovision",
        "tgdb_id": None,
        "ra_id": 44,
    },
    "commander-x16": {
        "id": 54769,
        "name": "8-Bit Productions Commander X16",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "commodore-cdtv": {
        "id": 9,
        "name": "Commodore CDTV",
        "igdb_id": "commodore-cdtv",
        "tgdb_id": None,
        "ra_id": None,
    },
    "cpet": {
        "id": 10,
        "name": "Commodore PET",
        "igdb_id": "cpet",
        "tgdb_id": None,
        "ra_id": None,
    },
    "dc": {
        "id": 54694,
        "name": "Sega Dreamcast",
        "igdb_id": "dc",
        "tgdb_id": None,
        "ra_id": 40,
    },
    "dos": {
        "id": 233075,
        "name": "Microsoft DOS",
        "igdb_id": "dos",
        "tgdb_id": None,
        "ra_id": None,
    },
    "excalibur-64": {
        "id": 97612,
        "name": "BGR Computers Excalibur 64",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "fairchild-channel-f": {
        "id": 43,
        "name": "Fairchild Channel F",
        "igdb_id": "fairchild-channel-f",
        "tgdb_id": None,
        "ra_id": 57,
    },
    "fds": {
        "id": 54692,
        "name": "Nintendo Famicom Disk System",
        "igdb_id": "fds",
        "tgdb_id": None,
        "ra_id": None,
    },
    "fm-towns": {
        "id": 238902,
        "name": "Fujitsu - FM Towns",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "gamate": {
        "id": 97616,
        "name": "Bit Corporation Gamate",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "gamegear": {
        "id": 84,
        "name": "Sega Game Gear",
        "igdb_id": "gamegear",
        "tgdb_id": None,
        "ra_id": 15,
    },
    "gb": {
        "id": 70,
        "name": "Nintendo GameBoy",
        "igdb_id": "gb",
        "tgdb_id": None,
        "ra_id": 4,
    },
    "gba": {
        "id": 71,
        "name": "Nintendo Game Boy Advance",
        "igdb_id": "gba",
        "tgdb_id": None,
        "ra_id": 5,
    },
    "gbc": {
        "id": 72,
        "name": "Nintendo Game Boy Color",
        "igdb_id": "gbc",
        "tgdb_id": None,
        "ra_id": 6,
    },
    "genesis-slash-megadrive": {
        "id": 86,
        "name": "Sega Mega Drive / Genesis",
        "igdb_id": "genesis-slash-megadrive",
        "tgdb_id": None,
        "ra_id": 1,
    },
    "intellivision": {
        "id": 52,
        "name": "Mattel Intellivision",
        "igdb_id": "intellivision",
        "tgdb_id": None,
        "ra_id": 45,
    },
    "jaguar": {
        "id": 13,
        "name": "Atari Jaguar",
        "igdb_id": "jaguar",
        "tgdb_id": None,
        "ra_id": 17,
    },
    "linux": {
        "id": 233076,
        "name": "Linux",
        "igdb_id": "linux",
        "tgdb_id": None,
        "ra_id": None,
    },
    "lynx": {
        "id": 14,
        "name": "Atari Lynx",
        "igdb_id": "lynx",
        "tgdb_id": None,
        "ra_id": 13,
    },
    "mac": {
        "id": 30,
        "name": "Apple Mac",
        "igdb_id": "mac",
        "tgdb_id": None,
        "ra_id": None,
    },
    "microbee": {
        "id": 69714,
        "name": "Applied Technology MicroBee",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "msx": {"id": 53, "name": "MSX", "igdb_id": "msx", "tgdb_id": None, "ra_id": 29},
    "msx2": {
        "id": 54,
        "name": "MSX 2",
        "igdb_id": "msx2",
        "tgdb_id": None,
        "ra_id": None,
    },
    "multivision": {
        "id": 52922,
        "name": "Tsukuda Original Othello Multivision",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "n64": {
        "id": 64,
        "name": "Nintendo 64",
        "igdb_id": "n64",
        "tgdb_id": None,
        "ra_id": 2,
    },
    "nds": {
        "id": 66,
        "name": "Nintendo DS",
        "igdb_id": "nds",
        "tgdb_id": None,
        "ra_id": 18,
    },
    "nec-pc-6000-series": {
        "id": 58,
        "name": "NEC PC-6000",
        "igdb_id": "nec-pc-6000-series",
        "tgdb_id": None,
        "ra_id": None,
    },
    "neo-geo-cd": {
        "id": 161829,
        "name": "Neo Geo CD",
        "igdb_id": "neo-geo-cd",
        "tgdb_id": None,
        "ra_id": 56,
    },
    "neo-geo-pocket": {
        "id": 97,
        "name": "Neo Geo Pocket",
        "igdb_id": "neo-geo-pocket",
        "tgdb_id": None,
        "ra_id": 14,
    },
    "neo-geo-pocket-color": {
        "id": 98,
        "name": "Neo Geo Pocket Color",
        "igdb_id": "neo-geo-pocket-color",
        "tgdb_id": None,
        "ra_id": None,
    },
    "neogeoaes": {
        "id": 96,
        "name": "Neo Geo",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "nes": {
        "id": 68,
        "name": "Nintendo Entertainment System",
        "igdb_id": "nes",
        "tgdb_id": None,
        "ra_id": 7,
    },
    "new-nintendo-3ds": {
        "id": 63,
        "name": "Nintendo New 3DS",
        "igdb_id": "new-nintendo-3ds",
        "tgdb_id": None,
        "ra_id": None,
    },
    "ngc": {
        "id": 73,
        "name": "Nintendo GameCube",
        "igdb_id": "ngc",
        "tgdb_id": None,
        "ra_id": 16,
    },
    "nintendo-dsi": {
        "id": 67,
        "name": "Nintendo DSi",
        "igdb_id": "nintendo-dsi",
        "tgdb_id": None,
        "ra_id": 78,
    },
    "odyssey--1": {
        "id": 48,
        "name": "Magnavox Odyssey",
        "igdb_id": "odyssey--1",
        "tgdb_id": None,
        "ra_id": None,
    },
    "odyssey-2-slash-videopac-g7000": {
        "id": 49,
        "name": "Magnavox Odyssey 2",
        "igdb_id": "odyssey-2-slash-videopac-g7000",
        "tgdb_id": None,
        "ra_id": 23,
    },
    "pc-8800-series": {
        "id": 57,
        "name": "NEC PC-8800",
        "igdb_id": "pc-8800-series",
        "tgdb_id": None,
        "ra_id": None,
    },
    "pc-9800-series": {
        "id": 59,
        "name": "NEC PC-9000",
        "igdb_id": "pc-9800-series",
        "tgdb_id": None,
        "ra_id": None,
    },
    "pc-jr": {
        "id": 233269,
        "name": "IBM PCjr",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "philips-cd-i": {
        "id": 161827,
        "name": "Philips CD-i",
        "igdb_id": "philips-cd-i",
        "tgdb_id": None,
        "ra_id": 42,
    },
    "pocket-challenge-v2": {
        "id": 97550,
        "name": "Benesse Pocket Challenge V2",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "pocket-challenge-w": {
        "id": 97577,
        "name": "Benesse Pocket Challenge W",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "pocketstation": {
        "id": 103,
        "name": "Sony PocketStation",
        "igdb_id": "pocketstation",
        "tgdb_id": None,
        "ra_id": None,
    },
    "pokemon-mini": {
        "id": 244733,
        "name": "Nintendo Pokemon Mini",
        "igdb_id": "pokemon-mini",
        "tgdb_id": None,
        "ra_id": 24,
    },
    "ps": {
        "id": 100,
        "name": "Sony PlayStation",
        "igdb_id": "ps",
        "tgdb_id": None,
        "ra_id": 12,
    },
    "ps2": {
        "id": 101,
        "name": "Sony PlayStation 2",
        "igdb_id": "ps2",
        "tgdb_id": None,
        "ra_id": 21,
    },
    "ps3": {
        "id": 161830,
        "name": "Sony Playstation 3",
        "igdb_id": "ps3",
        "tgdb_id": None,
        "ra_id": None,
    },
    "ps4--1": {
        "id": 232986,
        "name": "Sony Playstation 4",
        "igdb_id": "ps4--1",
        "tgdb_id": None,
        "ra_id": None,
    },
    "ps5": {
        "id": 232987,
        "name": "Sony Playstation 5",
        "igdb_id": "ps5",
        "tgdb_id": None,
        "ra_id": None,
    },
    "psp": {
        "id": 161831,
        "name": "Sony Playstation Portable",
        "igdb_id": "psp",
        "tgdb_id": None,
        "ra_id": 41,
    },
    "psvita": {
        "id": 102,
        "name": "Sony PlayStation Vita",
        "igdb_id": "psvita",
        "tgdb_id": None,
        "ra_id": None,
    },
    "rca-studio-ii": {
        "id": 234745,
        "name": "RCA Studio II",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "saturn": {
        "id": 54695,
        "name": "Sega Saturn",
        "igdb_id": "saturn",
        "tgdb_id": None,
        "ra_id": 39,
    },
    "sc3000": {
        "id": 52165,
        "name": "Sega Computer 3000",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "sega-pico": {
        "id": 81,
        "name": "Sega Pico",
        "igdb_id": "sega-pico",
        "tgdb_id": None,
        "ra_id": 68,
    },
    "sega32": {
        "id": 80,
        "name": "Sega 32X",
        "igdb_id": "sega32",
        "tgdb_id": None,
        "ra_id": 10,
    },
    "segacd": {
        "id": 161828,
        "name": "Sega Mega CD / Sega CD",
        "igdb_id": "segacd",
        "tgdb_id": None,
        "ra_id": 9,
    },
    "series-x-s": {
        "id": 232984,
        "name": "Microsoft Xbox Series X",
        "igdb_id": "series-x-s",
        "tgdb_id": None,
        "ra_id": None,
    },
    "sfam": {
        "id": 233081,
        "name": "Super Famicom",
        "igdb_id": "sfam",
        "tgdb_id": None,
        "ra_id": None,
    },
    "sg1000": {
        "id": 244470,
        "name": "SG-1000",
        "igdb_id": "sg1000",
        "tgdb_id": None,
        "ra_id": 33,
    },
    "sharp-x68000": {
        "id": 90,
        "name": "Sharp X68000",
        "igdb_id": "sharp-x68000",
        "tgdb_id": None,
        "ra_id": 52,
    },
    "sinclair-ql": {
        "id": 92,
        "name": "Sinclair QL",
        "igdb_id": "sinclair-ql",
        "tgdb_id": None,
        "ra_id": None,
    },
    "sinclair-zx81": {
        "id": 94,
        "name": "Sinclair ZX81",
        "igdb_id": "sinclair-zx81",
        "tgdb_id": None,
        "ra_id": None,
    },
    "sms": {
        "id": 85,
        "name": "Sega Master System",
        "igdb_id": "sms",
        "tgdb_id": None,
        "ra_id": 11,
    },
    "snes": {
        "id": 74,
        "name": "Super Nintendo Entertainment System",
        "igdb_id": "snes",
        "tgdb_id": None,
        "ra_id": 3,
    },
    "super-vision-8000": {
        "id": 97267,
        "name": "Bandai Super Vision 8000",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "switch": {
        "id": 233067,
        "name": "Nintendo Switch",
        "igdb_id": "switch",
        "tgdb_id": None,
        "ra_id": None,
    },
    "ti-82": {
        "id": 47973,
        "name": "Texas Instruments TI-82",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "ti-83": {
        "id": 243852,
        "name": "Texas Instruments TI-83",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "trs-80": {
        "id": 105,
        "name": "Tandy/RadioShack TRS-80",
        "igdb_id": "trs-80",
        "tgdb_id": None,
        "ra_id": None,
    },
    "trs-80-color-computer": {
        "id": 106,
        "name": "Tandy/RadioShack TRS-80 Color Computer",
        "igdb_id": "trs-80-color-computer",
        "tgdb_id": None,
        "ra_id": None,
    },
    "turbografx-16-slash-pc-engine-cd": {
        "id": 247350,
        "name": "Turbografx-16/PC Engine CD",
        "igdb_id": "turbografx-16-slash-pc-engine-cd",
        "tgdb_id": None,
        "ra_id": None,
    },
    "turbografx16--1": {
        "id": 245372,
        "name": "TurboGrafx-16/PC Engine",
        "igdb_id": "turbografx16--1",
        "tgdb_id": None,
        "ra_id": 8,
    },
    "vectrex": {
        "id": 45,
        "name": "Vectrex",
        "igdb_id": "vectrex",
        "tgdb_id": None,
        "ra_id": 46,
    },
    "vic-20": {
        "id": 4,
        "name": "Commodore VIC20",
        "igdb_id": "vic-20",
        "tgdb_id": None,
        "ra_id": None,
    },
    "virtualboy": {
        "id": 75,
        "name": "Nintendo Virtual Boy",
        "igdb_id": "virtualboy",
        "tgdb_id": None,
        "ra_id": 28,
    },
    "watara-slash-quickshot-supervision": {
        "id": 244828,
        "name": "Watara Supervision",
        "igdb_id": "watara-slash-quickshot-supervision",
        "tgdb_id": None,
        "ra_id": 63,
    },
    "wii": {
        "id": 76,
        "name": "Nintendo Wii",
        "igdb_id": "wii",
        "tgdb_id": None,
        "ra_id": None,
    },
    "wiiu": {
        "id": 77,
        "name": "Nintendo WiiU",
        "igdb_id": "wiiu",
        "tgdb_id": None,
        "ra_id": None,
    },
    "win": {
        "id": 233074,
        "name": "Microsoft Windows",
        "igdb_id": "win",
        "tgdb_id": None,
        "ra_id": None,
    },
    "wonderswan": {
        "id": 34,
        "name": "Bandai WonderSwan",
        "igdb_id": "wonderswan",
        "tgdb_id": None,
        "ra_id": 53,
    },
    "wonderswan-color": {
        "id": 35,
        "name": "Bandai WonderSwan Color",
        "igdb_id": "wonderswan-color",
        "tgdb_id": None,
        "ra_id": None,
    },
    "x1": {"id": 89, "name": "Sharp X1", "igdb_id": "x1", "tgdb_id": None, "ra_id": 64},
    "xbox": {
        "id": 54696,
        "name": "Microsoft Xbox",
        "igdb_id": "xbox",
        "tgdb_id": None,
        "ra_id": None,
    },
    "xbox360": {
        "id": 54697,
        "name": "Microsoft Xbox 360",
        "igdb_id": "xbox360",
        "tgdb_id": None,
        "ra_id": None,
    },
    "xboxone": {
        "id": 161824,
        "name": "Microsoft Xbox One",
        "igdb_id": "xboxone",
        "tgdb_id": None,
        "ra_id": None,
    },
    "z88": {
        "id": 97718,
        "name": "Cambridge Computer Z88",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "zx80": {
        "id": 232985,
        "name": "Sinclair ZX80",
        "igdb_id": "",
        "tgdb_id": None,
        "ra_id": None,
    },
    "zxs": {
        "id": 93,
        "name": "Sinclair ZX Spectrum",
        "igdb_id": "zxs",
        "tgdb_id": None,
        "ra_id": None,
    },
}
