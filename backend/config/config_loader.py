import os
import sys
import yaml
import pydash
from yaml.loader import SafeLoader
from urllib.parse import quote_plus
from typing import Final

from config import (
    ROMM_DB_DRIVER,
    ROMM_BASE_PATH,
    LIBRARY_BASE_PATH,
    DB_HOST,
    DB_PORT,
    DB_USER,
    DB_PASSWD,
    DB_NAME,
)
from logger.logger import log

ROMM_USER_CONFIG_PATH: Final = f"{ROMM_BASE_PATH}/config.yml"
SQLITE_DB_BASE_PATH: Final = f"{ROMM_BASE_PATH}/database"


class Config:
    EXCLUDED_PLATFORMS: list[str] = []
    EXCLUDED_SINGLE_EXT: list[str] = []
    EXCLUDED_SINGLE_FILES: list[str] = []
    EXCLUDED_MULTI_FILES: list[str] = []
    EXCLUDED_MULTI_PARTS_EXT: list[str] = []
    EXCLUDED_MULTI_PARTS_FILES: list[str] = []
    PLATFORMS_BINDING: dict[str, str] = {}
    ROMS_FOLDER_NAME: str = "roms"
    SAVES_FOLDER_NAME: str = "saves"
    STATES_FOLDER_NAME: str = "states"
    SCREENSHOTS_FOLDER_NAME: str = "screenshots"
    BIOS_FOLDER_NAME: str = "bios"
    EMULATORS_FOLDER_NAME: str = "emulators"
    HIGH_PRIO_STRUCTURE_PATH: str = ""

    def __init__(self, **entries):
        self.__dict__.update(entries)
        self.HIGH_PRIO_STRUCTURE_PATH = f"{LIBRARY_BASE_PATH}/{self.ROMS_FOLDER_NAME}"


class ConfigLoader:
    # Tests require custom config path
    def __init__(self, config_path: str = ROMM_USER_CONFIG_PATH):
        try:
            with open(config_path) as config_file:
                self._raw_config = yaml.load(config_file, Loader=SafeLoader) or {}
                self._parse_config()
        except FileNotFoundError:
            self.config = Config()

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
        self.config = Config(
            EXCLUDED_PLATFORMS=pydash.get(self._raw_config, "exclude.platforms", []),
            EXCLUDED_SINGLE_EXT=pydash.get(
                self._raw_config, "exclude.roms.single_file.extensions", []
            ),
            EXCLUDED_SINGLE_FILES=pydash.get(
                self._raw_config, "exclude.roms.single_file.names", []
            ),
            EXCLUDED_MULTI_FILES=pydash.get(
                self._raw_config, "exclude.roms.multi_file.names", []
            ),
            EXCLUDED_MULTI_PARTS_EXT=pydash.get(
                self._raw_config, "exclude.roms.multi_file.parts.extensions", []
            ),
            EXCLUDED_MULTI_PARTS_FILES=pydash.get(
                self._raw_config, "exclude.roms.multi_file.parts.names", []
            ),
            PLATFORMS_BINDING=pydash.get(self._raw_config, "system.platforms", {}),
            ROMS_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.roms_folder", "roms"
            ),
            SAVES_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.saves_folder", "saves"
            ),
            STATES_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.states_folder", "states"
            ),
            SCREENSHOTS_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.screenshots_folder", "screenshots"
            ),
            BIOS_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.bios_folder", "bios"
            ),
            EMULATORS_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.emulators_folder", "emulators"
            ),
        )


config = ConfigLoader().config
