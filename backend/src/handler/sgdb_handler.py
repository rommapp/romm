import requests

from config.config import STEAMGRIDDB_API_KEY
from logger.logger import log


class SGDBHandler():

    def __init__(self) -> None:
        self.headers: dict = {"Authorization": f"Bearer {STEAMGRIDDB_API_KEY}", "Accept": "*/*"}
        self.BASE_URL: str = "https://www.steamgriddb.com/api/v2"
        self.DEFAULT_IMAGE_URL: str = "https://www.steamgriddb.com/static/img/logo-512.png"


    def get_details(self, term) -> tuple:
        id: int = ""
        name: str = ""
        url_logo: str = ""
        try:
            res: dict = requests.get(f"{self.BASE_URL}/search/autocomplete/{term}", headers=self.headers).json()['data'][0]
            id: int = res['id']
            name: str = res['name']
        except IndexError:
            log.warning(f"{term} not found in steamgriddb")
        else:
            try:
                res = requests.get(f"{self.BASE_URL}/grid/game/{id}", headers=self.headers)
                url_logo: str = res.json()['data'][0]['url']
            except IndexError:
                log.warning(f"{term} logo not found in steamgriddb")
        return (id, name, url_logo)
