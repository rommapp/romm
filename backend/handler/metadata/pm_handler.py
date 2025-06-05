from enum import Enum
from typing import Final, NotRequired, Optional, TypedDict, cast

import httpx
import yarl
from fastapi import HTTPException, status
from logger.logger import log
from utils.context import ctx_httpx_client

from backend.config import PLAYMATCH_ENABLED

PM_ENABLED: Final = bool(PLAYMATCH_ENABLED)


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


class PlaymatchIdentifyRequest(TypedDict):
    fileName: str
    fileSize: int
    md5: NotRequired[str]
    sha1: NotRequired[str]


class PlaymatchExternalMetadata(TypedDict):
    automaticMatchReason: NotRequired[str]
    comment: NotRequired[str]
    failedMatchReason: NotRequired[str]
    manualMatchType: NotRequired[str]
    matchType: NotRequired[str]
    providerId: NotRequired[str]
    providerName: NotRequired[str]


class PlaymatchIdentifyResponse(TypedDict):
    id: str
    gameMatchType: GameMatchType
    externalMetadata: NotRequired[list[PlaymatchExternalMetadata]]


class PlaymatchHandler:
    """
    Handler for [Playmatch](https://github.com/RetroRealm/playmatch), a service for matching Roms by Hashes.
    """

    def __init__(self):
        self.base_url = "https://playmatch.retrorealm.dev/api"

    async def identify_rom(
        self, file_name: str, file_size: int, md5: Optional[str], sha1: Optional[str]
    ) -> Optional[int]:
        """
        Identify a ROM file using Playmatch API.

        :param file_name: The name of the ROM file.
        :param file_size: The size of the ROM file in bytes.
        :param md5: The MD5 hash of the ROM file, if available.
        :param sha1: The SHA1 hash of the ROM file, if available.
        :return: The IGDB provider ID if a match is found, otherwise None.
        :raises HTTPException: If the request fails or the service is unavailable.
        """
        if not PM_ENABLED:
            log.debug("Playmatch is not enabled, skipping identification.")
            return None

        url = f"{self.base_url}/identify/ids"

        try:
            response = await self._request(
                url,
                PlaymatchIdentifyRequest(
                    fileName=file_name, fileSize=file_size, md5=md5, sha1=sha1
                ),
            )
        except httpx.HTTPStatusError as e:
            # We silently fail if the service is unavailable as this should not block the rest of RomM.
            return None

        response_parsed = cast(PlaymatchIdentifyResponse, response)

        if response_parsed.get("gameMatchType") == GameMatchType.NoMatch:
            log.debug("No match found for the provided ROM file.")
            return None

        externalMetadata = response_parsed.get("externalMetadata", [])

        if len(externalMetadata) == 0:
            log.debug("No external metadata found for the matched ROM file.")
            return None

        for metadata in externalMetadata:
            if (
                metadata.get("providerName", "") == PlaymatchProvider.IGDB
                and metadata.get("providerId") is not None
            ):
                log.debug("Matched ROM file with IGDB provider.")
                return int(metadata.get("providerId"))

        log.debug("No IGDB match found in the external metadata.")

        return None  # No IGDB match found

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

        headers = {"user-agent": "RomM (https://github.com/rommapp/romm)"}

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
