import asyncio
import json
from enum import Enum
from typing import Final, NotRequired, TypedDict

import httpx
import yarl
from fastapi import HTTPException, status

from config import PLAYMATCH_API_ENABLED
from handler.metadata.base_handler import MetadataHandler
from logger.logger import log
from models.rom import Rom, RomFile
from utils import get_version
from utils.context import ctx_httpx_client
from utils.rate_limiter import RateLimiter

# Playmatch caps clients at 4 req/s per IP
PLAYMATCH_MAX_REQUESTS_PER_SECOND: Final[float] = 4
PLAYMATCH_MAX_REQUEST_ATTEMPTS: Final[int] = 2
_rate_limiter = RateLimiter(PLAYMATCH_MAX_REQUESTS_PER_SECOND)


class PlaymatchProvider(str, Enum):
    IGDB = "IGDB"
    STEAM_GRID_DB = "SteamGridDB"
    SCREEN_SCRAPER = "ScreenScraper"
    MOBY_GAMES = "MobyGames"
    LAUNCH_BOX = "LaunchBox"
    EMU_READY = "EmuReady"
    OPEN_VGDB = "OpenVGDB"


# Tag is the uppercased Playmatch MetadataProvider name.
# Playmatch parses it case-insensitively but spacing must match.
# Tags Playmatch doesn't yet know are kept so older RomM clients keep
# submitting the right tag once Playmatch adds support.
PLAYMATCH_TAG_TO_ATTR: Final[dict[str, str]] = {
    "IGDB": "igdb_id",
    "MOBYGAMES": "moby_id",
    "SCREENSCRAPER": "ss_id",
    "RETRO_ACHIEVEMENTS": "ra_id",
    "LAUNCHBOX": "launchbox_id",
    "HASHEOUS": "hasheous_id",
    "TGDB": "tgdb_id",
    "FLASHPOINT": "flashpoint_id",
    "HOWLONGTOBEAT": "hltb_id",
    "LIBRETRO": "libretro_id",
    "STEAMGRIDDB": "sgdb_id",
    "GAMELIST": "gamelist_id",
}

# Rom attrs the scan handler actually consumes from a Playmatch lookup.
# Other tags exist only for outbound suggestions.
PLAYMATCH_LOOKUP_ROM_ATTRS: frozenset[str] = frozenset(
    {"igdb_id", "moby_id", "ss_id", "launchbox_id", "sgdb_id"}
)

# MetadataSource values (StrEnum) for which Playmatch can return ids. Typed as
# strings so this module stays free of scan_handler imports. EmuReady and
# OpenVGDB are in Playmatch's enum but have no RomM counterpart yet.
PLAYMATCH_SUPPORTED_SOURCES: frozenset[str] = frozenset(
    {"igdb", "moby", "ss", "launchbox", "sgdb"}
)


class GameMatchType(str, Enum):
    SHA256 = "SHA256"
    SHA1 = "SHA1"
    MD5 = "MD5"
    FILE_NAME_AND_SIZE = "FileNameAndSize"
    NO_MATCH = "NoMatch"


class PlaymatchExternalMetadata(TypedDict):
    automaticMatchReason: NotRequired[str]
    comment: NotRequired[str]
    failedMatchReason: NotRequired[str]
    manualMatchType: NotRequired[str]
    matchType: NotRequired[str]
    providerId: NotRequired[str]
    providerName: NotRequired[str]


class PlaymatchRomMatch(TypedDict):
    igdb_id: int | None
    moby_id: int | None
    ss_id: int | None
    launchbox_id: int | None
    sgdb_id: int | None
    ra_id: int | None
    hasheous_id: int | None
    tgdb_id: int | None
    flashpoint_id: str | None
    hltb_id: int | None
    gamelist_id: str | None
    libretro_id: str | None


class PlaymatchHandler(MetadataHandler):
    """
    Handler for [Playmatch](https://github.com/RetroRealm/playmatch), a service for matching ROMs by Hashes.
    """

    def __init__(self):
        self.base_url = "https://playmatch.retrorealm.dev/api"
        self.identify_url = f"{self.base_url}/identify/ids"
        self.healthcheck_url = f"{self.base_url}/health"
        self.suggestion_url = f"{self.base_url}/suggestion/external/game"

    @classmethod
    def is_enabled(cls) -> bool:
        return PLAYMATCH_API_ENABLED

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            response = await self._request(self.healthcheck_url, {})
        except Exception as e:
            log.error("Error checking Playmatch API: %s", e)
            return False

        return bool(response)

    async def _request(self, url: str, query: dict) -> dict:
        """
        Sends a Request to Playmatch API.

        :param url: The API endpoint URL.
        :param query: A dictionary containing the query parameters.
        :return: A dictionary with the json result.
        :raises HTTPException: If the request fails or the service is unavailable.
        """
        httpx_client = ctx_httpx_client.get()

        filtered_query = {
            key: value
            for key, value in query.items()
            if value is not None and value != ""  # drop None and ""
        }

        url_with_query = yarl.URL(url).update_query(**filtered_query)

        log.debug(
            "API request: URL=%s, Timeout=%s",
            url_with_query,
            60,
        )

        headers = {"user-agent": f"RomM/{get_version()}"}

        for attempt in range(PLAYMATCH_MAX_REQUEST_ATTEMPTS):
            await _rate_limiter.acquire()
            try:
                res = await httpx_client.get(
                    str(url_with_query), headers=headers, timeout=60
                )
                res.raise_for_status()
                return res.json()
            except (
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.ReadTimeout,
            ) as exc:
                if (
                    attempt == 0
                    and isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                ):
                    log.warning("Playmatch: rate limit hit, retrying after 2s")
                    await asyncio.sleep(2)
                    continue
                log.warning(
                    "Connection error: can't connect to Playmatch", exc_info=True
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Can't connect to Playmatch, check your internet connection",
                ) from exc
            except json.JSONDecodeError as exc:
                log.error("Error decoding JSON response from Playmatch: %s", exc)
                return {}

        return {}

    async def lookup_rom(self, files: list[RomFile]) -> PlaymatchRomMatch:
        """
        Identify a ROM file using Playmatch API.

        :param rom_attrs: A dictionary containing the ROM attributes.
        :return: A PlaymatchRomMatch with the matched IDs, or an empty match if the
            lookup fails. Playmatch is best-effort and never raises to the caller.
        """
        fallback_rom = PlaymatchRomMatch(
            igdb_id=None,
            moby_id=None,
            ss_id=None,
            launchbox_id=None,
            sgdb_id=None,
            ra_id=None,
            hasheous_id=None,
            tgdb_id=None,
            flashpoint_id=None,
            hltb_id=None,
            gamelist_id=None,
            libretro_id=None,
        )

        if not self.is_enabled():
            return fallback_rom

        first_file = next(
            (file for file in files if file.file_size_bytes > 0),
            None,
        )
        if first_file is None:
            return fallback_rom

        try:
            response = await self._request(
                self.identify_url,
                {
                    "fileName": first_file.file_name,
                    "fileSize": first_file.file_size_bytes,
                    "md5": first_file.md5_hash,
                    "sha1": first_file.sha1_hash,
                },
            )
        except Exception as exc:
            # We silently fail if the service is unavailable as this should not block the rest of RomM.
            log.warning("Playmatch lookup failed, skipping: %s", exc)
            return fallback_rom

        game_match_type = response.get("gameMatchType", None)
        if game_match_type == GameMatchType.NO_MATCH:
            log.debug("No match found for the provided ROM file.")
            return fallback_rom

        externalMetadata = response.get("externalMetadata", [])
        if len(externalMetadata) == 0:
            log.debug("No external metadata found for the matched ROM file.")
            return fallback_rom

        result = fallback_rom
        for metadata in externalMetadata:
            provider_name = metadata.get("providerName", None)
            provider_game_id = metadata.get("providerId", None)
            if not provider_name or provider_game_id is None:
                continue

            attr = PLAYMATCH_TAG_TO_ATTR.get(provider_name.upper())
            if not attr or attr not in PLAYMATCH_LOOKUP_ROM_ATTRS:
                continue

            try:
                parsed_id = int(provider_game_id)
            except (TypeError, ValueError):
                log.debug(
                    "Playmatch returned non-int ID for %s: %r",
                    provider_name,
                    provider_game_id,
                )
                continue

            log.debug("Playmatch found %s match with id: %s", provider_name, parsed_id)
            result[attr] = parsed_id  # trunk-ignore(mypy/literal-required)

        return result

    @staticmethod
    def is_manual_match(form_fields_set: set[str]) -> bool:
        """True if the submitted form contains any Playmatch-tracked provider id field."""
        return any(attr in form_fields_set for attr in PLAYMATCH_TAG_TO_ATTR.values())

    async def submit_manual_match_suggestion(self, rom: Rom) -> None:
        """
        Fire-and-forget suggestion POST.
        No-ops if disabled or no provider IDs are set.
        """
        try:
            if not self.is_enabled():
                return

            mappings = [
                {"provider": tag, "providerId": str(getattr(rom, attr))}
                for tag, attr in PLAYMATCH_TAG_TO_ATTR.items()
                if getattr(rom, attr, None)
            ]
            if not mappings:
                return

            first_file = next(
                (f for f in rom.files if f.file_size_bytes > 0),
                None,
            )
            if first_file is not None:
                md5 = first_file.md5_hash
                sha1 = first_file.sha1_hash
                file_name = first_file.file_name
                file_size: int | None = first_file.file_size_bytes
            else:
                md5 = rom.md5_hash
                sha1 = rom.sha1_hash
                file_name = rom.fs_name
                file_size = rom.fs_size_bytes or None

            payload = {
                "md5": md5,
                "sha1": sha1,
                "sha256": None,
                "fileName": file_name,
                "fileSize": file_size,
                "mappings": mappings,
            }

            httpx_client = ctx_httpx_client.get()
            await _rate_limiter.acquire()
            res = await httpx_client.post(
                self.suggestion_url,
                json=payload,
                headers={"user-agent": f"RomM/{get_version()}"},
                timeout=30,
            )
            res.raise_for_status()
        except Exception:
            log.debug("Playmatch match suggestion failed (ignored)", exc_info=True)
