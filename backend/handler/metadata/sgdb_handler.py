import requests
from config import STEAMGRIDDB_API_KEY
from logger.logger import log


class SGDBBaseHandler:
    def __init__(self) -> None:
        self.headers = {
            "Authorization": f"Bearer {STEAMGRIDDB_API_KEY}",
            "Accept": "*/*",
        }
        self.BASE_URL = "https://www.steamgriddb.com/api/v2"
        self.DEFAULT_IMAGE_URL = "https://www.steamgriddb.com/static/img/logo-512.png"

    def get_details(self, term):
        search_response = requests.get(
            f"{self.BASE_URL}/search/autocomplete/{term}",
            headers=self.headers,
            timeout=120,
        ).json()

        if len(search_response["data"]) == 0:
            log.info(f"Could not find {term} on SteamGridDB")
            return ("", "", self.DEFAULT_IMAGE_URL)

        game_id = search_response["data"][0]["id"]
        game_name = search_response["data"][0]["name"]

        game_response = requests.get(
            f"{self.BASE_URL}/grid/game/{game_id}", headers=self.headers, timeout=120
        ).json()

        if len(game_response["data"]) == 0:
            log.info(f"Could not find {game_name} image on SteamGridDB")
            return (game_id, game_name, self.DEFAULT_IMAGE_URL)

        game_image_url = game_response["data"][0]["url"]

        return (game_id, game_name, game_image_url)


sgdb_handler = SGDBBaseHandler()
