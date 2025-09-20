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
from .giantbomb_handler import GiantBombMetadata
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


class HasheousPlatform(TypedDict):
    slug: str
    hasheous_id: int | None
    name: NotRequired[str]
    igdb_id: NotRequired[int | None]
    tgdb_id: NotRequired[int | None]
    ra_id: NotRequired[int | None]
    giantbomb_id: NotRequired[int | None]


class HasheousRom(BaseRom):
    hasheous_id: int | None
    igdb_id: NotRequired[int | None]
    slug: NotRequired[str]
    igdb_metadata: NotRequired[IGDBMetadata]
    ra_id: NotRequired[int | None]
    ra_metadata: NotRequired[RAMetadata]
    tgdb_id: NotRequired[int | None]
    giantbomb_id: NotRequired[int | None]
    giantbomb_metadata: NotRequired[GiantBombMetadata]
    hasheous_metadata: NotRequired[HasheousMetadata]


ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG = {"dc": ["cue"]}


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

            # Make the request
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
            if file.file_size_bytes is not None
            and file.file_size_bytes > 0
            and (
                file.file_extension
                in ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG[platform_slug]
                if platform_slug in ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG
                else True
            )
        ]

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
    giantbomb_id: int | None
    giantbomb_slug: str | None


HASHEOUS_PLATFORM_LIST: dict[UPS, SlugToHasheousId] = {
    UPS._3DO: {
        "id": 161825,
        "igdb_id": 50,
        "igdb_slug": "3do",
        "name": "3DO Interactive Multiplayer",
        "ra_id": 43,
        "tgdb_id": 25,
        "giantbomb_id": 26,
        "giantbomb_slug": "3do",
    },
    UPS.N3DS: {
        "id": 62,
        "igdb_id": 37,
        "igdb_slug": "3ds",
        "name": "Nintendo 3DS",
        "ra_id": 62,
        "tgdb_id": 4912,
        "giantbomb_id": 117,
        "giantbomb_slug": "nintendo-3ds",
    },
    UPS.N64DD: {
        "id": 65,
        "igdb_id": 416,
        "igdb_slug": "64dd",
        "name": "Nintendo 64DD",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 101,
        "giantbomb_slug": "nintendo-64dd",
    },
    UPS.APF: {
        "id": 61862,
        "igdb_id": None,
        "igdb_slug": None,
        "name": "APF M-1000",
        "ra_id": None,
        "tgdb_id": 4969,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.C64: {
        "id": 1,
        "igdb_id": 15,
        "igdb_slug": None,
        "name": "Commodore 64",
        "ra_id": 30,
        "tgdb_id": 40,
        "giantbomb_id": 14,
        "giantbomb_slug": None,
    },
    UPS.ARCADIA_2001: {
        "id": 322291,
        "igdb_id": None,
        "igdb_slug": None,
        "name": "Emerson Arcadia 2001",
        "ra_id": None,
        "tgdb_id": 4963,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 299046,
        "igdb_id": 376,
        "igdb_slug": None,
        "name": "Epoch Super Cassette Vision",
        "ra_id": None,
        "tgdb_id": 4966,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.EXIDY_SORCERER: {
        "id": 299154,
        "igdb_id": 236,
        "igdb_slug": None,
        "name": "Exidy Sorcerer",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.FDS: {
        "id": 69,
        "igdb_id": 51,
        "igdb_slug": None,
        "name": "Family Computer Disk System",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 91,
        "giantbomb_slug": None,
    },
    UPS.MEMOTECH_MTX: {
        "id": 338636,
        "igdb_id": None,
        "igdb_slug": None,
        "name": "Memotech MTX",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 206,
        "giantbomb_slug": None,
    },
    UPS.G_AND_W: {
        "id": 273860,
        "igdb_id": 307,
        "igdb_slug": None,
        "name": "Nintendo Game & Watch",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.PC_8800_SERIES: {
        "id": 311550,
        "igdb_id": None,
        "igdb_slug": None,
        "name": "PC-8000/8800",
        "ra_id": 47,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.LASERACTIVE: {
        "id": 261429,
        "igdb_id": None,
        "igdb_slug": None,
        "name": "Pioneer LaserActive",
        "ra_id": None,
        "tgdb_id": 4975,
        "giantbomb_id": 92,
        "giantbomb_slug": None,
    },
    UPS.SG1000: {
        "id": 83,
        "igdb_id": 84,
        "igdb_slug": None,
        "name": "Sega SG-1000",
        "ra_id": 33,
        "tgdb_id": 4949,
        "giantbomb_id": 141,
        "giantbomb_slug": None,
    },
    UPS.SORD_M5: {
        "id": 279962,
        "igdb_id": None,
        "igdb_slug": None,
        "name": "Sord M5",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 193,
        "giantbomb_slug": None,
    },
    UPS.ACORN_ARCHIMEDES: {
        "id": 24,
        "igdb_id": 116,
        "igdb_slug": "acorn-archimedes",
        "name": "Acorn Archimedes",
        "ra_id": None,
        "tgdb_id": 4944,
        "giantbomb_id": 125,
        "giantbomb_slug": "acorn-archimedes",
    },
    UPS.ACORN_ELECTRON: {
        "id": 25,
        "igdb_id": 134,
        "igdb_slug": "acorn-electron",
        "name": "Acorn Electron",
        "ra_id": None,
        "tgdb_id": 4954,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.ACPC: {
        "id": 28,
        "igdb_id": 25,
        "igdb_slug": "acpc",
        "name": "Amstrad CPC",
        "ra_id": 37,
        "tgdb_id": 4914,
        "giantbomb_id": 11,
        "giantbomb_slug": "amstrad-cpc",
    },
    UPS.ACTION_MAX: {
        "id": 232983,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Action Max",
        "ra_id": None,
        "tgdb_id": 4976,
        "giantbomb_id": 148,
        "giantbomb_slug": "action-max",
    },
    UPS.ADVENTURE_VISION: {
        "id": 234388,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Entex Adventure Vision",
        "ra_id": None,
        "tgdb_id": 4974,
        "giantbomb_id": 93,
        "giantbomb_slug": "adventure-vision",
    },
    UPS.ALTAIR_8800: {
        "id": 234456,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "MITS Altair 8800",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.AMIGA: {
        "id": 3,
        "igdb_id": 16,
        "igdb_slug": "amiga",
        "name": "Commodore Amiga",
        "ra_id": 35,
        "tgdb_id": 4911,
        "giantbomb_id": 1,
        "giantbomb_slug": "amiga",
    },
    UPS.AMIGA_CD32: {
        "id": 161823,
        "igdb_id": 114,
        "igdb_slug": "amiga-cd32",
        "name": "Commodore CD32",
        "ra_id": None,
        "tgdb_id": 4947,
        "giantbomb_id": 39,
        "giantbomb_slug": "amiga-cd32",
    },
    UPS.AMSTRAD_GX4000: {
        "id": 61540,
        "igdb_id": 506,
        "igdb_slug": "amstrad-gx4000",
        "name": "Amstrad GX4000",
        "ra_id": None,
        "tgdb_id": 4999,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.AMSTRAD_PCW: {
        "id": 29,
        "igdb_id": 154,
        "igdb_slug": "amstrad-pcw",
        "name": "Amstrad PCW",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 197,
        "giantbomb_slug": "amstrad-pcw",
    },
    UPS.APF: {
        "id": 61738,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "APF Imagination Machine",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 190,
        "giantbomb_slug": "apf-mp-1000",
    },
    UPS.APPLE: {
        "id": 61885,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Apple I",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.APPLE_IIGS: {
        "id": 21,
        "igdb_id": 115,
        "igdb_slug": "apple-iigs",
        "name": "Apple IIGS",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 38,
        "giantbomb_slug": "apple-iigs",
    },
    UPS.APPLE_LISA: {
        "id": 69659,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Apple Lisa",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.APPLE_PIPPIN: {
        "id": 22,
        "igdb_id": 476,
        "igdb_slug": "apple-pippin",
        "name": "Apple Pippin",
        "ra_id": None,
        "tgdb_id": 5001,
        "giantbomb_id": 102,
        "giantbomb_slug": None,
    },
    UPS.APPLEII: {
        "id": 20,
        "igdb_id": 75,
        "igdb_slug": "appleii",
        "name": "Apple II",
        "ra_id": 38,
        "tgdb_id": 4942,
        "giantbomb_id": 12,
        "giantbomb_slug": "apple-ii",
    },
    UPS.APPLEIII: {
        "id": 63154,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Apple III",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.AQUARIUS: {
        "id": 51,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Mattel Aquarius",
        "ra_id": None,
        "tgdb_id": 4989,
        "giantbomb_id": 100,
        "giantbomb_slug": "aquarius",
    },
    UPS.ARCADE: {
        "id": 178,
        "igdb_id": 52,
        "igdb_slug": "arcade",
        "name": "Arcade",
        "ra_id": 27,
        "tgdb_id": 23,
        "giantbomb_id": 84,
        "giantbomb_slug": "arcade",
    },
    UPS.ARDUBOY: {
        "id": 244294,
        "igdb_id": 438,
        "igdb_slug": "arduboy",
        "name": "Arduboy",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.ASTROCADE: {
        "id": 31,
        "igdb_id": 91,
        "igdb_slug": "astrocade",
        "name": "Bally Astrocade",
        "ra_id": None,
        "tgdb_id": 4968,
        "giantbomb_id": 120,
        "giantbomb_slug": "bally-astrocade",
    },
    UPS.ATARI_ST: {
        "id": 15,
        "igdb_id": 63,
        "igdb_slug": "atari-st",
        "name": "Atari ST/STE",
        "ra_id": 36,
        "tgdb_id": 4937,
        "giantbomb_id": 13,
        "giantbomb_slug": "atari-st",
    },
    UPS.ATARI2600: {
        "id": 12,
        "igdb_id": 59,
        "igdb_slug": "atari2600",
        "name": "Atari 2600",
        "ra_id": 25,
        "tgdb_id": 22,
        "giantbomb_id": 40,
        "giantbomb_slug": "atari-2600",
    },
    UPS.ATARI5200: {
        "id": 17,
        "igdb_id": 66,
        "igdb_slug": "atari5200",
        "name": "Atari 5200",
        "ra_id": 50,
        "tgdb_id": 26,
        "giantbomb_id": 67,
        "giantbomb_slug": "atari-5200",
    },
    UPS.ATARI7800: {
        "id": 16,
        "igdb_id": 60,
        "igdb_slug": "atari7800",
        "name": "Atari 7800",
        "ra_id": 51,
        "tgdb_id": 27,
        "giantbomb_id": 70,
        "giantbomb_slug": "atari-7800",
    },
    UPS.ATARI8BIT: {
        "id": 18,
        "igdb_id": 65,
        "igdb_slug": "atari8bit",
        "name": "Atari 8-bit",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 24,
        "giantbomb_slug": "atari-8-bit",
    },
    UPS.ATOM: {
        "id": 55099,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Acorn Atom",
        "ra_id": None,
        "tgdb_id": 5014,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.BBCMICRO: {
        "id": 26,
        "igdb_id": 69,
        "igdb_slug": "bbcmicro",
        "name": "BBC Micro",
        "ra_id": None,
        "tgdb_id": 5013,
        "giantbomb_id": 110,
        "giantbomb_slug": "bbc-micro",
    },
    UPS.BEENA: {
        "id": 82,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Sega Advanced Pico Beena",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 174,
        "giantbomb_slug": None,
    },
    UPS.BIT_90: {
        "id": 97614,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Bit Corporation BIT 90",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.C_PLUS_4: {
        "id": 7,
        "igdb_id": 94,
        "igdb_slug": "c-plus-4",
        "name": "Commodore Plus/4",
        "ra_id": None,
        "tgdb_id": 5007,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.C128: {
        "id": 8,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Commodore 128",
        "ra_id": None,
        "tgdb_id": 4946,
        "giantbomb_id": 58,
        "giantbomb_slug": "commodore-128",
    },
    UPS.C16: {
        "id": 6,
        "igdb_id": 93,
        "igdb_slug": "c16",
        "name": "Commodore 16",
        "ra_id": None,
        "tgdb_id": 5006,
        "giantbomb_id": 150,
        "giantbomb_slug": "commodore-16",
    },
    UPS.C64: {
        "id": 5,
        "igdb_id": 15,
        "igdb_slug": "c64",
        "name": "Commodore MAX",
        "ra_id": None,
        "tgdb_id": 40,
        "giantbomb_id": 14,
        "giantbomb_slug": "commodore-64",
    },
    UPS.CAMPUTERS_LYNX: {
        "id": 97720,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Camputers Lynx",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.CASIO_CFX_9850: {
        "id": 97839,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio CFX-9850",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.CASIO_FP_1000: {
        "id": 98757,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio FP-1000 & FP-1100",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.CASIO_LOOPY: {
        "id": 37,
        "igdb_id": 380,
        "igdb_slug": "casio-loopy",
        "name": "Casio Loopy",
        "ra_id": None,
        "tgdb_id": 4991,
        "giantbomb_id": 126,
        "giantbomb_slug": "casio-loopy",
    },
    UPS.CASIO_PB_1000: {
        "id": 98771,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio PB-1000",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.CASIO_PV_1000: {
        "id": 98793,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio PV-1000",
        "ra_id": None,
        "tgdb_id": 4964,
        "giantbomb_id": 149,
        "giantbomb_slug": "casio-pv-1000",
    },
    UPS.CASIO_PV_2000: {
        "id": 98811,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Casio PV-2000",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 187,
        "giantbomb_slug": "casio-pv-2000",
    },
    UPS.COLECOVISION: {
        "id": 39,
        "igdb_id": 68,
        "igdb_slug": "colecovision",
        "name": "ColecoVision",
        "ra_id": 44,
        "tgdb_id": 31,
        "giantbomb_id": 47,
        "giantbomb_slug": "colecovision",
    },
    UPS.COMMANDER_X16: {
        "id": 54769,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "8-Bit Productions Commander X16",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.COMMODORE_CDTV: {
        "id": 9,
        "igdb_id": 158,
        "igdb_slug": "commodore-cdtv",
        "name": "Commodore CDTV",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 142,
        "giantbomb_slug": "commodore-cdtv",
    },
    UPS.CPET: {
        "id": 10,
        "igdb_id": 90,
        "igdb_slug": "cpet",
        "name": "Commodore PET",
        "ra_id": None,
        "tgdb_id": 5008,
        "giantbomb_id": 62,
        "giantbomb_slug": "commodore-petcbm",
    },
    UPS.DC: {
        "id": 54694,
        "igdb_id": 23,
        "igdb_slug": "dc",
        "name": "Sega Dreamcast",
        "ra_id": 40,
        "tgdb_id": 16,
        "giantbomb_id": 37,
        "giantbomb_slug": "dreamcast",
    },
    UPS.DOS: {
        "id": 233075,
        "igdb_id": 13,
        "igdb_slug": "dos",
        "name": "Microsoft DOS",
        "ra_id": None,
        "tgdb_id": 1,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.EXCALIBUR_64: {
        "id": 97612,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "BGR Computers Excalibur 64",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.FAIRCHILD_CHANNEL_F: {
        "id": 43,
        "igdb_id": 127,
        "igdb_slug": "fairchild-channel-f",
        "name": "Fairchild Channel F",
        "ra_id": 57,
        "tgdb_id": 4928,
        "giantbomb_id": 66,
        "giantbomb_slug": "channel-f",
    },
    UPS.FDS: {
        "id": 54692,
        "igdb_id": 51,
        "igdb_slug": "fds",
        "name": "Nintendo Famicom Disk System",
        "ra_id": None,
        "tgdb_id": 4936,
        "giantbomb_id": 91,
        "giantbomb_slug": "famicom-disk-system",
    },
    UPS.FM_TOWNS: {
        "id": 238902,
        "igdb_id": 118,
        "igdb_slug": "fm-towns",
        "name": "Fujitsu - FM Towns",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 108,
        "giantbomb_slug": "fm-towns",
    },
    UPS.GAMATE: {
        "id": 97616,
        "igdb_id": 378,
        "igdb_slug": "gamate",
        "name": "Bit Corporation Gamate",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 166,
        "giantbomb_slug": "gamate",
    },
    UPS.GAMEGEAR: {
        "id": 84,
        "igdb_id": 35,
        "igdb_slug": "gamegear",
        "name": "Sega Game Gear",
        "ra_id": 15,
        "tgdb_id": 20,
        "giantbomb_id": 5,
        "giantbomb_slug": "game-gear",
    },
    UPS.GB: {
        "id": 70,
        "igdb_id": 33,
        "igdb_slug": "gb",
        "name": "Nintendo GameBoy",
        "ra_id": 4,
        "tgdb_id": 4,
        "giantbomb_id": 3,
        "giantbomb_slug": "game-boy",
    },
    UPS.GBA: {
        "id": 71,
        "igdb_id": 24,
        "igdb_slug": "gba",
        "name": "Nintendo Game Boy Advance",
        "ra_id": 5,
        "tgdb_id": 5,
        "giantbomb_id": 4,
        "giantbomb_slug": "game-boy-advance",
    },
    UPS.GBC: {
        "id": 72,
        "igdb_id": 22,
        "igdb_slug": "gbc",
        "name": "Nintendo Game Boy Color",
        "ra_id": 6,
        "tgdb_id": 41,
        "giantbomb_id": 57,
        "giantbomb_slug": "game-boy-color",
    },
    UPS.GENESIS: {
        "id": 86,
        "igdb_id": 29,
        "igdb_slug": "genesis-slash-megadrive",
        "name": "Sega Mega Drive / Genesis",
        "ra_id": 1,
        "tgdb_id": 18,
        "giantbomb_id": 6,
        "giantbomb_slug": "genesis",
    },
    UPS.INTELLIVISION: {
        "id": 52,
        "igdb_id": 67,
        "igdb_slug": "intellivision",
        "name": "Mattel Intellivision",
        "ra_id": 45,
        "tgdb_id": 32,
        "giantbomb_id": 51,
        "giantbomb_slug": "intellivision",
    },
    UPS.JAGUAR: {
        "id": 13,
        "igdb_id": 62,
        "igdb_slug": "jaguar",
        "name": "Atari Jaguar",
        "ra_id": 17,
        "tgdb_id": 28,
        "giantbomb_id": 28,
        "giantbomb_slug": "jaguar",
    },
    UPS.LINUX: {
        "id": 233076,
        "igdb_id": 3,
        "igdb_slug": "linux",
        "name": "Linux",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 152,
        "giantbomb_slug": "linux",
    },
    UPS.LYNX: {
        "id": 14,
        "igdb_id": 61,
        "igdb_slug": "lynx",
        "name": "Atari Lynx",
        "ra_id": 13,
        "tgdb_id": 4924,
        "giantbomb_id": 7,
        "giantbomb_slug": "atari-lynx",
    },
    UPS.MAC: {
        "id": 30,
        "igdb_id": 14,
        "igdb_slug": "mac",
        "name": "Apple Mac",
        "ra_id": None,
        "tgdb_id": 37,
        "giantbomb_id": 17,
        "giantbomb_slug": "mac",
    },
    UPS.MICROBEE: {
        "id": 69714,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Applied Technology MicroBee",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 168,
        "giantbomb_slug": "micro-bee",
    },
    UPS.MSX: {
        "id": 53,
        "igdb_id": 27,
        "igdb_slug": "msx",
        "name": "MSX",
        "ra_id": 29,
        "tgdb_id": 4929,
        "giantbomb_id": 15,
        "giantbomb_slug": "msx",
    },
    UPS.MSX2: {
        "id": 54,
        "igdb_id": 53,
        "igdb_slug": "msx2",
        "name": "MSX 2",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.MULTIVISION: {
        "id": 52922,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Tsukuda Original Othello Multivision",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.N64: {
        "id": 64,
        "igdb_id": 4,
        "igdb_slug": "n64",
        "name": "Nintendo 64",
        "ra_id": 2,
        "tgdb_id": 3,
        "giantbomb_id": 43,
        "giantbomb_slug": "nintendo-64",
    },
    UPS.NDS: {
        "id": 66,
        "igdb_id": 20,
        "igdb_slug": "nds",
        "name": "Nintendo DS",
        "ra_id": 18,
        "tgdb_id": 8,
        "giantbomb_id": 52,
        "giantbomb_slug": "nintendo-ds",
    },
    UPS.NEC_PC_6000_SERIES: {
        "id": 58,
        "igdb_id": 157,
        "igdb_slug": "nec-pc-6000-series",
        "name": "NEC PC-6000",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.NEO_GEO_CD: {
        "id": 161829,
        "igdb_id": 136,
        "igdb_slug": "neo-geo-cd",
        "name": "Neo Geo CD",
        "ra_id": 56,
        "tgdb_id": 4956,
        "giantbomb_id": 167,
        "giantbomb_slug": "neo-geo-cd",
    },
    UPS.NEO_GEO_POCKET: {
        "id": 97,
        "igdb_id": 119,
        "igdb_slug": "neo-geo-pocket",
        "name": "Neo Geo Pocket",
        "ra_id": 14,
        "tgdb_id": 4922,
        "giantbomb_id": 80,
        "giantbomb_slug": "neo-geo-pocket",
    },
    UPS.NEO_GEO_POCKET_COLOR: {
        "id": 98,
        "igdb_id": 120,
        "igdb_slug": "neo-geo-pocket-color",
        "name": "Neo Geo Pocket Color",
        "ra_id": None,
        "tgdb_id": 4923,
        "giantbomb_id": 81,
        "giantbomb_slug": "neo-geo-pocket-color",
    },
    UPS.NEOGEOAES: {
        "id": 96,
        "igdb_id": 80,
        "igdb_slug": "neogeoaes",
        "name": "Neo Geo",
        "ra_id": None,
        "tgdb_id": 24,
        "giantbomb_id": 25,
        "giantbomb_slug": "neo-geo",
    },
    UPS.NES: {
        "id": 68,
        "igdb_id": 18,
        "igdb_slug": "nes",
        "name": "Nintendo Entertainment System",
        "ra_id": 7,
        "tgdb_id": 7,
        "giantbomb_id": 21,
        "giantbomb_slug": "nintendo-entertainment-system",
    },
    UPS.NEW_NINTENDON3DS: {
        "id": 63,
        "igdb_id": 137,
        "igdb_slug": "new-nintendo-3ds",
        "name": "Nintendo New 3DS",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 156,
        "giantbomb_slug": "new-nintendo-3ds",
    },
    UPS.NGC: {
        "id": 73,
        "igdb_id": 21,
        "igdb_slug": "ngc",
        "name": "Nintendo GameCube",
        "ra_id": 16,
        "tgdb_id": 2,
        "giantbomb_id": 23,
        "giantbomb_slug": "gamecube",
    },
    UPS.NINTENDO_DSI: {
        "id": 67,
        "igdb_id": 159,
        "igdb_slug": "nintendo-dsi",
        "name": "Nintendo DSi",
        "ra_id": 78,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.ODYSSEY: {
        "id": 48,
        "igdb_id": 88,
        "igdb_slug": "odyssey--1",
        "name": "Magnavox Odyssey",
        "ra_id": None,
        "tgdb_id": 4961,
        "giantbomb_id": 74,
        "giantbomb_slug": "odyssey",
    },
    UPS.ODYSSEY_2_SLASH_VIDEOPAC_G7000: {
        "id": 49,
        "igdb_id": 133,
        "igdb_slug": "odyssey-2-slash-videopac-g7000",
        "name": "Magnavox Odyssey 2",
        "ra_id": 23,
        "tgdb_id": 4927,
        "giantbomb_id": 60,
        "giantbomb_slug": None,
    },
    UPS.PC_8800_SERIES: {
        "id": 57,
        "igdb_id": 125,
        "igdb_slug": "pc-8800-series",
        "name": "NEC PC-8800",
        "ra_id": None,
        "tgdb_id": 4933,
        "giantbomb_id": 47,
        "giantbomb_slug": "nec-pc-8800-series",
    },
    UPS.PC_9800_SERIES: {
        "id": 59,
        "igdb_id": 149,
        "igdb_slug": "pc-9800-series",
        "name": "NEC PC-9000",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 112,
        "giantbomb_slug": "nec-pc-9801",
    },
    UPS.PC_JR: {
        "id": 233269,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "IBM PCjr",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.PHILIPS_CD_I: {
        "id": 161827,
        "igdb_id": 117,
        "igdb_slug": "philips-cd-i",
        "name": "Philips CD-i",
        "ra_id": 42,
        "tgdb_id": 4917,
        "giantbomb_id": 27,
        "giantbomb_slug": "cd-i",
    },
    UPS.POCKET_CHALLENGE_V2: {
        "id": 97550,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Benesse Pocket Challenge V2",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.POCKET_CHALLENGE_W: {
        "id": 97577,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Benesse Pocket Challenge W",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.POCKETSTATION: {
        "id": 103,
        "igdb_id": 441,
        "igdb_slug": "pocketstation",
        "name": "Sony PocketStation",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.POKEMON_MINI: {
        "id": 244733,
        "igdb_id": 166,
        "igdb_slug": "pokemon-mini",
        "name": "Nintendo Pokemon Mini",
        "ra_id": 24,
        "tgdb_id": None,
        "giantbomb_id": 134,
        "giantbomb_slug": "pokemon-mini",
    },
    UPS.PS2: {
        "id": 101,
        "igdb_id": 8,
        "igdb_slug": "ps2",
        "name": "Sony PlayStation 2",
        "ra_id": 21,
        "tgdb_id": 11,
        "giantbomb_id": 19,
        "giantbomb_slug": "playstation-2",
    },
    UPS.PS3: {
        "id": 161830,
        "igdb_id": 9,
        "igdb_slug": "ps3",
        "name": "Sony Playstation 3",
        "ra_id": None,
        "tgdb_id": 12,
        "giantbomb_id": 35,
        "giantbomb_slug": "playstation-3",
    },
    UPS.PS4: {
        "id": 232986,
        "igdb_id": 48,
        "igdb_slug": "ps4--1",
        "name": "Sony Playstation 4",
        "ra_id": None,
        "tgdb_id": 4919,
        "giantbomb_id": 146,
        "giantbomb_slug": "playstation-4",
    },
    UPS.PS5: {
        "id": 232987,
        "igdb_id": 167,
        "igdb_slug": "ps5",
        "name": "Sony Playstation 5",
        "ra_id": None,
        "tgdb_id": 4980,
        "giantbomb_id": 176,
        "giantbomb_slug": "playstation-5",
    },
    UPS.PSP: {
        "id": 161831,
        "igdb_id": 38,
        "igdb_slug": "psp",
        "name": "Sony Playstation Portable",
        "ra_id": 41,
        "tgdb_id": 13,
        "giantbomb_id": 18,
        "giantbomb_slug": "playstation-portable",
    },
    UPS.PSVITA: {
        "id": 102,
        "igdb_id": 46,
        "igdb_slug": "psvita",
        "name": "Sony PlayStation Vita",
        "ra_id": None,
        "tgdb_id": 39,
        "giantbomb_id": 129,
        "giantbomb_slug": "playstation-vita",
    },
    UPS.PSX: {
        "id": 100,
        "igdb_id": 7,
        "igdb_slug": "ps",
        "name": "Sony PlayStation",
        "ra_id": 12,
        "tgdb_id": 10,
        "giantbomb_id": 22,
        "giantbomb_slug": "playstation",
    },
    UPS.RCA_STUDIO_II: {
        "id": 234745,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "RCA Studio II",
        "ra_id": None,
        "tgdb_id": 4967,
        "giantbomb_id": 131,
        "giantbomb_slug": "rca-studio-ii",
    },
    UPS.SATURN: {
        "id": 54695,
        "igdb_id": 32,
        "igdb_slug": "saturn",
        "name": "Sega Saturn",
        "ra_id": 39,
        "tgdb_id": 17,
        "giantbomb_id": 42,
        "giantbomb_slug": "saturn",
    },
    UPS.SC3000: {
        "id": 52165,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Sega Computer 3000",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.SEGA_PICO: {
        "id": 81,
        "igdb_id": 339,
        "igdb_slug": "sega-pico",
        "name": "Sega Pico",
        "ra_id": 68,
        "tgdb_id": 4958,
        "giantbomb_id": 105,
        "giantbomb_slug": "sega-pico",
    },
    UPS.SEGA32X: {
        "id": 80,
        "igdb_id": 30,
        "igdb_slug": "sega32",
        "name": "Sega 32X",
        "ra_id": 10,
        "tgdb_id": 33,
        "giantbomb_id": 31,
        "giantbomb_slug": "sega-32x",
    },
    UPS.SEGACD: {
        "id": 161828,
        "igdb_id": 78,
        "igdb_slug": "",
        "name": "Sega Mega CD / Sega CD",
        "ra_id": 9,
        "tgdb_id": 21,
        "giantbomb_id": 29,
        "giantbomb_slug": "sega-cd",
    },
    UPS.SERIES_X_S: {
        "id": 232984,
        "igdb_id": 169,
        "igdb_slug": "series-x-s",
        "name": "Microsoft Xbox Series X",
        "ra_id": None,
        "tgdb_id": 4981,
        "giantbomb_id": 179,
        "giantbomb_slug": "xbox-series-xs",
    },
    UPS.SFAM: {
        "id": 233081,
        "igdb_id": 58,
        "igdb_slug": "sfam",
        "name": "Super Famicom",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.SG1000: {
        "id": 244470,
        "igdb_id": 84,
        "igdb_slug": "sg1000",
        "name": "SG-1000",
        "ra_id": 33,
        "tgdb_id": None,
        "giantbomb_id": 141,
        "giantbomb_slug": "sega-sg-1000",
    },
    UPS.SHARP_X68000: {
        "id": 90,
        "igdb_id": 121,
        "igdb_slug": "sharp-x68000",
        "name": "Sharp X68000",
        "ra_id": 52,
        "tgdb_id": 4931,
        "giantbomb_id": 95,
        "giantbomb_slug": "sharp-x68000",
    },
    UPS.SINCLAIR_QL: {
        "id": 92,
        "igdb_id": 406,
        "igdb_slug": "sinclair-ql",
        "name": "Sinclair QL",
        "ra_id": None,
        "tgdb_id": 5020,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.SMS: {
        "id": 85,
        "igdb_id": 64,
        "igdb_slug": "sms",
        "name": "Sega Master System",
        "ra_id": 11,
        "tgdb_id": 35,
        "giantbomb_id": 8,
        "giantbomb_slug": "sega-master-system",
    },
    UPS.SNES: {
        "id": 74,
        "igdb_id": 19,
        "igdb_slug": "snes",
        "name": "Super Nintendo Entertainment System",
        "ra_id": 3,
        "tgdb_id": 6,
        "giantbomb_id": 9,
        "giantbomb_slug": "super-nintendo-entertainment-system",
    },
    UPS.SUPER_VISION_8000: {
        "id": 97267,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Bandai Super Vision 8000",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.SUPERVISION: {
        "id": 244828,
        "igdb_id": 415,
        "igdb_slug": "watara-slash-quickshot-supervision",
        "name": "Watara Supervision",
        "ra_id": 63,
        "tgdb_id": 4959,
        "giantbomb_id": 147,
        "giantbomb_slug": "watara-supervision",
    },
    UPS.SWITCH: {
        "id": 233067,
        "igdb_id": 130,
        "igdb_slug": "switch",
        "name": "Nintendo Switch",
        "ra_id": None,
        "tgdb_id": 4971,
        "giantbomb_id": 157,
        "giantbomb_slug": "nintendo-switch",
    },
    UPS.TG16: {
        "id": 245372,
        "igdb_id": 86,
        "igdb_slug": "turbografx16--1",
        "name": "TurboGrafx-16/PC Engine",
        "ra_id": 8,
        "tgdb_id": 34,
        "giantbomb_id": 55,
        "giantbomb_slug": "turbografx-16",
    },
    UPS.TI_82: {
        "id": 47973,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Texas Instruments TI-82",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.TI_83: {
        "id": 243852,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Texas Instruments TI-83",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.TRS_80: {
        "id": 105,
        "igdb_id": 126,
        "igdb_slug": "trs-80",
        "name": "Tandy/RadioShack TRS-80",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": 63,
        "giantbomb_slug": "trs-80",
    },
    UPS.TRS_80_COLOR_COMPUTER: {
        "id": 106,
        "igdb_id": 151,
        "igdb_slug": "trs-80-color-computer",
        "name": "Tandy/RadioShack TRS-80 Color Computer",
        "ra_id": None,
        "tgdb_id": 4941,
        "giantbomb_id": 68,
        "giantbomb_slug": "trs-80-coco",
    },
    UPS.TURBOGRAFX_CD: {
        "id": 247350,
        "igdb_id": 150,
        "igdb_slug": "turbografx-16-slash-pc-engine-cd",
        "name": "Turbografx-16/PC Engine CD",
        "ra_id": None,
        "tgdb_id": 4955,
        "giantbomb_id": 53,
        "giantbomb_slug": "turbografx-cd",
    },
    UPS.VECTREX: {
        "id": 45,
        "igdb_id": 70,
        "igdb_slug": "vectrex",
        "name": "Vectrex",
        "ra_id": 46,
        "tgdb_id": 4939,
        "giantbomb_id": 76,
        "giantbomb_slug": "vectrex",
    },
    UPS.VIC_20: {
        "id": 4,
        "igdb_id": 71,
        "igdb_slug": "vic-20",
        "name": "Commodore VIC20",
        "ra_id": None,
        "tgdb_id": 4945,
        "giantbomb_id": 30,
        "giantbomb_slug": "vic-20",
    },
    UPS.VIRTUALBOY: {
        "id": 75,
        "igdb_id": 87,
        "igdb_slug": "virtualboy",
        "name": "Nintendo Virtual Boy",
        "ra_id": 28,
        "tgdb_id": 4918,
        "giantbomb_id": 79,
        "giantbomb_slug": "virtual-boy",
    },
    UPS.WII: {
        "id": 76,
        "igdb_id": 5,
        "igdb_slug": "wii",
        "name": "Nintendo Wii",
        "ra_id": 19,
        "tgdb_id": 9,
        "giantbomb_id": 36,
        "giantbomb_slug": "wii",
    },
    UPS.WIIU: {
        "id": 77,
        "igdb_id": 41,
        "igdb_slug": "wiiu",
        "name": "Nintendo WiiU",
        "ra_id": None,
        "tgdb_id": 38,
        "giantbomb_id": 139,
        "giantbomb_slug": "wii-u",
    },
    UPS.WIN: {
        "id": 233074,
        "igdb_id": 6,
        "igdb_slug": "win",
        "name": "Microsoft Windows",
        "ra_id": None,
        "tgdb_id": 1,
        "giantbomb_id": 94,
        "giantbomb_slug": "pc",
    },
    UPS.WONDERSWAN: {
        "id": 34,
        "igdb_id": 57,
        "igdb_slug": "wonderswan",
        "name": "Bandai WonderSwan",
        "ra_id": 53,
        "tgdb_id": 4925,
        "giantbomb_id": 65,
        "giantbomb_slug": "wonderswan",
    },
    UPS.WONDERSWAN_COLOR: {
        "id": 35,
        "igdb_id": 123,
        "igdb_slug": "wonderswan-color",
        "name": "Bandai WonderSwan Color",
        "ra_id": None,
        "tgdb_id": 4926,
        "giantbomb_id": 54,
        "giantbomb_slug": "wonderswan-color",
    },
    UPS.X1: {
        "id": 89,
        "igdb_id": 77,
        "igdb_slug": "x1",
        "name": "Sharp X1",
        "ra_id": 64,
        "tgdb_id": 4977,
        "giantbomb_id": 113,
        "giantbomb_slug": "sharp-x1",
    },
    UPS.XBOX: {
        "id": 54696,
        "igdb_id": 11,
        "igdb_slug": "xbox",
        "name": "Microsoft Xbox",
        "ra_id": None,
        "tgdb_id": 14,
        "giantbomb_id": 32,
        "giantbomb_slug": "xbox",
    },
    UPS.XBOX360: {
        "id": 54697,
        "igdb_id": 12,
        "igdb_slug": "xbox360",
        "name": "Microsoft Xbox 360",
        "ra_id": None,
        "tgdb_id": 15,
        "giantbomb_id": 20,
        "giantbomb_slug": "xbox-360",
    },
    UPS.XBOXONE: {
        "id": 161824,
        "igdb_id": 49,
        "igdb_slug": "xboxone",
        "name": "Microsoft Xbox One",
        "ra_id": None,
        "tgdb_id": 4920,
        "giantbomb_id": 145,
        "giantbomb_slug": "xbox-one",
    },
    UPS.Z88: {
        "id": 97718,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Cambridge Computer Z88",
        "ra_id": None,
        "tgdb_id": None,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.ZX80: {
        "id": 232985,
        "igdb_id": None,
        "igdb_slug": "",
        "name": "Sinclair ZX80",
        "ra_id": None,
        "tgdb_id": 5009,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.ZX81: {
        "id": 94,
        "igdb_id": 373,
        "igdb_slug": "sinclair-zx81",
        "name": "Sinclair ZX81",
        "ra_id": None,
        "tgdb_id": 5010,
        "giantbomb_id": None,
        "giantbomb_slug": None,
    },
    UPS.ZXS: {
        "id": 93,
        "igdb_id": 26,
        "igdb_slug": "zxs",
        "name": "Sinclair ZX Spectrum",
        "ra_id": 59,
        "tgdb_id": 4913,
        "giantbomb_id": 16,
        "giantbomb_slug": "zx-spectrum",
    },
}
