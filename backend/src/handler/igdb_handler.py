import sys
import functools
import re
import unidecode
from time import time

import requests

from config import CLIENT_ID, CLIENT_SECRET, DEFAULT_URL_COVER_L
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
        try:
            res_details: dict = requests.post("https://api.igdb.com/v4/platforms/", headers=self.headers,
                                              data=f"fields id, name; where slug=\"{slug}\";").json()[0]
            igdb_id = res_details['id']
            name = res_details['name']
        except IndexError:
            log.warning(f"{slug} not found in IGDB")
        if not name: name = slug
        return {'igdb_id': igdb_id, 'name': name, 'slug': slug, 'logo_path': ''}


    @check_twitch_token
    def get_rom_details(self, file_name: str, p_igdb_id: int, r_igdb_id_search: str) -> dict:
        search_term: str = unidecode.unidecode(re.sub('[\(\[].*?[\)\]]', '', file_name.split('.')[0]))
        r_igdb_id: str = ""
        r_slug: str = ""
        r_name: str = ""
        summary: str = ""
        url_cover: str = ""

        if r_igdb_id_search:
            res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                              data=f"fields id, slug, name, summary; where id={r_igdb_id_search};").json()[0]
            r_igdb_id = res_details['id']
            r_slug = res_details['slug']
            r_name = res_details['name']
            try:
                summary = res_details['summary']
            except KeyError:
                pass            
        
        else: #TODO: improve API calls to make only one
            if p_igdb_id:
                try:

                    res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                                      data=f"search \"{search_term}\";fields id, slug, name, summary; where platforms=[{p_igdb_id}] & category=0;").json()[0]
                    r_igdb_id = res_details['id']
                    r_slug = res_details['slug']
                    r_name = res_details['name']
                    try:
                        summary = res_details['summary']
                    except KeyError:
                        pass
                except IndexError:
                    try:
                        res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                                          data=f"search \"{search_term}\";fields name, id, slug, summary; where platforms=[{p_igdb_id}] & category=10;").json()[0]
                        r_igdb_id = res_details['id']
                        r_slug = res_details['slug']
                        r_name = res_details['name']
                        try:
                            summary = res_details['summary']
                        except KeyError:
                            pass
                    except IndexError:
                        try:
                            res_details: dict = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                                              data=f"search \"{search_term}\";fields name, id, slug, summary; where platforms=[{p_igdb_id}];").json()[0]
                            r_igdb_id = res_details['id']
                            r_slug = res_details['slug']
                            r_name = res_details['name']
                            try:
                                summary = res_details['summary']
                            except KeyError:
                                pass
                        except IndexError:
                            log.warning(f"{file_name} not found in IGDB")
        if r_igdb_id:
            try:
                res_details: dict = requests.post("https://api.igdb.com/v4/covers/", headers=self.headers,
                                                  data=f"fields url; where game={r_igdb_id};").json()[0]
                url_cover: str = f"https:{res_details['url']}"
            except IndexError:
                log.warning(f"{r_name} cover not found in IGDB")
        if not r_name: r_name = search_term
        return {'r_igdb_id': r_igdb_id, 'r_slug': r_slug, 'r_name': r_name, 'summary': summary, 'url_cover': url_cover}

    
    @check_twitch_token
    def get_matched_roms(self, file_name: str, p_igdb_id: int, p_slug: str) -> list:
        matched_roms: list[dict] = []
        if p_igdb_id != '':
            search_term: str = unidecode.unidecode(re.sub('[\(\[].*?[\)\]]', '', file_name.split('.')[0]))
            matched_roms: list = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                               data=f"search \"{search_term}\";fields name, id, slug, summary; where platforms=[{p_igdb_id}];").json()
            for rom in matched_roms:
                try:
                    res_details: dict = requests.post("https://api.igdb.com/v4/covers/", headers=self.headers,
                                                      data=f"fields url; where game={rom['id']};").json()[0]
                    rom['url_cover'] = f"https:{res_details['url']}".replace('t_thumb', f't_cover_big')
                except IndexError:
                    rom['url_cover'] = DEFAULT_URL_COVER_L
                rom['r_igdb_id'] = rom.pop('id')
                rom['r_slug'] = rom.pop('slug')
                rom['r_name'] = rom.pop('name')
        else:
            log.warning(f"{p_slug} is not supported!")
        return matched_roms
    
    def get_matched_roms_by_id(self, igdb_id: str) -> list:
        res: list = requests.post("https://api.igdb.com/v4/games/", headers=self.headers,
                                            data=f"fields name, id, slug, summary; where id={igdb_id};")
        if res.status_code == 200:
            matched_roms = res.json()
            for rom in matched_roms:
                try:
                    res_details: dict = requests.post("https://api.igdb.com/v4/covers/", headers=self.headers,
                                                    data=f"fields url; where game={rom['id']};").json()[0]
                    rom['url_cover'] = f"https:{res_details['url']}".replace('t_thumb', f't_cover_big')
                except IndexError:
                    rom['url_cover'] = DEFAULT_URL_COVER_L
                rom['r_igdb_id'] = rom.pop('id')
                rom['r_slug'] = rom.pop('slug')
                rom['r_name'] = rom.pop('name')
        else:
            matched_roms: list = []
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
            log.info("Twitch token fetched!")
        except KeyError:
            log.error("Could not get twitch auth token: check client_id and client_secret")
            sys.exit(2)


    def get_oauth_token(self) -> str:
        if not self._is_token_valid():
            log.warning("Twitch token invalid: fetching a new one")
            self._update_twitch_token()
        return self.token