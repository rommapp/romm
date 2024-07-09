import itertools
from typing import Any, Final

import requests
from config import STEAMGRIDDB_API_KEY
from logger.logger import log

# Used to display the Mobygames API status in the frontend
STEAMGRIDDB_API_ENABLED: Final = bool(STEAMGRIDDB_API_KEY)

# SteamGridDB dimensions
STEAMVERTICAL: Final = "600x900"
GALAXY342: Final = "342x482"
GALAXY660: Final = "660x930"
SQUARE512: Final = "512x512"
SQUARE1024: Final = "1024x1024"

# SteamGridDB types
STATIC: Final = "static"
ANIMATED: Final = "animated"

SGDB_API_COVER_LIMIT: Final = 50


class SGDBBaseHandler:
    def __init__(self) -> None:
        self.BASE_URL = "https://www.steamgriddb.com/api/v2"
        self.search_endpoint = f"{self.BASE_URL}/search/autocomplete"
        self.grid_endpoint = f"{self.BASE_URL}/grids/game"
        self.headers = {
            "Authorization": f"Bearer {STEAMGRIDDB_API_KEY}",
            "Accept": "*/*",
        }

    def get_details(self, search_term: str) -> list[dict[str, Any]]:
        search_response = requests.get(
            f"{self.search_endpoint}/{search_term}",
            headers=self.headers,
            timeout=120,
        ).json()

        if len(search_response["data"]) == 0:
            log.warning(f"Could not find '{search_term}' on SteamGridDB")
            return []

        games = []
        for game in search_response["data"]:
            game_covers = []
            for page in itertools.count(start=0):
                covers_response = requests.get(
                    f"{self.grid_endpoint}/{game['id']}",
                    headers=self.headers,
                    timeout=120,
                    params={
                        "dimensions": f"{STEAMVERTICAL},{GALAXY342},{GALAXY660},{SQUARE512},{SQUARE1024}",
                        "types": f"{STATIC},{ANIMATED}",
                        "limit": SGDB_API_COVER_LIMIT,
                        "page": page,
                    },
                ).json()
                page_covers = covers_response["data"]

                game_covers.extend(page_covers)
                if len(page_covers) < SGDB_API_COVER_LIMIT:
                    break

            if game_covers:
                games.append(
                    {
                        "name": game["name"],
                        "resources": [
                            {
                                "thumb": cover["thumb"],
                                "url": cover["url"],
                                "type": (
                                    "animated"
                                    if cover["thumb"].endswith(".webm")
                                    else "static"
                                ),
                            }
                            for cover in game_covers
                        ],
                    }
                )
        return games


sgdb_handler = SGDBBaseHandler()
