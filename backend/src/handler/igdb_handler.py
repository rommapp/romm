import sys
import functools
from time import time

import requests

from config.config import CLIENT_ID, CLIENT_SECRET
from logger.logger import log


class IGDBHandler():

    def __init__(self) -> None:
        self.twitch_auth: TwitchAuth = TwitchAuth()
        self.headers = {
            'Client-ID': self.twitch_auth.client_id,
            'Authorization': f'Bearer {self.twitch_auth.get_oauth_token()}',
            'Accept': 'application/json'
        }
        

    def check_twitch_token(func) -> tuple:
        @functools.wraps(func)
        def wrapper(*args):
            args[0].headers['Authorization'] = f'Bearer {args[0].twitch_auth.get_oauth_token()}'
            return func(*args)
        return wrapper

    
    @check_twitch_token
    def get_platform_details(self, slug: str) -> tuple:
        igdb_id: str = ""
        name: str = ""
        url_logo: str = ""
        try:
            res_details: dict = requests.post("https://api.igdb.com/v4/platforms/", headers=self.headers,
                                              data=f"fields id, name, platform_logo; where slug=\"{slug}\";").json()[0]
            igdb_id = res_details['id']
            name = res_details['name']
            id_logo = res_details['platform_logo']
        except IndexError:
            log.warning("platform not found in igdb")
        else:
            try:
                res_logo: dict = requests.post("https://api.igdb.com/v4/platform_logos", headers=self.headers,
                                               data=f"fields image_id; where id={id_logo};").json()[0]
                url_logo: str = f"https://images.igdb.com/igdb/image/upload/t_logo_med/{res_logo['image_id']}.png"
            except IndexError:
                log.warning(f"{slug} logo not found in igdb")
        if not name: name = slug
        return igdb_id, name, url_logo


    @check_twitch_token
    def get_rom_details(self, filename: str, p_igdb_id: int, r_igdb_id: str) -> dict:
        filename_no_ext: str = filename.split('.')[0]
        igdb_id: str = ""
        slug: str = ""
        name: str = ""
        summary: str = ""
        url_cover: str = ""

        if r_igdb_id:
            res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                              data=f"fields id, slug, name, summary; where id={r_igdb_id};").json()[0]
            igdb_id = res_details['id']
            slug = res_details['slug']
            name = res_details['name']
            try:
                summary = res_details['summary']
            except KeyError:
                pass            
        
        else:
            if p_igdb_id:
                try:
                    res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                                      data=f"search \"{filename_no_ext}\";fields id, slug, name, summary; where platforms=[{p_igdb_id}] & category=0;").json()[0]
                    igdb_id = res_details['id']
                    slug = res_details['slug']
                    name = res_details['name']
                    try:
                        summary = res_details['summary']
                    except KeyError:
                        pass
                except IndexError:
                    try:
                        res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                                          data=f"search \"{filename_no_ext}\";fields name, id, slug, summary; where platforms=[{p_igdb_id}] & category=10;").json()[0]
                        igdb_id = res_details['id']
                        slug = res_details['slug']
                        name = res_details['name']
                        try:
                            summary = res_details['summary']
                        except KeyError:
                            pass
                    except IndexError:
                        try:
                            res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                                              data=f"search \"{filename_no_ext}\";fields name, id, slug, summary; where platforms=[{p_igdb_id}];").json()[0]
                            igdb_id = res_details['id']
                            slug = res_details['slug']
                            name = res_details['name']
                            try:
                                summary = res_details['summary']
                            except KeyError:
                                pass
                        except IndexError:
                            log.warning(f"{filename} rom not found in igdb")
        if igdb_id:
            try:
                res_details: dict = requests.post("https://api.igdb.com/v4/covers/", headers=self.headers,
                                                  data=f"fields url; where game={igdb_id};").json()[0]
                url_cover: str = f"https:{res_details['url']}"
            except IndexError:
                log.warning(f"{name} cover not found in igdb")
        if not name: name = filename_no_ext
        return (igdb_id, filename_no_ext, slug, name, summary, url_cover)

    
    @check_twitch_token
    def get_matched_roms(self, filename: str, p_igdb_id: int) -> list:
        matched_roms: list = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                           data=f"search \"{filename.split('.')[0]}\";fields name, id, slug, summary; where platforms=[{p_igdb_id}];").json()
        for rom in matched_roms:
            res_details: dict = requests.post("https://api.igdb.com/v4/covers/", headers=self.headers,
                                              data=f"fields url; where game={rom['id']};").json()[0]
            rom['url_cover'] = f"https:{res_details['url']}".replace('t_thumb', f't_cover_big')
        return matched_roms



class TwitchAuth():

    def __init__(self) -> None:
        self.token: str = ""
        self.token_checkout: int = int(time())
        self.SECURE_SECONDS_OFFSET: int = 10 # seconds offset to avoid invalid token 
        self.token_valid_seconds: int = 0
        self.client_id: str = CLIENT_ID
        self.client_secret: str = CLIENT_SECRET


    def _is_token_valid(self) -> str:
        return True if int(time()) + self.SECURE_SECONDS_OFFSET - self.token_checkout < self.token_valid_seconds else False


    def _update_twitch_token(self) -> str:
        res = requests.post(url=f"https://id.twitch.tv/oauth2/token",
                            params={
                                'client_id': self.client_id,
                                'client_secret': self.client_secret,
                                'grant_type': 'client_credentials'}
                            ).json()
        self.token_checkout = int(time())
        try:
            self.token_valid_seconds = res['expires_in']
            self.token = res['access_token']
            log.info("twitch token fetched!")
        except KeyError:
            log.error("could not get twitch auth token: check client_id and client_secret")
            sys.exit(2)


    def get_oauth_token(self) -> str:
        if not self._is_token_valid():
            log.warning("twitch token invalid: fetching a new one")
            self._update_twitch_token()
        return self.token