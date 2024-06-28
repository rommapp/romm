from typing import Final

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

    def get_details(self, search_term):
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
            page = 0
            covers_response = requests.get(
                f"{self.grid_endpoint}/{game['id']}",
                headers=self.headers,
                timeout=120,
                params={
                    "dimensions": f"{STEAMVERTICAL},{GALAXY342},{GALAXY660},{SQUARE512},{SQUARE1024}",
                    "types": f"{STATIC},{ANIMATED}",
                    "page": page,
                },
            ).json()

            while (
                len(covers_response["data"]) < covers_response["total"]
                and covers_response["total"] > SGDB_API_COVER_LIMIT
            ):
                page += 1
                covers_response["data"].extend(
                    requests.get(
                        f"{self.grid_endpoint}/{game['id']}",
                        headers=self.headers,
                        timeout=120,
                        params={
                            "dimensions": f"{STEAMVERTICAL},{GALAXY342},{GALAXY660},{SQUARE512},{SQUARE1024}",
                            "types": f"{STATIC},{ANIMATED}",
                            "page": page,
                        },
                    ).json()["data"]
                )

            if len(covers_response["data"]) > 0:
                games.append(
                    {
                        "name": game["name"],
                        "resources": [
                            {
                                "thumb": cover["thumb"],
                                "url": cover["url"],
                                "type": (
                                    "animated"
                                    if cover["thumb"].split(".")[-1] == "webm"
                                    else "static"
                                ),
                            }
                            for cover in covers_response["data"]
                        ],
                    }
                )

        return games


sgdb_handler = SGDBBaseHandler()
