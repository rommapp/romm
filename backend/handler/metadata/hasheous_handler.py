import json
from datetime import datetime
from typing import Any, NotRequired, TypedDict

import httpx
import pydash
from fastapi import HTTPException, status

from config import DEV_MODE, HASHEOUS_API_ENABLED
from logger.logger import log
from models.rom import RomFile
from utils import get_version
from utils.context import ctx_httpx_client

from .base_handler import BaseRom, MetadataHandler
from .base_handler import UniversalPlatformSlug as UPS
from .igdb_handler import (
    IGDB_AGE_RATINGS,
    IGDBMetadata,
    IGDBMetadataPlatform,
)
from .ra_handler import RAMetadata


class HasheousMetadata(TypedDict):
    tosec_match: bool
    mame_arcade_match: bool
    mame_mess_match: bool
    nointro_match: bool
    redump_match: bool
    whdload_match: bool
    ra_match: bool
    fbneo_match: bool
    puredos_match: bool


class HasheousPlatform(TypedDict):
    slug: str
    hasheous_id: int | None
    name: NotRequired[str]
    igdb_id: NotRequired[int | None]
    tgdb_id: NotRequired[int | None]
    ra_id: NotRequired[int | None]


class HasheousRom(BaseRom):
    hasheous_id: int | None
    igdb_id: NotRequired[int | None]
    slug: NotRequired[str]
    igdb_metadata: NotRequired[IGDBMetadata]
    ra_id: NotRequired[int | None]
    ra_metadata: NotRequired[RAMetadata]
    tgdb_id: NotRequired[int | None]
    hasheous_metadata: NotRequired[HasheousMetadata]


ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG = {UPS.DC: ["cue", "bin"]}


def extract_metadata_from_igdb_rom(rom: dict[str, Any]) -> IGDBMetadata:
    return IGDBMetadata(
        {
            "youtube_video_id": (
                list(rom["videos"].values())[0]["video_id"]
                if rom.get("videos")
                else None
            ),
            "total_rating": str(round(rom.get("total_rating", 0.0), 2)),
            "aggregated_rating": str(round(rom.get("aggregated_rating", 0.0), 2)),
            "first_release_date": (
                int(
                    datetime.fromisoformat(
                        rom["first_release_date"].replace("Z", "+00:00")
                    ).timestamp()
                )
                if rom.get("first_release_date")
                else None
            ),
            "genres": pydash.map_(rom.get("genres", {}), "name"),
            "franchises": pydash.compact(
                [rom.get("franchise.name", None)]
                + pydash.map_(rom.get("franchises", {}), "name")
            ),
            "alternative_names": pydash.map_(rom.get("alternative_names", {}), "name"),
            "collections": pydash.map_(rom.get("collections", {}), "name"),
            "game_modes": pydash.map_(rom.get("game_modes", {}), "name"),
            "companies": pydash.compact(
                pydash.map_(rom.get("involved_companies", {}), "company.name")
            ),
            "platforms": [
                IGDBMetadataPlatform(igdb_id=p.get("id", ""), name=p.get("name", ""))
                for p in pydash.map_(rom.get("platforms", {}))
            ],
            "age_ratings": [
                IGDB_AGE_RATINGS[r]
                for r in pydash.map_(rom.get("age_ratings", {}), "rating_category")
                if r in IGDB_AGE_RATINGS
            ],
            "expansions": [],
            "dlcs": [],
            "ports": [],
            "remakes": [],
            "remasters": [],
            "similar_games": [],
            "expanded_games": [],
        }
    )


class HasheousHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = (
            "https://beta.hasheous.org/api/v1"
            if DEV_MODE
            else "https://hasheous.org/api/v1"
        )
        self.healthcheck_endpoint = f"{self.BASE_URL}/HealthCheck"
        self.platform_endpoint = f"{self.BASE_URL}/Lookup/Platforms"
        self.games_endpoint = f"{self.BASE_URL}/Lookup/ByHash"
        self.proxy_igdb_game_endpoint = f"{self.BASE_URL}/MetadataProxy/IGDB/Game"
        self.proxy_igdb_cover_endpoint = f"{self.BASE_URL}/MetadataProxy/IGDB/Cover"
        self.proxy_ra_game_endpoint = f"{self.BASE_URL}/MetadataProxy/RA/Game"
        self.app_api_key = (
            "UUvh9ef_CddMM4xXO1iqxl9FqEt764v33LU-UiGFc0P34odXjMP9M6MTeE4JZRxZ"
            if DEV_MODE
            else "JNoFBA-jEh4HbxuxEHM6MVzydKoAXs9eCcp2dvcg5LRCnpp312voiWmjuaIssSzS"
        )

    @classmethod
    def is_enabled(cls) -> bool:
        """Return whether this metadata handler is enabled."""
        return HASHEOUS_API_ENABLED

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        httpx_client = ctx_httpx_client.get()
        try:
            response = await httpx_client.get(self.healthcheck_endpoint)
            response.raise_for_status()
        except Exception as e:
            log.error("Error checking Hasheous API: %s", e)
            return False

        return bool(response)

    async def _request(
        self,
        url: str,
        method: str = "POST",
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict:
        httpx_client = ctx_httpx_client.get()

        # Normalize method to uppercase
        method = method.upper()
        if method not in ["GET", "POST"]:
            raise ValueError(f"Unsupported HTTP method: {method}")

        try:
            log.debug(
                "API request: Method=%s, URL=%s, Params=%s, Data=%s",
                method,
                url,
                params,
                data,
            )

            # Prepare request kwargs
            request_kwargs = {
                "url": url,
                "params": params,
                "headers": {
                    "Content-Type": "application/json-patch+json",
                    "User-Agent": f"RomM/{get_version()}",
                    "X-Client-API-Key": self.app_api_key,
                },
                "timeout": 120,
            }

            # Add method-specific parameters
            if method == "POST":
                request_kwargs["json"] = data

            res = await httpx_client.request(method, **request_kwargs)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as exc:
            # Check if its a 404 error
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                log.debug("Game not found in Hasheous API")
                return {}

            log.error(
                "Hasheous API returned an error: %s %s",
                exc.response.status_code,
                exc.response.text,
            )
            pass
        except httpx.NetworkError as exc:
            log.critical("Connection error: can't connect to Hasheous")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Hasheous, check your internet connection",
            ) from exc
        except json.decoder.JSONDecodeError as exc:
            # Log the error and return an empty dict if the response is not valid JSON
            log.error(exc)
            return {}
        except httpx.TimeoutException:
            pass

        return {}

    def get_platform(self, slug: str) -> HasheousPlatform:
        if slug not in HASHEOUS_PLATFORM_LIST:
            return HasheousPlatform(hasheous_id=None, slug=slug)

        platform = HASHEOUS_PLATFORM_LIST[UPS(slug)]
        return HasheousPlatform(
            hasheous_id=platform["id"],
            slug=slug,
            name=platform["name"],
            igdb_id=platform["igdb_id"],
            tgdb_id=platform["tgdb_id"],
            ra_id=platform["ra_id"],
        )

    async def lookup_rom(self, platform_slug: str, files: list[RomFile]) -> HasheousRom:
        fallback_rom = HasheousRom(
            hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None
        )

        if not self.is_enabled():
            return fallback_rom

        filtered_files = [
            file
            for file in files
            if file.file_size_bytes > 0
            and file.is_top_level
            and (
                UPS(platform_slug) not in ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG
                or file.file_extension
                in ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG[UPS(platform_slug)]
            )
        ]

        # Select the largest file by size, as it is most likely to be the main ROM file.
        # This increases the accuracy of metadata lookups, since the largest file is
        # expected to have the correct and complete hash values for external services.
        first_file = max(filtered_files, key=lambda f: f.file_size_bytes, default=None)
        if first_file is None:
            return fallback_rom

        md5_hash = first_file.md5_hash
        sha1_hash = first_file.sha1_hash
        crc_hash = first_file.crc_hash

        if not (md5_hash or sha1_hash or crc_hash):
            log.warning(
                "No hashes provided for Hasheous lookup. "
                "At least one of md5_hash, sha1_hash, or crc_hash is required."
            )
            return fallback_rom

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
            return fallback_rom

        metadata = hasheous_game.get("metadata", [])
        attributes = hasheous_game.get("attributes", [])
        signatures = hasheous_game.get("signatures", {}).keys()

        igdb_id = None
        tgdb_id = None
        ra_id = None

        for meta in metadata:
            if meta["source"] == "IGDB":
                try:
                    # TEMP: Hasheous is slowly replacing slugs with IDs
                    igdb_id = int(meta["immutableId"])
                except (ValueError, TypeError):
                    log.debug(
                        f"Found an IGDB slug instead of an ID: {meta['immutableId']}"
                    )
                    pass
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
            igdb_id=int(igdb_id) if igdb_id else None,
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
                puredos_match="PureDOS" in signatures,
            ),
        )

    async def get_igdb_game(self, hasheous_rom: HasheousRom) -> HasheousRom:
        if not self.is_enabled():
            return hasheous_rom

        igdb_id = hasheous_rom.get("igdb_id", None)

        if igdb_id is None:
            log.info("No IGDB ID provided for Hasheous IGDB game lookup.")
            return hasheous_rom

        igdb_game = await self._request(
            self.proxy_igdb_game_endpoint,
            params={
                "Id": igdb_id,
                "expandColumns": "age_ratings, alternative_names, collections, cover, dlcs, expanded_games, franchise, franchises, game_modes, genres, involved_companies, platforms, ports, remakes, screenshots, similar_games, videos",
            },
            method="GET",
        )

        if not igdb_game:
            log.debug(f"No Hasheous game found for IGDB ID {igdb_id}.")
            return hasheous_rom

        return HasheousRom(
            {
                **hasheous_rom,
                "slug": igdb_game.get("slug") or hasheous_rom.get("slug") or "",
                "name": igdb_game.get("name") or hasheous_rom.get("name") or "",
                "summary": igdb_game.get("summary", ""),
                "url_cover": self.normalize_cover_url(
                    pydash.get(igdb_game, "cover.url", "")
                ).replace("t_thumb", "t_1080p")
                or hasheous_rom.get("url_cover", ""),
                "url_screenshots": [
                    self.normalize_cover_url(s.get("url", "")).replace(
                        "t_thumb", "t_720p"
                    )
                    for s in pydash.get(igdb_game, "screenshots", {}).values()
                ]
                or hasheous_rom.get("url_screenshots", []),
                "igdb_metadata": extract_metadata_from_igdb_rom(igdb_game),
            }
        )

    async def get_ra_game(self, hasheous_rom: HasheousRom) -> HasheousRom:
        if not self.is_enabled():
            return hasheous_rom

        ra_id = hasheous_rom.get("ra_id", None)

        if ra_id is None:
            log.info("No RA ID provided for Hasheous RA game lookup.")
            return hasheous_rom

        ra_game = await self._request(
            self.proxy_ra_game_endpoint,
            params={"Id": ra_id},
            method="GET",
        )

        if not ra_game:
            log.debug(f"No Hasheous game found for RA ID {ra_id}.")
            return hasheous_rom

        return hasheous_rom


class SlugToHasheousId(TypedDict):
    id: int
    name: str
    igdb_id: int | None
    igdb_slug: str | None
    tgdb_id: int | None
    ra_id: int | None


HASHEOUS_PLATFORM_LIST: dict[UPS, SlugToHasheousId] = {
    UPS._3DO: {
        "id": 161825,
        "igdb_id": 50,
        "igdb_slug": "3do",
        "name": "3DO Interactive Multiplayer",
        "ra_id": 43,
        "tgdb_id": None,
    },
    UPS.N3DS: {
        "id": 62,
        "igdb_id": 37,
        "igdb_slug": "3ds",
        "name": "Nintendo 3DS",
        "ra_id": 62,
        "tgdb_id": None,
    },
    UPS.N64DD: {
        "id": 65,
        "igdb_id": 416,
        "igdb_slug": "64dd",
        "name": "Nintendo 64DD",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ACORN_ARCHIMEDES: {
        "id": 24,
        "igdb_id": 116,
        "igdb_slug": "acorn-archimedes",
        "name": "Acorn Archimedes",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ACORN_ELECTRON: {
        "id": 25,
        "igdb_id": 134,
        "igdb_slug": "acorn-electron",
        "name": "Acorn Electron",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ACPC: {
        "id": 28,
        "igdb_id": 25,
        "igdb_slug": "acpc",
        "name": "Amstrad CPC",
        "ra_id": 37,
        "tgdb_id": None,
    },
    UPS.ACTION_MAX: {
        "id": 232983,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Action Max",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ADVENTURE_VISION: {
        "id": 234388,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Entex Adventure Vision",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ALTAIR_8800: {
        "id": 234456,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "MITS Altair 8800",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.AMIGA: {
        "id": 3,
        "igdb_id": 16,
        "igdb_slug": "amiga",
        "name": "Commodore Amiga",
        "ra_id": 35,
        "tgdb_id": None,
    },
    UPS.AMIGA_CD32: {
        "id": 161823,
        "igdb_id": 114,
        "igdb_slug": "amiga-cd32",
        "name": "Commodore CD32",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.AMSTRAD_GX4000: {
        "id": 61540,
        "igdb_id": 506,
        "igdb_slug": "amstrad-gx4000",
        "name": "Amstrad GX4000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.AMSTRAD_PCW: {
        "id": 29,
        "igdb_id": 154,
        "igdb_slug": "amstrad-pcw",
        "name": "Amstrad PCW",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.APF: {
        "id": 61738,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "APF Imagination Machine",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.APPLE: {
        "id": 61885,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Apple I",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.APPLE_IIGS: {
        "id": 21,
        "igdb_id": 115,
        "igdb_slug": "apple-iigs",
        "name": "Apple IIGS",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.APPLE_LISA: {
        "id": 69659,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Apple Lisa",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.APPLE_PIPPIN: {
        "id": 22,
        "igdb_id": 476,
        "igdb_slug": "apple-pippin",
        "name": "Apple Pippin",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.APPLEII: {
        "id": 20,
        "igdb_id": 75,
        "igdb_slug": "appleii",
        "name": "Apple II",
        "ra_id": 38,
        "tgdb_id": None,
    },
    UPS.APPLEIII: {
        "id": 63154,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Apple III",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ARCADE: {
        "id": 178,
        "igdb_id": 52,
        "igdb_slug": "arcade",
        "name": "Arcade",
        "ra_id": 27,
        "tgdb_id": None,
    },
    UPS.ARDUBOY: {
        "id": 244294,
        "igdb_id": 438,
        "igdb_slug": "arduboy",
        "name": "Arduboy",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ASTROCADE: {
        "id": 31,
        "igdb_id": 91,
        "igdb_slug": "astrocade",
        "name": "Bally Astrocade",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ATARI_ST: {
        "id": 15,
        "igdb_id": 63,
        "igdb_slug": "atari-st",
        "name": "Atari ST/STE",
        "ra_id": 36,
        "tgdb_id": None,
    },
    UPS.ATARI2600: {
        "id": 12,
        "igdb_id": 59,
        "igdb_slug": "atari2600",
        "name": "Atari 2600",
        "ra_id": 25,
        "tgdb_id": None,
    },
    UPS.ATARI5200: {
        "id": 17,
        "igdb_id": 66,
        "igdb_slug": "atari5200",
        "name": "Atari 5200",
        "ra_id": 50,
        "tgdb_id": None,
    },
    UPS.ATARI7800: {
        "id": 16,
        "igdb_id": 60,
        "igdb_slug": "atari7800",
        "name": "Atari 7800",
        "ra_id": 51,
        "tgdb_id": None,
    },
    UPS.ATARI8BIT: {
        "id": 18,
        "igdb_id": 65,
        "igdb_slug": "atari8bit",
        "name": "Atari 8-bit",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ATOM: {
        "id": 55099,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Acorn Atom",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.BBCMICRO: {
        "id": 26,
        "igdb_id": 69,
        "igdb_slug": "bbcmicro",
        "name": "BBC Micro",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.BEENA: {
        "id": 82,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Sega Advanced Pico Beena",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.BIT_90: {
        "id": 97614,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Bit Corporation BIT 90",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.C_PLUS_4: {
        "id": 7,
        "igdb_id": 94,
        "igdb_slug": "c-plus-4",
        "name": "Commodore Plus/4",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.C128: {
        "id": 8,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Commodore 128",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.C16: {
        "id": 6,
        "igdb_id": 93,
        "igdb_slug": "c16",
        "name": "Commodore 16",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.C64: {
        "id": 5,
        "igdb_id": 15,
        "igdb_slug": "c64",
        "name": "Commodore MAX",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CAMPUTERS_LYNX: {
        "id": 97720,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Camputers Lynx",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CASIO_CFX_9850: {
        "id": 97839,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio CFX-9850",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CASIO_FP_1000: {
        "id": 98757,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio FP-1000 & FP-1100",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CASIO_LOOPY: {
        "id": 37,
        "igdb_id": 380,
        "igdb_slug": "casio-loopy",
        "name": "Casio Loopy",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CASIO_PB_1000: {
        "id": 98771,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio PB-1000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CASIO_PV_1000: {
        "id": 98793,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio PV-1000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CASIO_PV_2000: {
        "id": 98811,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio PV-2000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.COLECOVISION: {
        "id": 39,
        "igdb_id": 68,
        "igdb_slug": "colecovision",
        "name": "ColecoVision",
        "ra_id": 44,
        "tgdb_id": None,
    },
    UPS.COMMANDER_X16: {
        "id": 54769,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "8-Bit Productions Commander X16",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.COMMODORE_CDTV: {
        "id": 9,
        "igdb_id": 158,
        "igdb_slug": "commodore-cdtv",
        "name": "Commodore CDTV",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.CPET: {
        "id": 10,
        "igdb_id": 90,
        "igdb_slug": "cpet",
        "name": "Commodore PET",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.DC: {
        "id": 54694,
        "igdb_id": 23,
        "igdb_slug": "dc",
        "name": "Sega Dreamcast",
        "ra_id": 40,
        "tgdb_id": None,
    },
    UPS.DOS: {
        "id": 233075,
        "igdb_id": 13,
        "igdb_slug": "dos",
        "name": "Microsoft DOS",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.EXCALIBUR_64: {
        "id": 97612,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "BGR Computers Excalibur 64",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.FAIRCHILD_CHANNEL_F: {
        "id": 43,
        "igdb_id": 127,
        "igdb_slug": "fairchild-channel-f",
        "name": "Fairchild Channel F",
        "ra_id": 57,
        "tgdb_id": None,
    },
    UPS.FDS: {
        "id": 54692,
        "igdb_id": 51,
        "igdb_slug": "fds",
        "name": "Nintendo Famicom Disk System",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.FM_TOWNS: {
        "id": 238902,
        "igdb_id": 118,
        "igdb_slug": "fm-towns",
        "name": "Fujitsu - FM Towns",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.GAMATE: {
        "id": 97616,
        "igdb_id": 378,
        "igdb_slug": "gamate",
        "name": "Bit Corporation Gamate",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.GAMEGEAR: {
        "id": 84,
        "igdb_id": 35,
        "igdb_slug": "gamegear",
        "name": "Sega Game Gear",
        "ra_id": 15,
        "tgdb_id": None,
    },
    UPS.GB: {
        "id": 70,
        "igdb_id": 33,
        "igdb_slug": "gb",
        "name": "Nintendo GameBoy",
        "ra_id": 4,
        "tgdb_id": None,
    },
    UPS.GBA: {
        "id": 71,
        "igdb_id": 24,
        "igdb_slug": "gba",
        "name": "Nintendo Game Boy Advance",
        "ra_id": 5,
        "tgdb_id": None,
    },
    UPS.GBC: {
        "id": 72,
        "igdb_id": 22,
        "igdb_slug": "gbc",
        "name": "Nintendo Game Boy Color",
        "ra_id": 6,
        "tgdb_id": None,
    },
    UPS.GENESIS: {
        "id": 86,
        "igdb_id": 29,
        "igdb_slug": "genesis-slash-megadrive",
        "name": "Sega Mega Drive / Genesis",
        "ra_id": 1,
        "tgdb_id": None,
    },
    UPS.INTELLIVISION: {
        "id": 52,
        "igdb_id": 67,
        "igdb_slug": "intellivision",
        "name": "Mattel Intellivision",
        "ra_id": 45,
        "tgdb_id": None,
    },
    UPS.JAGUAR: {
        "id": 13,
        "igdb_id": 62,
        "igdb_slug": "jaguar",
        "name": "Atari Jaguar",
        "ra_id": 17,
        "tgdb_id": None,
    },
    UPS.LINUX: {
        "id": 233076,
        "igdb_id": 3,
        "igdb_slug": "linux",
        "name": "Linux",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.LYNX: {
        "id": 14,
        "igdb_id": 61,
        "igdb_slug": "lynx",
        "name": "Atari Lynx",
        "ra_id": 13,
        "tgdb_id": None,
    },
    UPS.MAC: {
        "id": 30,
        "igdb_id": 14,
        "igdb_slug": "mac",
        "name": "Apple Mac",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.AQUARIUS: {
        "id": 51,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Mattel Aquarius",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.MICROBEE: {
        "id": 69714,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Applied Technology MicroBee",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.MSX: {
        "id": 53,
        "igdb_id": 27,
        "igdb_slug": "msx",
        "name": "MSX",
        "ra_id": 29,
        "tgdb_id": None,
    },
    UPS.MSX2: {
        "id": 54,
        "igdb_id": 53,
        "igdb_slug": "msx2",
        "name": "MSX 2",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.MULTIVISION: {
        "id": 52922,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Tsukuda Original Othello Multivision",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.N64: {
        "id": 64,
        "igdb_id": 4,
        "igdb_slug": "n64",
        "name": "Nintendo 64",
        "ra_id": 2,
        "tgdb_id": None,
    },
    UPS.NDS: {
        "id": 66,
        "igdb_id": 20,
        "igdb_slug": "nds",
        "name": "Nintendo DS",
        "ra_id": 18,
        "tgdb_id": None,
    },
    UPS.NEC_PC_6000_SERIES: {
        "id": 58,
        "igdb_id": 157,
        "igdb_slug": "nec-pc-6000-series",
        "name": "NEC PC-6000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.NEO_GEO_CD: {
        "id": 161829,
        "igdb_id": 136,
        "igdb_slug": "neo-geo-cd",
        "name": "Neo Geo CD",
        "ra_id": 56,
        "tgdb_id": None,
    },
    UPS.NEO_GEO_POCKET: {
        "id": 97,
        "igdb_id": 119,
        "igdb_slug": "neo-geo-pocket",
        "name": "Neo Geo Pocket",
        "ra_id": 14,
        "tgdb_id": None,
    },
    UPS.NEO_GEO_POCKET_COLOR: {
        "id": 98,
        "igdb_id": 120,
        "igdb_slug": "neo-geo-pocket-color",
        "name": "Neo Geo Pocket Color",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.NEOGEOAES: {
        "id": 96,
        "igdb_id": 80,
        "igdb_slug": "neogeoaes",
        "name": "Neo Geo",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.NES: {
        "id": 68,
        "igdb_id": 18,
        "igdb_slug": "nes",
        "name": "Nintendo Entertainment System",
        "ra_id": 7,
        "tgdb_id": None,
    },
    UPS.NEW_NINTENDON3DS: {
        "id": 63,
        "igdb_id": 137,
        "igdb_slug": "new-nintendo-3ds",
        "name": "Nintendo New 3DS",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.NGC: {
        "id": 73,
        "igdb_id": 21,
        "igdb_slug": "ngc",
        "name": "Nintendo GameCube",
        "ra_id": 16,
        "tgdb_id": None,
    },
    UPS.NINTENDO_DSI: {
        "id": 67,
        "igdb_id": 159,
        "igdb_slug": "nintendo-dsi",
        "name": "Nintendo DSi",
        "ra_id": 78,
        "tgdb_id": None,
    },
    UPS.ODYSSEY: {
        "id": 48,
        "igdb_id": 88,
        "igdb_slug": "odyssey--1",
        "name": "Magnavox Odyssey",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ODYSSEY_2: {
        "id": 49,
        "igdb_id": 133,
        "igdb_slug": "odyssey-2-slash-videopac-g7000",
        "name": "Magnavox Odyssey 2",
        "ra_id": 23,
        "tgdb_id": None,
    },
    UPS.PC_8800_SERIES: {
        "id": 57,
        "igdb_id": 125,
        "igdb_slug": "pc-8800-series",
        "name": "NEC PC-8800",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.PC_9800_SERIES: {
        "id": 59,
        "igdb_id": 149,
        "igdb_slug": "pc-9800-series",
        "name": "NEC PC-9000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.PC_JR: {
        "id": 233269,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "IBM PCjr",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.PHILIPS_CD_I: {
        "id": 161827,
        "igdb_id": 117,
        "igdb_slug": "philips-cd-i",
        "name": "Philips CD-i",
        "ra_id": 42,
        "tgdb_id": None,
    },
    UPS.POCKET_CHALLENGE_V2: {
        "id": 97550,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Benesse Pocket Challenge V2",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.POCKET_CHALLENGE_W: {
        "id": 97577,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Benesse Pocket Challenge W",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.POCKETSTATION: {
        "id": 103,
        "igdb_id": 441,
        "igdb_slug": "pocketstation",
        "name": "Sony PocketStation",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.POKEMON_MINI: {
        "id": 244733,
        "igdb_id": 166,
        "igdb_slug": "pokemon-mini",
        "name": "Nintendo Pokemon Mini",
        "ra_id": 24,
        "tgdb_id": None,
    },
    UPS.PS2: {
        "id": 101,
        "igdb_id": 8,
        "igdb_slug": "ps2",
        "name": "Sony PlayStation 2",
        "ra_id": 21,
        "tgdb_id": None,
    },
    UPS.PS3: {
        "id": 161830,
        "igdb_id": 9,
        "igdb_slug": "ps3",
        "name": "Sony Playstation 3",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.PS4: {
        "id": 232986,
        "igdb_id": 48,
        "igdb_slug": "ps4--1",
        "name": "Sony Playstation 4",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.PS5: {
        "id": 232987,
        "igdb_id": 167,
        "igdb_slug": "ps5",
        "name": "Sony Playstation 5",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.PSP: {
        "id": 161831,
        "igdb_id": 38,
        "igdb_slug": "psp",
        "name": "Sony Playstation Portable",
        "ra_id": 41,
        "tgdb_id": None,
    },
    UPS.PSVITA: {
        "id": 102,
        "igdb_id": 46,
        "igdb_slug": "psvita",
        "name": "Sony PlayStation Vita",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.PSX: {
        "id": 100,
        "igdb_id": 7,
        "igdb_slug": "ps",
        "name": "Sony PlayStation",
        "ra_id": 12,
        "tgdb_id": None,
    },
    UPS.RCA_STUDIO_II: {
        "id": 234745,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "RCA Studio II",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.SATURN: {
        "id": 54695,
        "igdb_id": 32,
        "igdb_slug": "saturn",
        "name": "Sega Saturn",
        "ra_id": 39,
        "tgdb_id": None,
    },
    UPS.SC3000: {
        "id": 52165,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Sega Computer 3000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.SEGA_PICO: {
        "id": 81,
        "igdb_id": 339,
        "igdb_slug": "sega-pico",
        "name": "Sega Pico",
        "ra_id": 68,
        "tgdb_id": None,
    },
    UPS.SEGA32: {
        "id": 80,
        "igdb_id": 30,
        "igdb_slug": "sega32",
        "name": "Sega 32X",
        "ra_id": 10,
        "tgdb_id": None,
    },
    UPS.SEGACD: {
        "id": 161828,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Sega Mega CD / Sega CD",
        "ra_id": 9,
        "tgdb_id": None,
    },
    UPS.SERIES_X_S: {
        "id": 232984,
        "igdb_id": 169,
        "igdb_slug": "series-x-s",
        "name": "Microsoft Xbox Series X",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.SFAM: {
        "id": 233081,
        "igdb_id": 58,
        "igdb_slug": "sfam",
        "name": "Super Famicom",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.SG1000: {
        "id": 244470,
        "igdb_id": 84,
        "igdb_slug": "sg1000",
        "name": "SG-1000",
        "ra_id": 33,
        "tgdb_id": None,
    },
    UPS.SHARP_X68000: {
        "id": 90,
        "igdb_id": 121,
        "igdb_slug": "sharp-x68000",
        "name": "Sharp X68000",
        "ra_id": 52,
        "tgdb_id": None,
    },
    UPS.SINCLAIR_QL: {
        "id": 92,
        "igdb_id": 406,
        "igdb_slug": "sinclair-ql",
        "name": "Sinclair QL",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.SMS: {
        "id": 85,
        "igdb_id": 64,
        "igdb_slug": "sms",
        "name": "Sega Master System",
        "ra_id": 11,
        "tgdb_id": None,
    },
    UPS.SNES: {
        "id": 74,
        "igdb_id": 19,
        "igdb_slug": "snes",
        "name": "Super Nintendo Entertainment System",
        "ra_id": 3,
        "tgdb_id": None,
    },
    UPS.SUPER_VISION_8000: {
        "id": 97267,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Bandai Super Vision 8000",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.SWITCH: {
        "id": 233067,
        "igdb_id": 130,
        "igdb_slug": "switch",
        "name": "Nintendo Switch",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.TG16: {
        "id": 245372,
        "igdb_id": 86,
        "igdb_slug": "turbografx16--1",
        "name": "TurboGrafx-16/PC Engine",
        "ra_id": 8,
        "tgdb_id": None,
    },
    UPS.TI_82: {
        "id": 47973,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Texas Instruments TI-82",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.TI_83: {
        "id": 243852,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Texas Instruments TI-83",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.TRS_80: {
        "id": 105,
        "igdb_id": 126,
        "igdb_slug": "trs-80",
        "name": "Tandy/RadioShack TRS-80",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.TRS_80_COLOR_COMPUTER: {
        "id": 106,
        "igdb_id": 151,
        "igdb_slug": "trs-80-color-computer",
        "name": "Tandy/RadioShack TRS-80 Color Computer",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.TURBOGRAFX_CD: {
        "id": 247350,
        "igdb_id": 150,
        "igdb_slug": "turbografx-16-slash-pc-engine-cd",
        "name": "Turbografx-16/PC Engine CD",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.VECTREX: {
        "id": 45,
        "igdb_id": 70,
        "igdb_slug": "vectrex",
        "name": "Vectrex",
        "ra_id": 46,
        "tgdb_id": None,
    },
    UPS.VIC_20: {
        "id": 4,
        "igdb_id": 71,
        "igdb_slug": "vic-20",
        "name": "Commodore VIC20",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.VIRTUALBOY: {
        "id": 75,
        "igdb_id": 87,
        "igdb_slug": "virtualboy",
        "name": "Nintendo Virtual Boy",
        "ra_id": 28,
        "tgdb_id": None,
    },
    UPS.SUPERVISION: {
        "id": 244828,
        "igdb_id": 415,
        "igdb_slug": "watara-slash-quickshot-supervision",
        "name": "Watara Supervision",
        "ra_id": 63,
        "tgdb_id": None,
    },
    UPS.WII: {
        "id": 76,
        "igdb_id": 5,
        "igdb_slug": "wii",
        "name": "Nintendo Wii",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.WIIU: {
        "id": 77,
        "igdb_id": 41,
        "igdb_slug": "wiiu",
        "name": "Nintendo WiiU",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.WIN: {
        "id": 233074,
        "igdb_id": 6,
        "igdb_slug": "win",
        "name": "Microsoft Windows",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.WONDERSWAN: {
        "id": 34,
        "igdb_id": 57,
        "igdb_slug": "wonderswan",
        "name": "Bandai WonderSwan",
        "ra_id": 53,
        "tgdb_id": None,
    },
    UPS.WONDERSWAN_COLOR: {
        "id": 35,
        "igdb_id": 123,
        "igdb_slug": "wonderswan-color",
        "name": "Bandai WonderSwan Color",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.X1: {
        "id": 89,
        "igdb_id": 77,
        "igdb_slug": "x1",
        "name": "Sharp X1",
        "ra_id": 64,
        "tgdb_id": None,
    },
    UPS.XBOX: {
        "id": 54696,
        "igdb_id": 11,
        "igdb_slug": "xbox",
        "name": "Microsoft Xbox",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.XBOX360: {
        "id": 54697,
        "igdb_id": 12,
        "igdb_slug": "xbox360",
        "name": "Microsoft Xbox 360",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.XBOXONE: {
        "id": 161824,
        "igdb_id": 49,
        "igdb_slug": "xboxone",
        "name": "Microsoft Xbox One",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.Z88: {
        "id": 97718,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Cambridge Computer Z88",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ZX80: {
        "id": 232985,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Sinclair ZX80",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ZX81: {
        "id": 94,
        "igdb_id": 373,
        "igdb_slug": "sinclair-zx81",
        "name": "Sinclair ZX81",
        "ra_id": None,
        "tgdb_id": None,
    },
    UPS.ZXS: {
        "id": 93,
        "igdb_id": 26,
        "igdb_slug": "zxs",
        "name": "Sinclair ZX Spectrum",
        "ra_id": None,
        "tgdb_id": None,
    },
}
