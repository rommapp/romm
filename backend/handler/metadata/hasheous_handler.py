import json
from datetime import datetime
from typing import Any, NotRequired, TypedDict

import httpx
import pydash
from config import DEV_MODE, HASHEOUS_API_ENABLED
from fastapi import HTTPException, status
from logger.logger import log
from models.rom import RomFile
from utils import get_version
from utils.context import ctx_httpx_client

from .base_hander import BaseRom, MetadataHandler
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


class HasheousRom(BaseRom):
    hasheous_id: int | None
    igdb_id: NotRequired[int | None]
    slug: NotRequired[str]
    igdb_metadata: NotRequired[IGDBMetadata]
    ra_id: NotRequired[int | None]
    ra_metadata: NotRequired[RAMetadata]
    tgdb_id: NotRequired[int | None]
    hasheous_metadata: NotRequired[HasheousMetadata]


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
        platform = HASHEOUS_PLATFORM_LIST.get(slug, None)

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

    async def lookup_rom(self, files: list[RomFile]) -> HasheousRom:
        fallback_rom = HasheousRom(
            hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None
        )

        if not HASHEOUS_API_ENABLED:
            return fallback_rom

        first_file = next(
            (
                file
                for file in files
                if file.file_size_bytes is not None and file.file_size_bytes > 0
            ),
            None,
        )
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
        if not HASHEOUS_API_ENABLED:
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
        if not HASHEOUS_API_ENABLED:
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


HASHEOUS_PLATFORM_LIST: dict[str, SlugToHasheousId] = {
    "3do": {
        "id": 161825,
        "name": "3DO Interactive Multiplayer",
        "igdb_id": 50,
        "tgdb_id": None,
        "ra_id": 43,
        "igdb_slug": "3do",
    },
    "3ds": {
        "id": 62,
        "name": "Nintendo 3DS",
        "igdb_id": 37,
        "tgdb_id": None,
        "ra_id": 62,
        "igdb_slug": "3ds",
    },
    "64dd": {
        "id": 65,
        "name": "Nintendo 64DD",
        "igdb_id": 416,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "64dd",
    },
    "acorn-archimedes": {
        "id": 24,
        "name": "Acorn Archimedes",
        "igdb_id": 116,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "acorn-archimedes",
    },
    "acorn-electron": {
        "id": 25,
        "name": "Acorn Electron",
        "igdb_id": 134,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "acorn-electron",
    },
    "acpc": {
        "id": 28,
        "name": "Amstrad CPC",
        "igdb_id": 25,
        "tgdb_id": None,
        "ra_id": 37,
        "igdb_slug": "acpc",
    },
    "action-max": {
        "id": 232983,
        "name": "Action Max",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "adventure-vision": {
        "id": 234388,
        "name": "Entex Adventure Vision",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "altair-8800": {
        "id": 234456,
        "name": "MITS Altair 8800",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "amiga": {
        "id": 3,
        "name": "Commodore Amiga",
        "igdb_id": 16,
        "tgdb_id": None,
        "ra_id": 35,
        "igdb_slug": "amiga",
    },
    "amiga-cd32": {
        "id": 161823,
        "name": "Commodore CD32",
        "igdb_id": 114,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "amiga-cd32",
    },
    "amstrad-gx4000": {
        "id": 61540,
        "name": "Amstrad GX4000",
        "igdb_id": 506,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "amstrad-gx4000",
    },
    "amstrad-pcw": {
        "id": 29,
        "name": "Amstrad PCW",
        "igdb_id": 154,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "amstrad-pcw",
    },
    "apf": {
        "id": 61738,
        "name": "APF Imagination Machine",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "apple": {
        "id": 61885,
        "name": "Apple I",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "apple-iigs": {
        "id": 21,
        "name": "Apple IIGS",
        "igdb_id": 115,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "apple-iigs",
    },
    "apple-lisa": {
        "id": 69659,
        "name": "Apple Lisa",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "apple-pippin": {
        "id": 22,
        "name": "Apple Pippin",
        "igdb_id": 476,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "apple-pippin",
    },
    "apple2": {
        "id": 20,
        "name": "Apple II",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": 38,
        "igdb_slug": "",
    },
    "apple2gs": {
        "id": 21,
        "name": "Apple IIGS",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "apple3": {
        "id": 63154,
        "name": "Apple III",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "appleii": {
        "id": 20,
        "name": "Apple II",
        "igdb_id": 75,
        "tgdb_id": None,
        "ra_id": 38,
        "igdb_slug": "appleii",
    },
    "appleiii": {
        "id": 63154,
        "name": "Apple III",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "aquarius": {
        "id": 51,
        "name": "Mattel Aquarius",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "arcade": {
        "id": 178,
        "name": "Arcade",
        "igdb_id": 52,
        "tgdb_id": None,
        "ra_id": 27,
        "igdb_slug": "arcade",
    },
    "arduboy": {
        "id": 244294,
        "name": "Arduboy",
        "igdb_id": 438,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "arduboy",
    },
    "astrocade": {
        "id": 31,
        "name": "Bally Astrocade",
        "igdb_id": 91,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "astrocade",
    },
    "atari-st": {
        "id": 15,
        "name": "Atari ST/STE",
        "igdb_id": 63,
        "tgdb_id": None,
        "ra_id": 36,
        "igdb_slug": "atari-st",
    },
    "atari2600": {
        "id": 12,
        "name": "Atari 2600",
        "igdb_id": 59,
        "tgdb_id": None,
        "ra_id": 25,
        "igdb_slug": "atari2600",
    },
    "atari5200": {
        "id": 17,
        "name": "Atari 5200",
        "igdb_id": 66,
        "tgdb_id": None,
        "ra_id": 50,
        "igdb_slug": "atari5200",
    },
    "atari7800": {
        "id": 16,
        "name": "Atari 7800",
        "igdb_id": 60,
        "tgdb_id": None,
        "ra_id": 51,
        "igdb_slug": "atari7800",
    },
    "atari8bit": {
        "id": 18,
        "name": "Atari 8-bit",
        "igdb_id": 65,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "atari8bit",
    },
    "atom": {
        "id": 55099,
        "name": "Acorn Atom",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "bbcmicro": {
        "id": 26,
        "name": "BBC Micro",
        "igdb_id": 69,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "bbcmicro",
    },
    "beena": {
        "id": 82,
        "name": "Sega Advanced Pico Beena",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "bit-90": {
        "id": 97614,
        "name": "Bit Corporation BIT 90",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "c-plus-4": {
        "id": 7,
        "name": "Commodore Plus/4",
        "igdb_id": 94,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "c-plus-4",
    },
    "c128": {
        "id": 8,
        "name": "Commodore 128",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "c16": {
        "id": 6,
        "name": "Commodore 16",
        "igdb_id": 93,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "c16",
    },
    "c64": {
        "id": 5,
        "name": "Commodore MAX",
        "igdb_id": 15,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "c64",
    },
    "camputers-lynx": {
        "id": 97720,
        "name": "Camputers Lynx",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "casio-cfx-9850": {
        "id": 97839,
        "name": "Casio CFX-9850",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "casio-fp-1000": {
        "id": 98757,
        "name": "Casio FP-1000 & FP-1100",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "casio-loopy": {
        "id": 37,
        "name": "Casio Loopy",
        "igdb_id": 380,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "casio-loopy",
    },
    "casio-pb-1000": {
        "id": 98771,
        "name": "Casio PB-1000",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "casio-pv-1000": {
        "id": 98793,
        "name": "Casio PV-1000",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "casio-pv-2000": {
        "id": 98811,
        "name": "Casio PV-2000",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "colecovision": {
        "id": 39,
        "name": "ColecoVision",
        "igdb_id": 68,
        "tgdb_id": None,
        "ra_id": 44,
        "igdb_slug": "colecovision",
    },
    "commander-x16": {
        "id": 54769,
        "name": "8-Bit Productions Commander X16",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "commodore-cdtv": {
        "id": 9,
        "name": "Commodore CDTV",
        "igdb_id": 158,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "commodore-cdtv",
    },
    "cpet": {
        "id": 10,
        "name": "Commodore PET",
        "igdb_id": 90,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "cpet",
    },
    "dc": {
        "id": 54694,
        "name": "Sega Dreamcast",
        "igdb_id": 23,
        "tgdb_id": None,
        "ra_id": 40,
        "igdb_slug": "dc",
    },
    "dos": {
        "id": 233075,
        "name": "Microsoft DOS",
        "igdb_id": 13,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "dos",
    },
    "excalibur-64": {
        "id": 97612,
        "name": "BGR Computers Excalibur 64",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "fairchild-channel-f": {
        "id": 43,
        "name": "Fairchild Channel F",
        "igdb_id": 127,
        "tgdb_id": None,
        "ra_id": 57,
        "igdb_slug": "fairchild-channel-f",
    },
    "fds": {
        "id": 54692,
        "name": "Nintendo Famicom Disk System",
        "igdb_id": 51,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "fds",
    },
    "fm-towns": {
        "id": 238902,
        "name": "Fujitsu - FM Towns",
        "igdb_id": 118,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "fm-towns",
    },
    "gamate": {
        "id": 97616,
        "name": "Bit Corporation Gamate",
        "igdb_id": 378,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "gamate",
    },
    "gamegear": {
        "id": 84,
        "name": "Sega Game Gear",
        "igdb_id": 35,
        "tgdb_id": None,
        "ra_id": 15,
        "igdb_slug": "gamegear",
    },
    "gb": {
        "id": 70,
        "name": "Nintendo GameBoy",
        "igdb_id": 33,
        "tgdb_id": None,
        "ra_id": 4,
        "igdb_slug": "gb",
    },
    "gba": {
        "id": 71,
        "name": "Nintendo Game Boy Advance",
        "igdb_id": 24,
        "tgdb_id": None,
        "ra_id": 5,
        "igdb_slug": "gba",
    },
    "gbc": {
        "id": 72,
        "name": "Nintendo Game Boy Color",
        "igdb_id": 22,
        "tgdb_id": None,
        "ra_id": 6,
        "igdb_slug": "gbc",
    },
    "genesis-slash-megadrive": {
        "id": 86,
        "name": "Sega Mega Drive / Genesis",
        "igdb_id": 29,
        "tgdb_id": None,
        "ra_id": 1,
        "igdb_slug": "genesis-slash-megadrive",
    },
    "intellivision": {
        "id": 52,
        "name": "Mattel Intellivision",
        "igdb_id": 67,
        "tgdb_id": None,
        "ra_id": 45,
        "igdb_slug": "intellivision",
    },
    "jaguar": {
        "id": 13,
        "name": "Atari Jaguar",
        "igdb_id": 62,
        "tgdb_id": None,
        "ra_id": 17,
        "igdb_slug": "jaguar",
    },
    "linux": {
        "id": 233076,
        "name": "Linux",
        "igdb_id": 3,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "linux",
    },
    "lynx": {
        "id": 14,
        "name": "Atari Lynx",
        "igdb_id": 61,
        "tgdb_id": None,
        "ra_id": 13,
        "igdb_slug": "lynx",
    },
    "mac": {
        "id": 30,
        "name": "Apple Mac",
        "igdb_id": 14,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "mac",
    },
    "microbee": {
        "id": 69714,
        "name": "Applied Technology MicroBee",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "msx": {
        "id": 53,
        "name": "MSX",
        "igdb_id": 27,
        "tgdb_id": None,
        "ra_id": 29,
        "igdb_slug": "msx",
    },
    "msx2": {
        "id": 54,
        "name": "MSX 2",
        "igdb_id": 53,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "msx2",
    },
    "multivision": {
        "id": 52922,
        "name": "Tsukuda Original Othello Multivision",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "n64": {
        "id": 64,
        "name": "Nintendo 64",
        "igdb_id": 4,
        "tgdb_id": None,
        "ra_id": 2,
        "igdb_slug": "n64",
    },
    "nds": {
        "id": 66,
        "name": "Nintendo DS",
        "igdb_id": 20,
        "tgdb_id": None,
        "ra_id": 18,
        "igdb_slug": "nds",
    },
    "nec-pc-6000-series": {
        "id": 58,
        "name": "NEC PC-6000",
        "igdb_id": 157,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "nec-pc-6000-series",
    },
    "neo-geo-cd": {
        "id": 161829,
        "name": "Neo Geo CD",
        "igdb_id": 136,
        "tgdb_id": None,
        "ra_id": 56,
        "igdb_slug": "neo-geo-cd",
    },
    "neo-geo-pocket": {
        "id": 97,
        "name": "Neo Geo Pocket",
        "igdb_id": 119,
        "tgdb_id": None,
        "ra_id": 14,
        "igdb_slug": "neo-geo-pocket",
    },
    "neo-geo-pocket-color": {
        "id": 98,
        "name": "Neo Geo Pocket Color",
        "igdb_id": 120,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "neo-geo-pocket-color",
    },
    "neogeoaes": {
        "id": 96,
        "name": "Neo Geo",
        "igdb_id": 80,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "neogeoaes",
    },
    "nes": {
        "id": 68,
        "name": "Nintendo Entertainment System",
        "igdb_id": 18,
        "tgdb_id": None,
        "ra_id": 7,
        "igdb_slug": "nes",
    },
    "new-nintendo-3ds": {
        "id": 63,
        "name": "Nintendo New 3DS",
        "igdb_id": 137,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "new-nintendo-3ds",
    },
    "ngc": {
        "id": 73,
        "name": "Nintendo GameCube",
        "igdb_id": 21,
        "tgdb_id": None,
        "ra_id": 16,
        "igdb_slug": "ngc",
    },
    "nintendo-dsi": {
        "id": 67,
        "name": "Nintendo DSi",
        "igdb_id": 159,
        "tgdb_id": None,
        "ra_id": 78,
        "igdb_slug": "nintendo-dsi",
    },
    "odyssey--1": {
        "id": 48,
        "name": "Magnavox Odyssey",
        "igdb_id": 88,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "odyssey--1",
    },
    "odyssey-2-slash-videopac-g7000": {
        "id": 49,
        "name": "Magnavox Odyssey 2",
        "igdb_id": 133,
        "tgdb_id": None,
        "ra_id": 23,
        "igdb_slug": "odyssey-2-slash-videopac-g7000",
    },
    "pc-8800-series": {
        "id": 57,
        "name": "NEC PC-8800",
        "igdb_id": 125,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "pc-8800-series",
    },
    "pc-9800-series": {
        "id": 59,
        "name": "NEC PC-9000",
        "igdb_id": 149,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "pc-9800-series",
    },
    "pc-jr": {
        "id": 233269,
        "name": "IBM PCjr",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "philips-cd-i": {
        "id": 161827,
        "name": "Philips CD-i",
        "igdb_id": 117,
        "tgdb_id": None,
        "ra_id": 42,
        "igdb_slug": "philips-cd-i",
    },
    "pocket-challenge-v2": {
        "id": 97550,
        "name": "Benesse Pocket Challenge V2",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "pocket-challenge-w": {
        "id": 97577,
        "name": "Benesse Pocket Challenge W",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "pocketstation": {
        "id": 103,
        "name": "Sony PocketStation",
        "igdb_id": 441,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "pocketstation",
    },
    "pokemon-mini": {
        "id": 244733,
        "name": "Nintendo Pokemon Mini",
        "igdb_id": 166,
        "tgdb_id": None,
        "ra_id": 24,
        "igdb_slug": "pokemon-mini",
    },
    "ps": {
        "id": 100,
        "name": "Sony PlayStation",
        "igdb_id": 7,
        "tgdb_id": None,
        "ra_id": 12,
        "igdb_slug": "ps",
    },
    "ps2": {
        "id": 101,
        "name": "Sony PlayStation 2",
        "igdb_id": 8,
        "tgdb_id": None,
        "ra_id": 21,
        "igdb_slug": "ps2",
    },
    "ps3": {
        "id": 161830,
        "name": "Sony Playstation 3",
        "igdb_id": 9,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "ps3",
    },
    "ps4--1": {
        "id": 232986,
        "name": "Sony Playstation 4",
        "igdb_id": 48,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "ps4--1",
    },
    "ps5": {
        "id": 232987,
        "name": "Sony Playstation 5",
        "igdb_id": 167,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "ps5",
    },
    "psp": {
        "id": 161831,
        "name": "Sony Playstation Portable",
        "igdb_id": 38,
        "tgdb_id": None,
        "ra_id": 41,
        "igdb_slug": "psp",
    },
    "psvita": {
        "id": 102,
        "name": "Sony PlayStation Vita",
        "igdb_id": 46,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "psvita",
    },
    "rca-studio-ii": {
        "id": 234745,
        "name": "RCA Studio II",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "saturn": {
        "id": 54695,
        "name": "Sega Saturn",
        "igdb_id": 32,
        "tgdb_id": None,
        "ra_id": 39,
        "igdb_slug": "saturn",
    },
    "sc3000": {
        "id": 52165,
        "name": "Sega Computer 3000",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "sega-pico": {
        "id": 81,
        "name": "Sega Pico",
        "igdb_id": 339,
        "tgdb_id": None,
        "ra_id": 68,
        "igdb_slug": "sega-pico",
    },
    "sega32": {
        "id": 80,
        "name": "Sega 32X",
        "igdb_id": 30,
        "tgdb_id": None,
        "ra_id": 10,
        "igdb_slug": "sega32",
    },
    "segacd": {
        "id": 161828,
        "name": "Sega Mega CD / Sega CD",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": 9,
        "igdb_slug": "",
    },
    "series-x-s": {
        "id": 232984,
        "name": "Microsoft Xbox Series X",
        "igdb_id": 169,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "series-x-s",
    },
    "sfam": {
        "id": 233081,
        "name": "Super Famicom",
        "igdb_id": 58,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "sfam",
    },
    "sg1000": {
        "id": 244470,
        "name": "SG-1000",
        "igdb_id": 84,
        "tgdb_id": None,
        "ra_id": 33,
        "igdb_slug": "sg1000",
    },
    "sharp-x68000": {
        "id": 90,
        "name": "Sharp X68000",
        "igdb_id": 121,
        "tgdb_id": None,
        "ra_id": 52,
        "igdb_slug": "sharp-x68000",
    },
    "sinclair-ql": {
        "id": 92,
        "name": "Sinclair QL",
        "igdb_id": 406,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "sinclair-ql",
    },
    "sinclair-zx81": {
        "id": 94,
        "name": "Sinclair ZX81",
        "igdb_id": 373,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "sinclair-zx81",
    },
    "sms": {
        "id": 85,
        "name": "Sega Master System",
        "igdb_id": 64,
        "tgdb_id": None,
        "ra_id": 11,
        "igdb_slug": "sms",
    },
    "snes": {
        "id": 74,
        "name": "Super Nintendo Entertainment System",
        "igdb_id": 19,
        "tgdb_id": None,
        "ra_id": 3,
        "igdb_slug": "snes",
    },
    "super-vision-8000": {
        "id": 97267,
        "name": "Bandai Super Vision 8000",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "switch": {
        "id": 233067,
        "name": "Nintendo Switch",
        "igdb_id": 130,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "switch",
    },
    "ti-82": {
        "id": 47973,
        "name": "Texas Instruments TI-82",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "ti-83": {
        "id": 243852,
        "name": "Texas Instruments TI-83",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "trs-80": {
        "id": 105,
        "name": "Tandy/RadioShack TRS-80",
        "igdb_id": 126,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "trs-80",
    },
    "trs-80-color-computer": {
        "id": 106,
        "name": "Tandy/RadioShack TRS-80 Color Computer",
        "igdb_id": 151,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "trs-80-color-computer",
    },
    "turbografx-16-slash-pc-engine-cd": {
        "id": 247350,
        "name": "Turbografx-16/PC Engine CD",
        "igdb_id": 150,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "turbografx-16-slash-pc-engine-cd",
    },
    "turbografx16--1": {
        "id": 245372,
        "name": "TurboGrafx-16/PC Engine",
        "igdb_id": 86,
        "tgdb_id": None,
        "ra_id": 8,
        "igdb_slug": "turbografx16--1",
    },
    "vectrex": {
        "id": 45,
        "name": "Vectrex",
        "igdb_id": 70,
        "tgdb_id": None,
        "ra_id": 46,
        "igdb_slug": "vectrex",
    },
    "vic-20": {
        "id": 4,
        "name": "Commodore VIC20",
        "igdb_id": 71,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "vic-20",
    },
    "virtualboy": {
        "id": 75,
        "name": "Nintendo Virtual Boy",
        "igdb_id": 87,
        "tgdb_id": None,
        "ra_id": 28,
        "igdb_slug": "virtualboy",
    },
    "watara-slash-quickshot-supervision": {
        "id": 244828,
        "name": "Watara Supervision",
        "igdb_id": 415,
        "tgdb_id": None,
        "ra_id": 63,
        "igdb_slug": "watara-slash-quickshot-supervision",
    },
    "wii": {
        "id": 76,
        "name": "Nintendo Wii",
        "igdb_id": 5,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "wii",
    },
    "wiiu": {
        "id": 77,
        "name": "Nintendo WiiU",
        "igdb_id": 41,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "wiiu",
    },
    "win": {
        "id": 233074,
        "name": "Microsoft Windows",
        "igdb_id": 6,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "win",
    },
    "wonderswan": {
        "id": 34,
        "name": "Bandai WonderSwan",
        "igdb_id": 57,
        "tgdb_id": None,
        "ra_id": 53,
        "igdb_slug": "wonderswan",
    },
    "wonderswan-color": {
        "id": 35,
        "name": "Bandai WonderSwan Color",
        "igdb_id": 123,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "wonderswan-color",
    },
    "x1": {
        "id": 89,
        "name": "Sharp X1",
        "igdb_id": 77,
        "tgdb_id": None,
        "ra_id": 64,
        "igdb_slug": "x1",
    },
    "xbox": {
        "id": 54696,
        "name": "Microsoft Xbox",
        "igdb_id": 11,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "xbox",
    },
    "xbox360": {
        "id": 54697,
        "name": "Microsoft Xbox 360",
        "igdb_id": 12,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "xbox360",
    },
    "xboxone": {
        "id": 161824,
        "name": "Microsoft Xbox One",
        "igdb_id": 49,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "xboxone",
    },
    "z88": {
        "id": 97718,
        "name": "Cambridge Computer Z88",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "zx80": {
        "id": 232985,
        "name": "Sinclair ZX80",
        "igdb_id": None,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "",
    },
    "zxs": {
        "id": 93,
        "name": "Sinclair ZX Spectrum",
        "igdb_id": 26,
        "tgdb_id": None,
        "ra_id": None,
        "igdb_slug": "zxs",
    },
}
