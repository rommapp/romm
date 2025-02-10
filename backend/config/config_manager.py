import os
import sys
from pathlib import Path
from typing import Final

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
from sqlalchemy import URL
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
    PLATFORMS_VERSIONS: dict[str, str]
    ROMS_FOLDER_NAME: str
    FIRMWARE_FOLDER_NAME: str
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
            self.get_config()
        except ConfigNotReadableException as e:
            log.critical(e.message)
            sys.exit(5)

    @staticmethod
    def get_db_engine() -> URL:
        """Builds the database connection string depending on the defined database in the config.yml file

        Returns:
            str: database connection string
        """

        # DEPRECATED
        if ROMM_DB_DRIVER == "sqlite":
            log.critical("Sqlite is not supported anymore, migrate to mariaDB")
            sys.exit(6)
        # DEPRECATED

        if ROMM_DB_DRIVER == "mariadb":
            driver = "mariadb+mariadbconnector"
        elif ROMM_DB_DRIVER == "mysql":
            driver = "mysql+mysqlconnector"
        elif ROMM_DB_DRIVER == "postgresql":
            driver = "postgresql+psycopg"
        else:
            log.critical(f"{ROMM_DB_DRIVER} database not supported")
            sys.exit(3)

        if not DB_USER or not DB_PASSWD:
            log.critical(
                "Missing database credentials, check your environment variables!"
            )
            sys.exit(3)

        return URL.create(
            drivername=driver,
            username=DB_USER,
            password=DB_PASSWD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
        )

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
            PLATFORMS_VERSIONS=pydash.get(self._raw_config, "system.versions", {}),
            ROMS_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.roms_folder", "roms"
            ),
            FIRMWARE_FOLDER_NAME=pydash.get(
                self._raw_config, "filesystem.firmware_folder", "bios"
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

        if not isinstance(self.config.PLATFORMS_VERSIONS, dict):
            log.critical("Invalid config.yml: system.versions must be a dictionary")
            sys.exit(3)
        else:
            for fs_slug, slug in self.config.PLATFORMS_VERSIONS.items():
                if slug is None:
                    log.critical(
                        f"Invalid config.yml: system.versions.{fs_slug} must be a string"
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

        if not isinstance(self.config.FIRMWARE_FOLDER_NAME, str):
            log.critical(
                "Invalid config.yml: filesystem.firmware_folder must be a string"
            )
            sys.exit(3)

        if self.config.FIRMWARE_FOLDER_NAME == "":
            log.critical(
                "Invalid config.yml: filesystem.firmware_folder cannot be an empty string"
            )
            sys.exit(3)

    def get_config(self) -> Config:
        try:
            with open(self.config_file) as config_file:
                self._raw_config = yaml.load(config_file, Loader=SafeLoader) or {}
        except FileNotFoundError:
            self._raw_config = {}
        except PermissionError as exc:
            self._raw_config = {}
            raise ConfigNotReadableException from exc

        self._parse_config()
        self._validate_config()

        return self.config

    def update_config_file(self) -> None:
        self._raw_config = {
            "exclude": {
                "platforms": self.config.EXCLUDED_PLATFORMS,
                "roms": {
                    "single_file": {
                        "extensions": self.config.EXCLUDED_SINGLE_EXT,
                        "names": self.config.EXCLUDED_SINGLE_FILES,
                    },
                    "multi_file": {
                        "names": self.config.EXCLUDED_MULTI_FILES,
                        "parts": {
                            "extensions": self.config.EXCLUDED_MULTI_PARTS_EXT,
                            "names": self.config.EXCLUDED_MULTI_PARTS_FILES,
                        },
                    },
                },
            },
            "filesystem": {"roms_folder": self.config.ROMS_FOLDER_NAME},
            "system": {
                "platforms": self.config.PLATFORMS_BINDING,
                "versions": self.config.PLATFORMS_VERSIONS,
            },
        }

        try:
            with open(self.config_file, "w") as config_file:
                yaml.dump(self._raw_config, config_file)
        except FileNotFoundError:
            self._raw_config = {}
        except PermissionError as exc:
            self._raw_config = {}
            raise ConfigNotWritableException from exc

    def add_platform_binding(self, fs_slug: str, slug: str) -> None:
        platform_bindings = self.config.PLATFORMS_BINDING
        if fs_slug in platform_bindings:
            log.warning(f"Binding for {fs_slug} already exists")
            return

        platform_bindings[fs_slug] = slug
        self.config.PLATFORMS_BINDING = platform_bindings
        self.update_config_file()

    def remove_platform_binding(self, fs_slug: str) -> None:
        platform_bindings = self.config.PLATFORMS_BINDING

        try:
            del platform_bindings[fs_slug]
        except KeyError:
            pass

        self.config.PLATFORMS_BINDING = platform_bindings
        self.update_config_file()

    def add_platform_version(self, fs_slug: str, slug: str) -> None:
        platform_versions = self.config.PLATFORMS_VERSIONS
        if fs_slug in platform_versions:
            log.warning(f"Version for {fs_slug} already exists")
            return

        platform_versions[fs_slug] = slug
        self.config.PLATFORMS_VERSIONS = platform_versions
        self.update_config_file()

    def remove_platform_version(self, fs_slug: str) -> None:
        platform_versions = self.config.PLATFORMS_VERSIONS

        try:
            del platform_versions[fs_slug]
        except KeyError:
            pass

        self.config.PLATFORMS_VERSIONS = platform_versions
        self.update_config_file()

    def add_exclusion(self, exclusion_type: str, exclusion_value: str):
        config_item = self.config.__getattribute__(exclusion_type)
        if exclusion_value in config_item:
            log.warning(f"{exclusion_value} already excluded in {exclusion_type}")
            return

        config_item.append(exclusion_value)
        self.config.__setattr__(exclusion_type, config_item)
        self.update_config_file()

    def remove_exclusion(self, exclusion_type: str, exclusion_value: str):
        config_item = self.config.__getattribute__(exclusion_type)

        try:
            config_item.remove(exclusion_value)
        except ValueError:
            pass

        self.config.__setattr__(exclusion_type, config_item)
        self.update_config_file()


config_manager = ConfigManager()
