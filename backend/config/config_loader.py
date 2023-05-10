import os
import sys
import yaml
from yaml.loader import SafeLoader
from urllib.parse import quote_plus

from config import ROMM_DB_DRIVER, SUPPORTED_DB_DRIVERS, SQLITE_DB_BASE_PATH, ROMM_USER_CONFIG_PATH
from logger.logger import log


class ConfigLoader:

    def __init__(self):
        try:
            with open(ROMM_USER_CONFIG_PATH) as config_file: self.config: dict = (yaml.load(config_file, Loader=SafeLoader) or {})
        except FileNotFoundError:
            self.config: dict = {}
        self._parse_config()


    @staticmethod
    def get_db_engine():
        if ROMM_DB_DRIVER in SUPPORTED_DB_DRIVERS:

            if ROMM_DB_DRIVER == 'mariadb':
                DB_HOST: str = os.environ.get('DB_HOST')
                try:
                    DB_PORT: int = int(os.environ.get('DB_PORT'))
                except TypeError:
                    log.critical("DB_PORT variable not set properly")
                    sys.exit(3)
                DB_USER: str = os.environ.get('DB_USER')
                DB_PASSWD: str = os.environ.get('DB_PASSWD')
                DB_NAME: str = os.environ.get('DB_NAME', 'romm')

                return f"mariadb+mariadbconnector://{DB_USER}:%s@{DB_HOST}:{DB_PORT}/{DB_NAME}" % quote_plus(DB_PASSWD)

            elif ROMM_DB_DRIVER == 'sqlite':
                if not os.path.exists(SQLITE_DB_BASE_PATH): os.makedirs(SQLITE_DB_BASE_PATH)
                return f"sqlite:////{SQLITE_DB_BASE_PATH}/romm.db"

        else:
            log.critical(f"{ROMM_DB_DRIVER} database not supported")
            sys.exit(3)


    def _parse_config(self) -> dict:
        try:
            self.config['EXCLUDED_PLATFORMS'] = self.config['exclude']['platforms'] if self.config['exclude']['platforms'] else []
        except (KeyError, TypeError):
            self.config['EXCLUDED_PLATFORMS'] = []
        try:
            self.config['EXCLUDED_SINGLE_EXT'] = self.config['exclude']['roms']['single_file']['extensions'] if self.config['exclude']['roms']['single_file']['extensions'] else []
        except (KeyError, TypeError):
            self.config['EXCLUDED_SINGLE_EXT'] = []
        try:
            self.config['EXCLUDED_SINGLE_FILES'] = self.config['exclude']['roms']['single_file']['names'] if self.config['exclude']['roms']['single_file']['names'] else []
        except (KeyError, TypeError):
            self.config['EXCLUDED_SINGLE_FILES'] = []
        try:
            self.config['EXCLUDED_MULTI_FILES'] = self.config['exclude']['roms']['multi_file']['names'] if self.config['exclude']['roms']['multi_file']['names'] else []
        except (KeyError, TypeError):
            self.config['EXCLUDED_MULTI_FILES'] = []
        try:
            self.config['EXCLUDED_MULTI_PARTS_EXT'] = self.config['exclude']['roms']['multi_file']['parts']['extensions'] if self.config['exclude']['roms']['multi_file']['parts']['extensions'] else []
        except (KeyError, TypeError):
            self.config['EXCLUDED_MULTI_PARTS_EXT'] = []
        try:
            self.config['EXCLUDED_MULTI_PARTS_FILES'] = self.config['exclude']['roms']['multi_file']['parts']['names'] if self.config['exclude']['roms']['multi_file']['parts']['names'] else []
        except (KeyError, TypeError):
            self.config['EXCLUDED_MULTI_PARTS_FILES'] = []
        try:
            self.config['PLATFORMS_BINDING'] = self.config['system']['platforms'] if self.config['system']['platforms'] else {}
        except (KeyError, TypeError):
            self.config['PLATFORMS_BINDING'] = {}

	