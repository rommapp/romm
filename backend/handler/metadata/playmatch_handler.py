from enum import Enum
from typing import NotRequired, TypedDict

import httpx
import yarl
from config import PLAYMATCH_API_ENABLED
from fastapi import HTTPException, status
from logger.logger import log
from utils import get_version
from utils.context import ctx_httpx_client


class PlaymatchProvider(str, Enum):
    """
    Enum for Playmatch Providers.
    """

    IGDB = "IGDB"


class GameMatchType(str, Enum):
    """
    Enum for Game Match Types.
    """

    SHA256 = "SHA256"
    SHA1 = "SHA1"
    MD5 = "MD5"
    FileNameAndSize = "FileNameAndSize"
    NoMatch = "NoMatch"


class PlaymatchExternalMetadata(TypedDict):
    automaticMatchReason: NotRequired[str]
    comment: NotRequired[str]
    failedMatchReason: NotRequired[str]
    manualMatchType: NotRequired[str]
    matchType: NotRequired[str]
    providerId: NotRequired[str]
    providerName: NotRequired[str]


class PlaymatchRomMatch(TypedDict):
    provider: PlaymatchProvider
    provider_game_id: int
    game_match_type: GameMatchType


class PlaymatchHandler:
    """
    Handler for [Playmatch](https://github.com/RetroRealm/playmatch), a service for matching Roms by Hashes.
    """

    def __init__(self):
        self.base_url = "https://playmatch.retrorealm.dev/api"

    async def lookup_rom(self, rom_attrs: dict) -> list[PlaymatchRomMatch]:
        """
        Identify a ROM file using Playmatch API.

        :param file_name: The name of the ROM file.
        :param file_size: The size of the ROM file in bytes.
        :param md5: The MD5 hash of the ROM file, if available.
        :param sha1: The SHA1 hash of the ROM file, if available.
        :return: The IGDB provider ID if a match is found, otherwise None.
        :raises HTTPException: If the request fails or the service is unavailable.
        """
        if not PLAYMATCH_API_ENABLED:
            return []

        url = f"{self.base_url}/identify/ids"

        try:
            response = await self._request(
                url,
                {
                    "fileName": rom_attrs["file_name"],
                    "fileSize": rom_attrs["file_size_bytes"],
                    "md5": rom_attrs["md5_hash"],
                    "sha1": rom_attrs["sha1_hash"],
                },
            )
        except httpx.HTTPStatusError:
            # We silently fail if the service is unavailable as this should not block the rest of RomM.
            return []

        game_match_type = response.get("gameMatchType", None)
        if game_match_type == GameMatchType.NoMatch:
            log.debug("No match found for the provided ROM file.")
            return []

        externalMetadata = response.get("externalMetadata", [])

        if len(externalMetadata) == 0:
            log.debug("No external metadata found for the matched ROM file.")
            return []

        rom_matches: list[PlaymatchRomMatch] = []

        for metadata in externalMetadata:
            provider_name = metadata.get("providerName", None)
            provider_game_id = metadata.get("providerId", None)
            if provider_name == PlaymatchProvider.IGDB and provider_game_id is not None:
                log.debug("Found IGDB match with IGDB ID: %s", provider_game_id)
                rom_matches.append(
                    PlaymatchRomMatch(
                        provider=PlaymatchProvider.IGDB,
                        provider_game_id=int(provider_game_id),
                        game_match_type=GameMatchType(game_match_type),
                    )
                )

        return rom_matches

    async def _request(self, url: str, query: dict, timeout=60) -> dict:
        """
        Sends a Request to Playmatch API.

        :param url: The API endpoint URL.
        :param query: A dictionary containing the query parameters.
        :param timeout: The timeout for the request in seconds.
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
            timeout,
        )

        headers = {
            "user-agent": "RomM/" + get_version() + " (https://github.com/rommapp/romm)"
        }

        try:
            res = await httpx_client.get(
                str(url_with_query), headers=headers, timeout=timeout
            )
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            log.warning("Connection error: can't connect to Playmatch", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Playmatch, check your internet connection",
            ) from e
