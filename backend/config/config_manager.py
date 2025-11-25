import enum
import json
import os
import sys
from typing import Final, NotRequired, TypedDict

import pydash
import yaml
from sqlalchemy import URL
from yaml.loader import SafeLoader

from config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWD,
    DB_PORT,
    DB_QUERY_JSON,
    DB_USER,
    LIBRARY_BASE_PATH,
    ROMM_BASE_PATH,
    ROMM_DB_DRIVER,
)
from exceptions.config_exceptions import ConfigNotWritableException
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log

ROMM_USER_CONFIG_PATH: Final = f"{ROMM_BASE_PATH}/config"
ROMM_USER_CONFIG_FILE: Final = f"{ROMM_USER_CONFIG_PATH}/config.yml"
SQLITE_DB_BASE_PATH: Final = f"{ROMM_BASE_PATH}/database"


class EjsControlsButton(TypedDict):
    value: NotRequired[str]  # Keyboard key
    value2: NotRequired[str]  # Controller button


class MetadataMediaType(enum.StrEnum):
    BEZEL = "bezel"
    BOX2D = "box2d"
    BOX2D_BACK = "box2d_back"
    BOX3D = "box3d"
    MIXIMAGE = "miximage"
    PHYSICAL = "physical"
    SCREENSHOT = "screenshot"
    TITLE_SCREEN = "title_screen"
    MARQUEE = "marquee"
    LOGO = "logo"
    FANART = "fanart"
    VIDEO = "video"
    MANUAL = "manual"


class EjsControls(TypedDict):
    _0: dict[int, EjsControlsButton]  # button_number -> EjsControlsButton
    _1: dict[int, EjsControlsButton]
    _2: dict[int, EjsControlsButton]
    _3: dict[int, EjsControlsButton]


EjsOption = dict[str, str]  # option_name -> option_value


class Config:
    CONFIG_FILE_MOUNTED: bool
    CONFIG_FILE_WRITABLE: bool
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
    SKIP_HASH_CALCULATION: bool
    HIGH_PRIO_STRUCTURE_PATH: str
    EJS_DEBUG: bool
    EJS_CACHE_LIMIT: int | None
    EJS_SETTINGS: dict[str, EjsOption]  # core_name -> EjsOption
    EJS_CONTROLS: dict[str, EjsControls]  # core_name -> EjsControls
    SCAN_METADATA_PRIORITY: list[str]
    SCAN_ARTWORK_PRIORITY: list[str]
    SCAN_REGION_PRIORITY: list[str]
    SCAN_LANGUAGE_PRIORITY: list[str]
    SCAN_MEDIA: list[str]

    def __init__(self, **entries):
        self.__dict__.update(entries)
        self.HIGH_PRIO_STRUCTURE_PATH = f"{LIBRARY_BASE_PATH}/{self.ROMS_FOLDER_NAME}"


class ConfigManager:
    """
    Parse and load the user configuration from the config.yml file.
    If config.yml is not found, uses default configuration values.

    The config file will be created automatically when configuration is updated.
    """

    _self = None
    _raw_config: dict = {}
    _config_file_mounted: bool = False
    _config_file_writable: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._self is None:
            cls._self = super().__new__(cls, *args, **kwargs)

        return cls._self

    # Tests require custom config path
    def __init__(self, config_file: str = ROMM_USER_CONFIG_FILE):
        self.config_file = config_file

        try:
            # Check if the config file is mounted
            with open(self.config_file, "r") as cf:
                self._config_file_mounted = True
                self._raw_config = yaml.load(cf, Loader=SafeLoader) or {}

            # Also check if the config file is writable
            self._config_file_writable = os.access(self.config_file, os.W_OK)
        except FileNotFoundError:
            log.critical(
                "Config file not found! Any changes made to the configuration will not persist after the application restarts."
            )
        except PermissionError:
            log.warning(
                "Config file not writable! Any changes made to the configuration will not persist after the application restarts."
            )
        finally:
            # Set the config to default values
            self._parse_config()
            self._validate_config()

    @staticmethod
    def get_db_engine() -> URL:
        """Builds the database connection string using environment variables

        Returns:
            str: database connection string
        """

        if ROMM_DB_DRIVER == "mariadb":
            driver = "mariadb+mariadbconnector"
        elif ROMM_DB_DRIVER == "mysql":
            driver = "mysql+mysqlconnector"
        elif ROMM_DB_DRIVER == "postgresql":
            driver = "postgresql+psycopg"
        else:
            log.critical(f"{hl(ROMM_DB_DRIVER)} database not supported")
            sys.exit(3)

        if not DB_USER or not DB_PASSWD:
            log.critical(
                "Missing database credentials, check your environment variables!"
            )
            sys.exit(3)

        query: dict[str, str] = {}
        if DB_QUERY_JSON:
            try:
                query = json.loads(DB_QUERY_JSON)
            except ValueError as exc:
                log.critical(f"Invalid JSON in DB_QUERY_JSON: {exc}")
                sys.exit(3)

        return URL.create(
            drivername=driver,
            username=DB_USER,
            password=DB_PASSWD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            query=query,
        )

    def _parse_config(self):
        """Parses each entry in the config.yml"""

        self.config = Config(
            CONFIG_FILE_MOUNTED=self._config_file_mounted,
            CONFIG_FILE_WRITABLE=self._config_file_writable,
            EXCLUDED_PLATFORMS=pydash.get(self._raw_config, "exclude.platforms", []),
            EXCLUDED_SINGLE_EXT=[
                e.lower()
                for e in pydash.get(
                    self._raw_config, "exclude.roms.single_file.extensions", []
                )
            ],
            EXCLUDED_SINGLE_FILES=pydash.get(
                self._raw_config, "exclude.roms.single_file.names", []
            ),
            EXCLUDED_MULTI_FILES=pydash.get(
                self._raw_config, "exclude.roms.multi_file.names", []
            ),
            EXCLUDED_MULTI_PARTS_EXT=[
                e.lower()
                for e in pydash.get(
                    self._raw_config, "exclude.roms.multi_file.parts.extensions", []
                )
            ],
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
            SKIP_HASH_CALCULATION=pydash.get(
                self._raw_config, "filesystem.skip_hash_calculation", False
            ),
            EJS_DEBUG=pydash.get(self._raw_config, "emulatorjs.debug", False),
            EJS_CACHE_LIMIT=pydash.get(
                self._raw_config, "emulatorjs.cache_limit", None
            ),
            EJS_SETTINGS=pydash.get(self._raw_config, "emulatorjs.settings", {}),
            EJS_CONTROLS=self._get_ejs_controls(),
            SCAN_METADATA_PRIORITY=pydash.get(
                self._raw_config,
                "scan.priority.metadata",
                [
                    "igdb",
                    "moby",
                    "ss",
                    "ra",
                    "launchbox",
                    "gamelist",
                    "hasheous",
                    "tgdb",
                    "flashpoint",
                    "hltb",
                ],
            ),
            SCAN_ARTWORK_PRIORITY=pydash.get(
                self._raw_config,
                "scan.priority.artwork",
                [
                    "igdb",
                    "moby",
                    "ss",
                    "ra",
                    "launchbox",
                    "gamelist",
                    "hasheous",
                    "tgdb",
                    "flashpoint",
                    "hltb",
                ],
            ),
            SCAN_REGION_PRIORITY=pydash.get(
                self._raw_config,
                "scan.priority.region",
                ["us", "wor", "ss", "eu", "jp"],
            ),
            SCAN_LANGUAGE_PRIORITY=pydash.get(
                self._raw_config,
                "scan.priority.language",
                ["en", "fr"],
            ),
            SCAN_MEDIA=pydash.get(
                self._raw_config,
                "scan.media",
                [
                    "box2d",
                    "screenshot",
                    "manual",
                ],
            ),
        )

    def _get_ejs_controls(self) -> dict[str, EjsControls]:
        """Get EJS controls with default player entries for each core"""
        raw_controls = pydash.get(self._raw_config, "emulatorjs.controls", {})
        controls = {}

        for core, core_controls in raw_controls.items():
            # Create EjsControls object with default empty player dictionaries
            controls[core] = EjsControls(
                _0=core_controls.get(0, {}),
                _1=core_controls.get(1, {}),
                _2=core_controls.get(2, {}),
                _3=core_controls.get(3, {}),
            )

        return controls

    def _format_ejs_controls_for_yaml(
        self,
    ) -> dict[str, dict[int, dict[int, EjsControlsButton]]]:
        """Format EJS controls back to YAML structure for saving"""
        yaml_controls = {}

        for core, controls in self.config.EJS_CONTROLS.items():
            yaml_controls[core] = {
                0: controls["_0"],
                1: controls["_1"],
                2: controls["_2"],
                3: controls["_3"],
            }

        return yaml_controls

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

        if not isinstance(self.config.EJS_DEBUG, bool):
            log.critical("Invalid config.yml: emulatorjs.debug must be a boolean")
            sys.exit(3)

        if self.config.EJS_CACHE_LIMIT is not None and not isinstance(
            self.config.EJS_CACHE_LIMIT, int
        ):
            log.critical(
                "Invalid config.yml: emulatorjs.cache_limit must be an integer"
            )
            sys.exit(3)

        if not isinstance(self.config.EJS_SETTINGS, dict):
            log.critical("Invalid config.yml: emulatorjs.settings must be a dictionary")
            sys.exit(3)
        else:
            for core, options in self.config.EJS_SETTINGS.items():
                if not isinstance(options, dict):
                    log.critical(
                        f"Invalid config.yml: emulatorjs.settings.{core} must be a dictionary"
                    )
                    sys.exit(3)

        if not isinstance(self.config.EJS_CONTROLS, dict):
            log.critical("Invalid config.yml: emulatorjs.controls must be a dictionary")
            sys.exit(3)
        else:
            for core, controls in self.config.EJS_CONTROLS.items():
                if not isinstance(controls, dict):
                    log.critical(
                        f"Invalid config.yml: emulatorjs.controls.{core} must be a dictionary"
                    )
                    sys.exit(3)

                for player, buttons in controls.items():
                    if not isinstance(buttons, dict):
                        log.critical(
                            f"Invalid config.yml: emulatorjs.controls.{core}.{player} must be a dictionary"
                        )
                        sys.exit(3)

                    for button, value in buttons.items():
                        if not isinstance(value, dict):
                            log.critical(
                                f"Invalid config.yml: emulatorjs.controls.{core}.{player}.{button} must be a dictionary"
                            )
                            sys.exit(3)

        if not isinstance(self.config.SCAN_METADATA_PRIORITY, list):
            log.critical("Invalid config.yml: scan.priority.metadata must be a list")
            sys.exit(3)

        if not isinstance(self.config.SCAN_ARTWORK_PRIORITY, list):
            log.critical("Invalid config.yml: scan.priority.artwork must be a list")
            sys.exit(3)

        if not isinstance(self.config.SCAN_REGION_PRIORITY, list):
            log.critical("Invalid config.yml: scan.priority.region must be a list")
            sys.exit(3)

        if not isinstance(self.config.SCAN_LANGUAGE_PRIORITY, list):
            log.critical("Invalid config.yml: scan.priority.language must be a list")
            sys.exit(3)

        if not isinstance(self.config.SCAN_MEDIA, list):
            log.critical("Invalid config.yml: scan.media must be a list")
            sys.exit(3)

        for media in self.config.SCAN_MEDIA:
            if media not in MetadataMediaType:
                log.critical(
                    f"Invalid config.yml: scan.media.{media} is not a valid media type"
                )
                sys.exit(3)

    def get_config(self) -> Config:
        try:
            with open(self.config_file, "r") as config_file:
                self._raw_config = yaml.load(config_file, Loader=SafeLoader) or {}
        except FileNotFoundError:
            log.debug("Config file not found!")

        self._parse_config()
        self._validate_config()

        return self.config

    def _update_config_file(self) -> None:
        if not self._config_file_writable:
            log.warning("Config file not writable, skipping config file update")
            raise ConfigNotWritableException

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
            "filesystem": {
                "roms_folder": self.config.ROMS_FOLDER_NAME,
                "firmware_folder": self.config.FIRMWARE_FOLDER_NAME,
            },
            "system": {
                "platforms": self.config.PLATFORMS_BINDING,
                "versions": self.config.PLATFORMS_VERSIONS,
            },
            "emulatorjs": {
                "debug": self.config.EJS_DEBUG,
                "cache_limit": self.config.EJS_CACHE_LIMIT,
                "settings": self.config.EJS_SETTINGS,
                "controls": self._format_ejs_controls_for_yaml(),
            },
            "scan": {
                "priority": {
                    "metadata": self.config.SCAN_METADATA_PRIORITY,
                    "artwork": self.config.SCAN_ARTWORK_PRIORITY,
                    "region": self.config.SCAN_REGION_PRIORITY,
                    "language": self.config.SCAN_LANGUAGE_PRIORITY,
                },
            },
        }

        try:
            # Ensure the config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            with open(self.config_file, "w+") as config_file:
                yaml.dump(self._raw_config, config_file)
        except PermissionError as exc:
            log.critical("Config file not writable, skipping config file update")
            raise ConfigNotWritableException from exc

    def add_platform_binding(self, fs_slug: str, slug: str) -> None:
        platform_bindings = self.config.PLATFORMS_BINDING
        if fs_slug in platform_bindings:
            log.warning(f"Binding for {hl(fs_slug)} already exists")
            return None

        platform_bindings[fs_slug] = slug
        self.config.PLATFORMS_BINDING = platform_bindings
        self._update_config_file()

    def remove_platform_binding(self, fs_slug: str) -> None:
        platform_bindings = self.config.PLATFORMS_BINDING

        try:
            del platform_bindings[fs_slug]
        except KeyError:
            pass

        self.config.PLATFORMS_BINDING = platform_bindings
        self._update_config_file()

    def add_platform_version(self, fs_slug: str, slug: str) -> None:
        platform_versions = self.config.PLATFORMS_VERSIONS
        if fs_slug in platform_versions:
            log.warning(f"Version for {hl(fs_slug)} already exists")
            return None

        platform_versions[fs_slug] = slug
        self.config.PLATFORMS_VERSIONS = platform_versions
        self._update_config_file()

    def remove_platform_version(self, fs_slug: str) -> None:
        platform_versions = self.config.PLATFORMS_VERSIONS

        try:
            del platform_versions[fs_slug]
        except KeyError:
            pass

        self.config.PLATFORMS_VERSIONS = platform_versions
        self._update_config_file()

    def add_exclusion(self, exclusion_type: str, exclusion_value: str):
        config_item = self.config.__getattribute__(exclusion_type)
        if exclusion_value in config_item:
            log.warning(
                f"{hl(exclusion_value)} already excluded in {hl(exclusion_type, color=BLUE)}"
            )
            return None

        config_item.append(exclusion_value)
        self.config.__setattr__(exclusion_type, config_item)
        self._update_config_file()

    def remove_exclusion(self, exclusion_type: str, exclusion_value: str):
        config_item = self.config.__getattribute__(exclusion_type)

        try:
            config_item.remove(exclusion_value)
        except ValueError:
            pass

        self.config.__setattr__(exclusion_type, config_item)
        self._update_config_file()


config_manager = ConfigManager()
