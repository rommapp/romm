import os
import sys
import yaml
import pydash
from yaml.loader import SafeLoader
from urllib.parse import quote_plus

from config import (
    ROMM_DB_DRIVER,
    SQLITE_DB_BASE_PATH,
    ROMM_USER_CONFIG_PATH,
    DB_HOST,
    DB_PORT,
    DB_USER,
    DB_PASSWD,
    DB_NAME,
)
from logger.logger import log


class ConfigLoader:
    # Tests require custom config path
    def __init__(self, config_path: str = ROMM_USER_CONFIG_PATH):
        try:
            with open(config_path) as config_file:
                self.config = yaml.load(config_file, Loader=SafeLoader) or {}
        except FileNotFoundError:
            self.config = {}
        finally:
            self._parse_config()

    @staticmethod
    def get_db_engine() -> str:
        if ROMM_DB_DRIVER == "mariadb":
            if not DB_USER or not DB_PASSWD:
                log.critical(
                    "Missing database credentials. Please check your configuration file"
                )
                sys.exit(3)

            return (
                f"mariadb+mariadbconnector://{DB_USER}:%s@{DB_HOST}:{DB_PORT}/{DB_NAME}"
                % quote_plus(DB_PASSWD)
            )

        if ROMM_DB_DRIVER == "sqlite":
            if not os.path.exists(SQLITE_DB_BASE_PATH):
                os.makedirs(SQLITE_DB_BASE_PATH)
            return f"sqlite:////{SQLITE_DB_BASE_PATH}/romm.db"

        log.critical(f"{ROMM_DB_DRIVER} database not supported")
        sys.exit(3)

    def _parse_config(self):
        self.config["EXCLUDED_PLATFORMS"] = pydash.get(
            self.config, "exclude.platforms", []
        )
        self.config["EXCLUDED_SINGLE_EXT"] = pydash.get(
            self.config, "exclude.roms.single_file.extensions", []
        )
        self.config["EXCLUDED_SINGLE_FILES"] = pydash.get(
            self.config, "exclude.roms.single_file.names", []
        )
        self.config["EXCLUDED_MULTI_FILES"] = pydash.get(
            self.config, "exclude.roms.multi_file.names", []
        )
        self.config["EXCLUDED_MULTI_PARTS_EXT"] = pydash.get(
            self.config, "exclude.roms.multi_file.parts.extensions", []
        )
        self.config["EXCLUDED_MULTI_PARTS_FILES"] = pydash.get(
            self.config, "exclude.roms.multi_file.parts.names", []
        )
        self.config["PLATFORMS_BINDING"] = pydash.get(
            self.config, "system.platforms", {}
        )


config = ConfigLoader().config
