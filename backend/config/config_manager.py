import os
import sys
from pathlib import Path
from typing import Final
from urllib.parse import quote_plus

import pydash
import yaml
from config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWD,
    DB_PORT,
    DB_USER,
    LIBRARY_BASE_PATH,
    ROMM_BASE_PATH,
    ROMM_DB_DRIVER,
)
from exceptions.config_exceptions import (
    ConfigNotReadableException,
    ConfigNotWritableException,
)
from logger.logger import log
from yaml.loader import SafeLoader

ROMM_USER_CONFIG_PATH: Final = f"{ROMM_BASE_PATH}/config"
ROMM_USER_CONFIG_FILE: Final = f"{ROMM_USER_CONFIG_PATH}/config.yml"
SQLITE_DB_BASE_PATH: Final = f"{ROMM_BASE_PATH}/database"


class Config:
    EXCLUDED_PLATFORMS: list[str]
    EXCLUDED_SINGLE_EXT: list[str]
    EXCLUDED_SINGLE_FILES: list[str]
    EXCLUDED_MULTI_FILES: list[str]
    EXCLUDED_MULTI_PARTS_EXT: list[str]
    EXCLUDED_MULTI_PARTS_FILES: list[str]
    PLATFORMS_BINDING: dict[str, str]
    ROMS_FOLDER_NAME: str
    SAVES_FOLDER_NAME: str
    STATES_FOLDER_NAME: str
    SCREENSHOTS_FOLDER_NAME: str
    HIGH_PRIO_STRUCTURE_PATH: str

    def __init__(self, **entries):
        self.__dict__.update(entries)
        self.HIGH_PRIO_STRUCTURE_PATH = f"{LIBRARY_BASE_PATH}/{self.ROMS_FOLDER_NAME}"


class ConfigManager:
    """Parse and load the user configuration from the config.yml file

    Raises:
        FileNotFoundError: Raises an error if the config.yml is not found
    """

    _self = None

    def __new__(cls, *args, **kwargs):
        if cls._self is None:
            cls._self = super().__new__(cls, *args, **kwargs)

        return cls._self

    # Tests require custom config path
    def __init__(self, config_file: str = ROMM_USER_CONFIG_FILE):
        self.config_file = config_file
        # If config file doesn't exists, create an empty one
        if not os.path.exists(config_file):
            Path(ROMM_USER_CONFIG_PATH).mkdir(parents=True, exist_ok=True)
            with open(config_file, "w") as file:
                file.write("")
        try:
            self.read_config()
        except ConfigNotReadableException as e:
            log.critical(e.message)
            sys.exit(5)

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

        # DEPRECATED
        if ROMM_DB_DRIVER == "sqlite":
            log.critical(
                "Sqlite is not supported anymore, change to MariaDB is needed."
            )
            sys.exit(6)
        # DEPRECATED

        log.critical(f"{ROMM_DB_DRIVER} database not supported")
        sys.exit(3)

    def _parse_config(self):
        """Parses each entry in the config.yml"""

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
        )

    def _validate_config(self):
        """Validates the config.yml file"""
        if not isinstance(self.config.EXCLUDED_PLATFORMS, list):
            log.critical("Invalid config.yml: exclude.platforms must be a list")
            sys.exit(3)

        if not isinstance(self.config.EXCLUDED_SINGLE_EXT, list):
            log.critical(
                "Invalid config.yml: exclude.roms.single_file.extensions must be a list"
            )
            sys.exit(3)

        if not isinstance(self.config.EXCLUDED_SINGLE_FILES, list):
            log.critical(
                "Invalid config.yml: exclude.roms.single_file.names must be a list"
            )
            sys.exit(3)

        if not isinstance(self.config.EXCLUDED_MULTI_FILES, list):
            log.critical(
                "Invalid config.yml: exclude.roms.multi_file.names must be a list"
            )
            sys.exit(3)

        if not isinstance(self.config.EXCLUDED_MULTI_PARTS_EXT, list):
            log.critical(
                "Invalid config.yml: exclude.roms.multi_file.parts.extensions must be a list"
            )
            sys.exit(3)

        if not isinstance(self.config.EXCLUDED_MULTI_PARTS_FILES, list):
            log.critical(
                "Invalid config.yml: exclude.roms.multi_file.parts.names must be a list"
            )
            sys.exit(3)

        if not isinstance(self.config.PLATFORMS_BINDING, dict):
            log.critical("Invalid config.yml: system.platforms must be a dictionary")
            sys.exit(3)
        else:
            for fs_slug, slug in self.config.PLATFORMS_BINDING.items():
                if slug is None:
                    log.critical(
                        f"Invalid config.yml: system.platforms.{fs_slug} must be a string"
                    )
                    sys.exit(3)

        if not isinstance(self.config.ROMS_FOLDER_NAME, str):
            log.critical("Invalid config.yml: filesystem.roms_folder must be a string")
            sys.exit(3)

        if self.config.ROMS_FOLDER_NAME == "":
            log.critical(
                "Invalid config.yml: filesystem.roms_folder cannot be an empty string"
            )
            sys.exit(3)

        if not isinstance(self.config.SAVES_FOLDER_NAME, str):
            log.critical("Invalid config.yml: filesystem.saves_folder must be a string")
            sys.exit(3)

        if self.config.SAVES_FOLDER_NAME == "":
            log.critical(
                "Invalid config.yml: filesystem.saves_folder cannot be an empty string"
            )
            sys.exit(3)

        if not isinstance(self.config.STATES_FOLDER_NAME, str):
            log.critical(
                "Invalid config.yml: filesystem.states_folder must be a string"
            )
            sys.exit(3)

        if self.config.STATES_FOLDER_NAME == "":
            log.critical(
                "Invalid config.yml: filesystem.states_folder cannot be an empty string"
            )
            sys.exit(3)

        if not isinstance(self.config.SCREENSHOTS_FOLDER_NAME, str):
            log.critical(
                "Invalid config.yml: filesystem.screenshots_folder must be a string"
            )
            sys.exit(3)

        if self.config.SCREENSHOTS_FOLDER_NAME == "":
            log.critical(
                "Invalid config.yml: filesystem.screenshots_folder cannot be an empty string"
            )
            sys.exit(3)

    def read_config(self) -> None:
        try:
            with open(self.config_file) as config_file:
                self._raw_config = yaml.load(config_file, Loader=SafeLoader) or {}
        except FileNotFoundError:
            self._raw_config = {}
        except PermissionError:
            self._raw_config = {}
            raise ConfigNotReadableException
        self._parse_config()
        self._validate_config()

    def update_config(self) -> None:
        try:
            with open(self.config_file, "w") as config_file:
                yaml.dump(self._raw_config, config_file)
        except FileNotFoundError:
            self._raw_config = {}
        except PermissionError:
            self._raw_config = {}
            raise ConfigNotWritableException
        finally:
            self._parse_config()

    def add_binding(self, fs_slug: str, slug: str) -> None:
        try:
            _ = self._raw_config["system"]
        except KeyError:
            self._raw_config = {"system": {"platforms": {}}}
        try:
            _ = self._raw_config["system"]["platforms"]
        except KeyError:
            self._raw_config["system"]["platforms"] = {}
        self._raw_config["system"]["platforms"][fs_slug] = slug
        self.update_config()

    def remove_binding(self, fs_slug: str) -> None:
        try:
            del self._raw_config["system"]["platforms"][fs_slug]
        except KeyError:
            pass
        self.update_config()

    # def _get_exclude_path(self, exclude):
    #     exclude_base = self._raw_config["exclude"]
    #     exclusions = {
    #         "platforms": exclude_base["platforms"],
    #         "single_ext": exclude_base["roms"]["single_file"]["extensions"],
    #         "single_file": exclude_base["roms"]["single_file"]["names"],
    #         "multi_file": exclude_base["roms"]["multi_file"]["names"],
    #         "multi_part_ext": exclude_base["roms"]["multi_file"]["parts"]["extensions"],
    #         "multi_part_file": exclude_base["roms"]["multi_file"]["parts"]["names"],
    #     }
    #     return exclusions[exclude]

    # def add_exclusion(self, exclude: str, exclusion: str):
    #     config = self._get_exclude_path(exclude)
    #     config.append(exclusion)

    # def remove_exclusion(self, exclude: str, exclusion: str):
    #     config = self._get_exclude_path(exclude)
    #     config.remove(exclusion)


config_manager = ConfigManager()
