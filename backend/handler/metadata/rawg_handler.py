import re
from typing import Final, NotRequired, TypedDict

import httpx
import pydash
from config import RAWG_API_KEY
from logger.logger import log
from utils.context import ctx_httpx_client

from .base_handler import BaseRom, MetadataHandler
from .base_handler import UniversalPlatformSlug as UPS

# Filename tag like (rawg-12345), matching the convention the other handlers
# use so an operator can pin a match by hand.
RAWG_TAG_REGEX = re.compile(r"\(rawg-(\d+)\)", re.IGNORECASE)

RAWG_API_URL: Final = "https://api.rawg.io/api"


class RAWGPlatform(TypedDict):
    slug: str
    rawg_slug: str | None
    name: NotRequired[str]


class RAWGMetadata(TypedDict):
    rawg_score: str
    genres: list[str]
    esrb_rating: str
    developers: list[str]
    publishers: list[str]
    first_release_date: int | None


class RAWGRom(BaseRom):
    rawg_id: int | None
    rawg_metadata: NotRequired[RAWGMetadata]


def extract_metadata_from_rawg_rom(rom: dict) -> RAWGMetadata:
    return RAWGMetadata(
        {
            "rawg_score": str(rom.get("rating", "")),
            "genres": [g["name"] for g in rom.get("genres", []) if g.get("name")],
            "esrb_rating": pydash.get(rom, "esrb_rating.name", "") or "",
            "developers": [
                d["name"] for d in rom.get("developers", []) or [] if d.get("name")
            ],
            "publishers": [
                p["name"] for p in rom.get("publishers", []) or [] if p.get("name")
            ],
            "first_release_date": rom.get("released_timestamp"),
        }
    )


# RomM's universal slug -> RAWG's platform slug.
#
# Only mapped where RAWG actually has the platform. RAWG is a modern and PC
# focused database, so a good deal of the retro catalogue is simply absent --
# mapping those to a near neighbour would return confidently wrong matches,
# which is worse than returning nothing.
SLUG_TO_RAWG_SLUG: dict[UPS, str] = {
    UPS._3DO: "3do",
    UPS.AMIGA: "commodore-amiga",
    UPS.ANDROID: "android",
    UPS.ATARI2600: "atari-2600",
    UPS.ATARI5200: "atari-5200",
    UPS.ATARI7800: "atari-7800",
    UPS.ATARI_ST: "atari-st",
    UPS.NEW_NINTENDON3DS: "nintendo-3ds",
    UPS.DC: "dreamcast",
    UPS.DOS: "pc",
    UPS.GB: "game-boy",
    UPS.GBA: "game-boy-advance",
    UPS.GBC: "game-boy-color",
    UPS.GENESIS: "genesis",
    UPS.IOS: "ios",
    UPS.JAGUAR: "jaguar",
    UPS.LINUX: "linux",
    UPS.LYNX: "atari-lynx",
    UPS.MAC: "macos",
    UPS.N64: "nintendo-64",
    UPS.NDS: "nintendo-ds",
    UPS.NEO_GEO_CD: "neogeo",
    UPS.NES: "nes",
    UPS.NGC: "gamecube",
    UPS.PS2: "playstation2",
    UPS.PS3: "playstation3",
    UPS.PS4: "playstation4",
    UPS.PS5: "playstation5",
    UPS.PSP: "psp",
    UPS.PSVITA: "ps-vita",
    UPS.PSX: "playstation1",
    UPS.SATURN: "sega-saturn",
    UPS.SEGA32: "sega-32x",
    UPS.SEGACD: "sega-cd",
    UPS.SMS: "sega-master-system",
    UPS.SNES: "snes",
    UPS.SWITCH: "nintendo-switch",
    UPS.WII: "wii",
    UPS.WIIU: "wii-u",
    UPS.WIN: "pc",
    UPS.XBOX: "xbox-old",
    UPS.XBOX360: "xbox360",
    UPS.XBOXONE: "xone",
    UPS.N3DS: "nintendo-3ds",
}


class RAWGHandler(MetadataHandler):
    """
    Handler for RAWG.io, a large general-purpose video game database.

    RAWG is strongest on modern and PC titles and thinner on the retro
    catalogue than IGDB, MobyGames or ScreenScraper, so it is offered as an
    additional source rather than a replacement for any of them. Its free tier
    is generous, which makes it a reasonable first source for anybody who has
    not obtained keys elsewhere.
    """

    def __init__(self) -> None:
        self.search_endpoint = f"{RAWG_API_URL}/games"
        self.min_similarity_score: Final = 0.7

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(RAWG_API_KEY)

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            response = await self._request(self.search_endpoint, {"page_size": 1})
        except Exception as e:
            log.error("Error checking RAWG API: %s", e)
            return False

        return bool(response)

    @staticmethod
    def extract_rawg_id_from_filename(fs_name: str) -> int | None:
        """Extract a RAWG id from a filename tag like (rawg-12345)."""
        match = RAWG_TAG_REGEX.search(fs_name)
        return int(match.group(1)) if match else None

    async def _request(self, url: str, params: dict) -> dict:
        httpx_client = ctx_httpx_client.get()
        try:
            res = await httpx_client.get(
                url,
                params={**params, "key": RAWG_API_KEY},
                timeout=120,
            )
            res.raise_for_status()
            return res.json()
        except httpx.NetworkError as exc:
            log.critical("Connection error: can't connect to RAWG", exc_info=True)
            raise exc
        except httpx.HTTPStatusError as err:
            # RAWG answers 401 for a bad key and 404 for an unknown id. Neither
            # is a reason to fail a whole scan -- an empty result lets the next
            # handler in the chain try.
            if err.response.status_code == 401:
                log.error("RAWG rejected the API key")
            return {}
        except httpx.TimeoutException:
            log.debug("Request to RAWG timed out")
            return {}

    def get_platform(self, slug: str) -> RAWGPlatform:
        platform = SLUG_TO_RAWG_SLUG.get(slug.lower(), None)  # type: ignore[arg-type]
        if not platform:
            return RAWGPlatform(rawg_slug=None, slug=slug)

        return RAWGPlatform(rawg_slug=platform, slug=slug)

    async def get_rom(self, fs_name: str, platform_rawg_slug: str) -> RAWGRom:
        fallback_rom = RAWGRom(rawg_id=None)

        if not self.is_enabled():
            return fallback_rom

        # A pinned id in the filename is an explicit instruction and beats any
        # amount of searching.
        rawg_id = self.extract_rawg_id_from_filename(fs_name)
        if rawg_id:
            return await self.get_rom_by_id(rawg_id)

        if not platform_rawg_slug:
            return fallback_rom

        search_term = self.normalize_search_term(fs_name)
        if not search_term:
            return fallback_rom

        res = await self._request(
            self.search_endpoint,
            {
                "search": search_term,
                "platforms_slug": platform_rawg_slug,
                "page_size": 10,
            },
        )
        results = res.get("results", []) or []
        if not results:
            return fallback_rom

        games_by_name = {game["name"]: game for game in results if game.get("name")}
        best_match, best_score = self.find_best_match(
            search_term,
            list(games_by_name.keys()),
            self.min_similarity_score,
        )
        if not best_match:
            return fallback_rom

        log.debug(
            f"Found RAWG match for '{search_term}' -> '{best_match}' "
            f"(score: {best_score:.3f})"
        )
        return await self.get_rom_by_id(games_by_name[best_match]["id"])

    async def get_rom_by_id(self, rawg_id: int) -> RAWGRom:
        if not self.is_enabled():
            return RAWGRom(rawg_id=None)

        res = await self._request(f"{self.search_endpoint}/{rawg_id}", {})
        if not res or not res.get("name"):
            return RAWGRom(rawg_id=None)

        return RAWGRom(
            rawg_id=rawg_id,
            name=res["name"],
            summary=res.get("description_raw", "") or "",
            url_cover=self.normalize_cover_url(res.get("background_image", "") or ""),
            url_screenshots=[
                self.normalize_cover_url(shot["image"])
                for shot in (res.get("short_screenshots") or [])
                if shot.get("image")
            ],
            rawg_metadata=extract_metadata_from_rawg_rom(res),
        )

    async def get_matched_roms_by_name(
        self, search_term: str, platform_rawg_slug: str | None
    ) -> list[RAWGRom]:
        """Candidates for a manual match, unfiltered by similarity.

        The operator is choosing, so a low-scoring result is theirs to reject
        rather than something to hide from them.
        """
        if not self.is_enabled():
            return []

        params: dict = {"search": search_term, "page_size": 20}
        if platform_rawg_slug:
            params["platforms_slug"] = platform_rawg_slug

        res = await self._request(self.search_endpoint, params)
        return [
            RAWGRom(
                rawg_id=game["id"],
                name=game["name"],
                summary="",
                url_cover=self.normalize_cover_url(
                    game.get("background_image", "") or ""
                ),
                url_screenshots=[
                    self.normalize_cover_url(shot["image"])
                    for shot in (game.get("short_screenshots") or [])
                    if shot.get("image")
                ],
                rawg_metadata=extract_metadata_from_rawg_rom(game),
            )
            for game in (res.get("results") or [])
            if game.get("id") and game.get("name")
        ]
