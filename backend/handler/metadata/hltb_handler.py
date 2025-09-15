import json
from typing import Final, NotRequired, TypedDict

import httpx
from fastapi import HTTPException, status

from config import HLTB_API_ENABLED
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.logger import log
from utils import get_version
from utils.context import ctx_httpx_client

from .base_handler import BaseRom, MetadataHandler


class HLTBPlatform(TypedDict):
    slug: str
    name: NotRequired[str]


class HLTBGame(TypedDict):
    game_id: int
    game_name: str
    game_name_date: int
    game_alias: str
    game_type: str
    game_image: str
    comp_lvl_combine: int
    comp_lvl_sp: int
    comp_lvl_co: int
    comp_lvl_mp: int
    comp_main: int
    comp_plus: int
    comp_100: int
    comp_all: int
    comp_main_count: int
    comp_plus_count: int
    comp_100_count: int
    comp_all_count: int
    invested_co: int
    invested_mp: int
    invested_co_count: int
    invested_mp_count: int
    count_comp: int
    count_speedrun: int
    count_backlog: int
    count_review: int
    review_score: int
    count_playing: int
    count_retired: int
    profile_platform: str
    profile_popular: int
    release_world: int


class HLTBSearchResponse(TypedDict):
    color: str
    title: str
    category: str
    count: int
    pageCurrent: int
    pageTotal: int
    pageSize: int
    data: list[HLTBGame]
    userData: list
    displayModifier: str | None


class HLTBMetadata(TypedDict):
    main_story: NotRequired[int]
    main_story_count: NotRequired[int]
    main_plus_extra: NotRequired[int]
    main_plus_extra_count: NotRequired[int]
    completionist: NotRequired[int]
    completionist_count: NotRequired[int]
    all_styles: NotRequired[int]
    all_styles_count: NotRequired[int]
    release_year: NotRequired[int]
    review_score: NotRequired[int]
    review_count: NotRequired[int]
    popularity: NotRequired[int]
    completions: NotRequired[int]


class HLTBPriceCheckRequest(TypedDict):
    steamId: int
    itchId: int


class HLTBStorePrice(TypedDict):
    id: NotRequired[int]
    url: NotRequired[str]
    symbol: NotRequired[str]
    basePrice: NotRequired[float]
    price: NotRequired[float]
    onSale: NotRequired[bool]
    discount: NotRequired[str]


class HLTBPriceCheckResponse(TypedDict):
    region: str
    gog: HLTBStorePrice
    steam: HLTBStorePrice
    itch: HLTBStorePrice


class HLTBRom(BaseRom):
    hltb_id: int | None
    hltb_metadata: NotRequired[HLTBMetadata]


def extract_hltb_metadata(game: HLTBGame) -> HLTBMetadata:
    """Extract metadata from HLTB game data."""
    metadata = HLTBMetadata()

    # Convert times from centiseconds to seconds (HLTB stores times in centiseconds)
    if game.get("comp_main") and game["comp_main"] > 0:
        metadata["main_story"] = game["comp_main"] // 100

    if game.get("comp_main_count") and game["comp_main_count"] > 0:
        metadata["main_story_count"] = game["comp_main_count"]

    if game.get("comp_plus") and game["comp_plus"] > 0:
        metadata["main_plus_extra"] = game["comp_plus"] // 100

    if game.get("comp_plus_count") and game["comp_plus_count"] > 0:
        metadata["main_plus_extra_count"] = game["comp_plus_count"]

    if game.get("comp_100") and game["comp_100"] > 0:
        metadata["completionist"] = game["comp_100"] // 100

    if game.get("comp_100_count") and game["comp_100_count"] > 0:
        metadata["completionist_count"] = game["comp_100_count"]

    if game.get("comp_all") and game["comp_all"] > 0:
        metadata["all_styles"] = game["comp_all"] // 100

    if game.get("comp_all_count") and game["comp_all_count"] > 0:
        metadata["all_styles_count"] = game["comp_all_count"]

    # Extract platforms
    # if game.get("profile_platform"):
    #     platforms = [p.strip() for p in game["profile_platform"].split(",")]
    #     metadata["platforms"] = platforms

    # Extract release year
    if game.get("release_world") and game["release_world"] > 0:
        metadata["release_year"] = game["release_world"]

    # Extract review score
    if game.get("review_score") and game["review_score"] > 0:
        metadata["review_score"] = game["review_score"]

    if game.get("count_review") and game["count_review"] > 0:
        metadata["review_count"] = game["count_review"]

    # Extract popularity
    if game.get("profile_popular") and game["profile_popular"] > 0:
        metadata["popularity"] = game["profile_popular"]

    if game.get("count_comp") and game["count_comp"] > 0:
        metadata["completions"] = game["count_comp"]

    return metadata


class HowLongToBeatHandler(MetadataHandler):
    """
    Handler for HowLongToBeat, a service that provides game completion times.
    """

    def __init__(self) -> None:
        self.base_url = "https://howlongtobeat.com"
        self.search_url = f"{self.base_url}/api/seek/28b235595e8e894c"
        self.min_similarity_score: Final = 0.85

    @classmethod
    def is_enabled(cls) -> bool:
        return HLTB_API_ENABLED

    async def _request(self, url: str, payload: dict) -> dict:
        """
        Sends a POST request to HowLongToBeat API.

        :param url: The API endpoint URL.
        :param payload: A dictionary containing the request payload.
        :return: A dictionary with the json result.
        :raises HTTPException: If the request fails or the service is unavailable.
        """
        httpx_client = ctx_httpx_client.get()

        headers = {
            "Content-Type": "application/json",
            "Referer": "https://howlongtobeat.com",
            "User-Agent": f"RomM/{get_version()}",
            "Accept-Encoding": "gzip, deflate",
        }

        log.debug(
            "HowLongToBeat API request: URL=%s, Headers=%s, Payload=%s, Timeout=%s",
            url,
            headers,
            payload,
            60,
        )

        try:
            res = await httpx_client.post(
                url, json=payload, headers=headers, timeout=60
            )
            res.raise_for_status()
            return res.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            log.warning(
                "Connection error: can't connect to HowLongToBeat API", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to HowLongToBeat API, check your internet connection",
            ) from exc
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from HowLongToBeat API: %s", exc)
            return {}

    async def search_games(
        self, search_term: str, platform_slug: str
    ) -> list[HLTBGame]:
        """
        Search for games in HowLongToBeat database.

        :param search_term: The search term to look for.
        :return: A list of HLTBGame objects.
        """

        platform_name = self.get_platform(platform_slug).get("name", "")

        try:
            payload = {
                "searchType": "games",
                "searchTerms": [search_term],
                "searchPage": 1,
                "size": 20,
                "searchOptions": {
                    "games": {
                        "userId": 0,
                        "platform": platform_name,
                        "sortCategory": "popular",
                        "rangeCategory": "main",
                        "rangeTime": {"min": None, "max": None},
                        "gameplay": {
                            "perspective": "",
                            "flow": "",
                            "genre": "",
                            "difficulty": "",
                        },
                        "rangeYear": {"min": "", "max": ""},
                        "modifier": "",
                    },
                    "users": {"sortCategory": "postcount"},
                    "lists": {"sortCategory": "follows"},
                    "filter": "",
                    "sort": 0,
                    "randomizer": 0,
                },
                "useCache": True,
            }

            response = await self._request(self.search_url, payload)

            if not response or "data" not in response:
                return []

            games_data = response["data"]
            if not isinstance(games_data, list):
                return []

            games = []
            for game_data in games_data:
                if isinstance(game_data, dict) and "game_id" in game_data:
                    # Create HLTBGame with all required fields, using defaults for missing ones
                    hltb_game = HLTBGame(
                        game_id=game_data.get("game_id", 0),
                        game_name=game_data.get("game_name", ""),
                        game_name_date=game_data.get("game_name_date", 0),
                        game_alias=game_data.get("game_alias", ""),
                        game_type=game_data.get("game_type", ""),
                        game_image=game_data.get("game_image", ""),
                        comp_lvl_combine=game_data.get("comp_lvl_combine", 0),
                        comp_lvl_sp=game_data.get("comp_lvl_sp", 0),
                        comp_lvl_co=game_data.get("comp_lvl_co", 0),
                        comp_lvl_mp=game_data.get("comp_lvl_mp", 0),
                        comp_main=game_data.get("comp_main", 0),
                        comp_plus=game_data.get("comp_plus", 0),
                        comp_100=game_data.get("comp_100", 0),
                        comp_all=game_data.get("comp_all", 0),
                        comp_main_count=game_data.get("comp_main_count", 0),
                        comp_plus_count=game_data.get("comp_plus_count", 0),
                        comp_100_count=game_data.get("comp_100_count", 0),
                        comp_all_count=game_data.get("comp_all_count", 0),
                        invested_co=game_data.get("invested_co", 0),
                        invested_mp=game_data.get("invested_mp", 0),
                        invested_co_count=game_data.get("invested_co_count", 0),
                        invested_mp_count=game_data.get("invested_mp_count", 0),
                        count_comp=game_data.get("count_comp", 0),
                        count_speedrun=game_data.get("count_speedrun", 0),
                        count_backlog=game_data.get("count_backlog", 0),
                        count_review=game_data.get("count_review", 0),
                        review_score=game_data.get("review_score", 0),
                        count_playing=game_data.get("count_playing", 0),
                        count_retired=game_data.get("count_retired", 0),
                        profile_platform=game_data.get("profile_platform", ""),
                        profile_popular=game_data.get("profile_popular", 0),
                        release_world=game_data.get("release_world", 0),
                    )
                    games.append(hltb_game)
            return games

        except Exception as exc:
            log.error("Error searching HowLongToBeat API: %s", exc)
            return []

    def get_platform(self, slug: str) -> HLTBPlatform:
        if slug not in HLTB_PLATFORM_LIST:
            return HLTBPlatform(slug=slug)

        platform = HLTB_PLATFORM_LIST[UPS(slug)]

        return HLTBPlatform(
            slug=slug,
            name=platform["name"],
        )

    async def get_rom(self, fs_name: str, platform_slug: str) -> HLTBRom:
        """
        Get ROM information from HowLongToBeat.

        :param fs_name: The filename to search for.
        :param platform_slug: The platform slug (not used for HLTB but required by interface).
        :return: A HLTBRom object.
        """
        from handler.filesystem import fs_rom_handler

        if not HLTB_API_ENABLED:
            return HLTBRom(hltb_id=None)

        # Normalize the search term
        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        search_term = self.normalize_search_term(search_term, remove_punctuation=False)

        # Search for games
        games = await self.search_games(search_term, platform_slug)

        if not games:
            log.debug(f"Could not find '{search_term}' on HowLongToBeat")
            return HLTBRom(hltb_id=None)

        # Find the best match
        game_names = [game["game_name"] for game in games]
        best_match, best_score = self.find_best_match(
            search_term,
            game_names,
            min_similarity_score=self.min_similarity_score,
        )

        if best_match:
            # Find the game data for the best match
            best_game = next(
                (game for game in games if game["game_name"] == best_match), None
            )

            if best_game:
                log.debug(
                    f"Found HowLongToBeat match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
                )

                # Build cover URL if image is available
                cover_url = ""
                if best_game.get("game_image"):
                    cover_url = (
                        f"https://howlongtobeat.com/games/{best_game['game_image']}"
                    )

                return HLTBRom(
                    hltb_id=best_game["game_id"],
                    name=best_game["game_name"],
                    url_cover=cover_url,
                    hltb_metadata=extract_hltb_metadata(best_game),
                )

        log.debug(f"No good match found for '{search_term}' on HowLongToBeat")
        return HLTBRom(hltb_id=None)

    async def get_matched_roms_by_name(
        self, fs_name: str, platform_slug: str
    ) -> list[HLTBRom]:
        """
        Get ROM information by name from HowLongToBeat.
        """
        from handler.filesystem import fs_rom_handler

        if not HLTB_API_ENABLED:
            return []

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        search_term = self.normalize_search_term(search_term, remove_punctuation=False)

        games = await self.search_games(search_term, platform_slug)

        roms = []
        for game in games:
            # Build cover URL if image is available
            cover_url = ""
            if game.get("game_image"):
                cover_url = f"https://howlongtobeat.com/games/{game['game_image']}"

            roms.append(
                HLTBRom(
                    hltb_id=game["game_id"],
                    name=game["game_name"],
                    url_cover=cover_url,
                    hltb_metadata=extract_hltb_metadata(game),
                )
            )

        return roms

    async def get_rom_by_id(self, hltb_id: int) -> HLTBRom:
        """
        Get ROM information by HowLongToBeat ID.
        Note: HLTB doesn't have a direct "get by ID" endpoint,
        so this method searches by the game name if we can find it.

        :param hltb_id: The HowLongToBeat game ID.
        :return: A HLTBRom object.
        """
        if not HLTB_API_ENABLED:
            return HLTBRom(hltb_id=None)

        if not hltb_id:
            return HLTBRom(hltb_id=None)

        # Unfortunately, HLTB doesn't provide a direct "get by ID" endpoint
        # This is a limitation of their API - we would need to search and filter
        # In practice, this method might not be very useful for HLTB
        log.debug(
            f"get_rom_by_id not fully supported for HowLongToBeat (ID: {hltb_id})"
        )
        return HLTBRom(hltb_id=hltb_id)

    async def price_check(
        self, hltb_id: int, steam_id: int = 0, itch_id: int = 0
    ) -> HLTBPriceCheckResponse | None:
        """
        Check prices for a game on different platforms.

        :param hltb_id: The HowLongToBeat game ID.
        :param steam_id: The Steam app ID (optional).
        :param itch_id: The Itch.io game ID (optional).
        :return: A HLTBPriceCheckResponse object or None if the request fails.
        """
        if not HLTB_API_ENABLED:
            log.debug("HowLongToBeat API is disabled")
            return None

        if not hltb_id:
            log.debug("No HLTB ID provided for price check")
            return None

        price_check_url = f"{self.base_url}/api/price-checks/{hltb_id}"

        payload = {"steamId": steam_id, "itchId": itch_id}

        try:
            log.debug(
                "HowLongToBeat price check request: HLTB_ID=%s, Steam_ID=%s, Itch_ID=%s",
                hltb_id,
                steam_id,
                itch_id,
            )

            response = await self._request(price_check_url, payload)

            if not response:
                log.debug(f"No price data returned for HLTB ID: {hltb_id}")
                return None

            # Validate response structure
            if not isinstance(response, dict) or "region" not in response:
                log.warning(
                    f"Invalid price check response format for HLTB ID: {hltb_id}"
                )
                return None

            # Create typed response with defaults for missing store data
            price_response = HLTBPriceCheckResponse(
                region=response.get("region", ""),
                gog=response.get("gog", {}),
                steam=response.get("steam", {}),
                itch=response.get("itch", {}),
            )

            log.debug(f"Successfully retrieved price data for HLTB ID: {hltb_id}")
            return price_response

        except Exception as exc:
            log.error("Error fetching price data from HowLongToBeat API: %s", exc)
            return None


class SlugToHLTBPlatform(TypedDict):
    name: str
    count: int


HLTB_PLATFORM_LIST: dict[UPS, SlugToHLTBPlatform] = {
    UPS._3DO: {"name": "3DO", "count": 159},
    UPS.ACORN_ARCHIMEDES: {"name": "Acorn Archimedes", "count": 65},
    UPS.LUNA: {"name": "Amazon Luna", "count": 42},
    UPS.AMIGA: {"name": "Amiga", "count": 984},
    UPS.AMIGA_CD32: {"name": "Amiga CD32", "count": 91},
    UPS.ACPC: {"name": "Amstrad CPC", "count": 660},
    UPS.APPLEII: {"name": "Apple II", "count": 292},
    UPS.ARCADE: {"name": "Arcade", "count": 2010},
    UPS.ATARI2600: {"name": "Atari 2600", "count": 562},
    UPS.ATARI5200: {"name": "Atari 5200", "count": 63},
    UPS.ATARI7800: {"name": "Atari 7800", "count": 54},
    UPS.ATARI8BIT: {"name": "Atari 8-bit Family", "count": 259},
    UPS.JAGUAR: {"name": "Atari Jaguar", "count": 64},
    UPS.ATARI_JAGUAR_CD: {"name": "Atari Jaguar CD", "count": 14},
    UPS.LYNX: {"name": "Atari Lynx", "count": 87},
    UPS.ATARI_ST: {"name": "Atari ST", "count": 531},
    UPS.BBCMICRO: {"name": "BBC Micro", "count": 170},
    UPS.BROWSER: {"name": "Browser", "count": 1463},
    UPS.COLECOVISION: {"name": "ColecoVision", "count": 105},
    UPS.C64: {"name": "Commodore 64", "count": 1227},
    UPS.CPET: {"name": "Commodore PET", "count": 11},
    UPS.C_PLUS_4: {"name": "Commodore VIC-20", "count": 52},
    UPS.DC: {"name": "Dreamcast", "count": 465},
    UPS.EVERCADE: {"name": "Evercade", "count": 10},
    UPS.FM_TOWNS: {"name": "FM Towns", "count": 190},
    UPS.FM_7: {"name": "FM-7", "count": 58},
    UPS.G_AND_W: {"name": "Game & Watch", "count": 48},
    UPS.GB: {"name": "Game Boy", "count": 960},
    UPS.GBA: {"name": "Game Boy Advance", "count": 1236},
    UPS.GBC: {"name": "Game Boy Color", "count": 833},
    UPS.GEAR_VR: {"name": "Gear VR", "count": 4},
    UPS.GIZMONDO: {"name": "Gizmondo", "count": 14},
    UPS.STADIA: {"name": "Google Stadia", "count": 242},
    UPS.INTELLIVISION: {"name": "Intellivision", "count": 121},
    UPS.DVD_PLAYER: {"name": "Interactive Movie", "count": 35},
    UPS.LINUX: {"name": "Linux", "count": 4761},
    UPS.MSX: {"name": "MSX", "count": 436},
    UPS.MAC: {"name": "Mac", "count": 6445},
    UPS.OCULUS_QUEST: {"name": "Meta Quest", "count": 411},
    UPS.MOBILE: {"name": "Mobile", "count": 5588},
    UPS.NGAGE: {"name": "N-Gage", "count": 66},
    UPS.PC_8800_SERIES: {"name": "NEC PC-88", "count": 167},
    UPS.PC_9800_SERIES: {"name": "NEC PC-98", "count": 311},
    UPS.PC_FX: {"name": "NEC PC-FX", "count": 25},
    UPS.NES: {"name": "NES", "count": 1300},
    UPS.NEOGEOAES: {"name": "Neo Geo", "count": 160},
    UPS.NEO_GEO_CD: {"name": "Neo Geo CD", "count": 76},
    UPS.NEO_GEO_POCKET: {"name": "Neo Geo Pocket", "count": 75},
    UPS.N3DS: {"name": "Nintendo 3DS", "count": 1048},
    UPS.N64: {"name": "Nintendo 64", "count": 446},
    UPS.NDS: {"name": "Nintendo DS", "count": 1732},
    UPS.NGC: {"name": "Nintendo GameCube", "count": 672},
    UPS.SWITCH: {"name": "Nintendo Switch", "count": 8290},
    UPS.SWITCH_2: {"name": "Nintendo Switch 2", "count": 164},
    UPS.OCULUS_GO: {"name": "Oculus Go", "count": 27},
    UPS.ODYSSEY: {"name": "Odyssey", "count": 9},
    UPS.ODYSSEY_2: {"name": "Odyssey 2", "count": 24},
    UPS.ONLIVE_GAME_SYSTEM: {"name": "OnLive", "count": 14},
    UPS.OUYA: {"name": "Ouya", "count": 20},
    UPS.WIN: {"name": "PC", "count": 58016},
    UPS.PICO: {"name": "PICO-8", "count": 3},
    UPS.PHILIPS_CD_I: {"name": "Philips CD-i", "count": 68},
    UPS.PSX: {"name": "PlayStation", "count": 2094},
    UPS.PS2: {"name": "PlayStation 2", "count": 2733},
    UPS.PS3: {"name": "PlayStation 3", "count": 2137},
    UPS.PS4: {"name": "PlayStation 4", "count": 7444},
    UPS.PS5: {"name": "PlayStation 5", "count": 3652},
    UPS.PLAYSTATION_NOW: {"name": "PlayStation Now", "count": 5},
    UPS.PSP: {"name": "PlayStation Portable", "count": 1191},
    UPS.PSVR: {"name": "PlayStation VR", "count": 52},
    UPS.PSVITA: {"name": "PlayStation Vita", "count": 1289},
    UPS.PLAYDATE: {"name": "Playdate", "count": 128},
    UPS.PS2: {"name": "Playstation 2", "count": 1},
    UPS.PLUG_AND_PLAY: {"name": "Plug & Play", "count": 18},
    UPS.SG1000: {"name": "SG-1000", "count": 75},
    UPS.SEGA32: {"name": "Sega 32X", "count": 42},
    UPS.SEGACD: {"name": "Sega CD", "count": 209},
    UPS.GAMEGEAR: {"name": "Sega Game Gear", "count": 329},
    UPS.SMS: {"name": "Sega Master System", "count": 324},
    UPS.GENESIS: {"name": "Sega Mega Drive/Genesis", "count": 959},
    UPS.SEGA_PICO: {"name": "Sega Pico", "count": 7},
    UPS.SATURN: {"name": "Sega Saturn", "count": 691},
    UPS.X1: {"name": "Sharp X1", "count": 57},
    UPS.SHARP_X68000: {"name": "Sharp X68000", "count": 195},
    UPS.SNES: {"name": "Super Nintendo", "count": 1768},
    UPS.GAME_DOT_COM: {"name": "Tiger Handheld", "count": 13},
    UPS.TG16: {"name": "TurboGrafx-16", "count": 277},
    UPS.TURBOGRAFX_CD: {"name": "TurboGrafx-CD", "count": 204},
    UPS.VECTREX: {"name": "Vectrex", "count": 16},
    UPS.VIRTUALBOY: {"name": "Virtual Boy", "count": 23},
    UPS.WII: {"name": "Wii", "count": 1314},
    UPS.WIIU: {"name": "Wii U", "count": 457},
    UPS.WINPHONE: {"name": "Windows Phone", "count": 2},
    UPS.WONDERSWAN: {"name": "WonderSwan", "count": 70},
    UPS.XBOX: {"name": "Xbox", "count": 876},
    UPS.XBOX360: {"name": "Xbox 360", "count": 2123},
    UPS.XBOXONE: {"name": "Xbox One", "count": 5326},
    UPS.XBOXONE: {"name": "Xbox Series X/S", "count": 2865},
    UPS.ZX81: {"name": "ZX Spectrum", "count": 646},
    UPS.ZEEBO: {"name": "ZX81", "count": 41},
    UPS.ZEEBO: {"name": "Zeebo", "count": 9},
}
