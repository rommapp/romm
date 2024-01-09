import os
import sys
from urllib.parse import quote_plus

import pydash
import yaml
from config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWD,
    DB_PORT,
    DB_USER,
    ROMM_DB_DRIVER,
    ROMM_USER_CONFIG_PATH,
    SQLITE_DB_BASE_PATH,
)
from logger.logger import log
from typing_extensions import TypedDict
from yaml.loader import SafeLoader


class ConfigDict(TypedDict):
    EXCLUDED_PLATFORMS: list[str]
    EXCLUDED_SINGLE_EXT: list[str]
    EXCLUDED_SINGLE_FILES: list[str]
    EXCLUDED_MULTI_FILES: list[str]
    EXCLUDED_MULTI_PARTS_EXT: list[str]
    EXCLUDED_MULTI_PARTS_FILES: list[str]
    PLATFORMS_BINDING: dict[str, str]


class ConfigLoader:
    """Parse and load the user configuration from the config.yml file

    Raises:
        FileNotFoundError: Raises an error if the config.yml is not found
    """

    # Tests require custom config path
    def __init__(self, config_path: str = ROMM_USER_CONFIG_PATH):
        self.config_path = config_path
        if os.path.isdir(config_path):
            log.critical(
                f"Your config file {config_path} is a directory, not a file. Docker creates folders by default for binded files that doesn't exists in advance in the host system."
            )
            raise FileNotFoundError()
        try:
            with open(config_path) as config_file:
                self.config = yaml.load(config_file, Loader=SafeLoader) or {}
        except FileNotFoundError:
            self.config = {}
        finally:
            self._parse_config()

    @staticmethod
    def get_db_engine() -> str:
        """Builds the database connection string depending on the defined database in the config.yml file

        Returns:
            str: database connection string
        """

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
        """Parses each entry in the config.yml"""

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
