import os
import re
import shutil
from abc import ABC
from enum import Enum
from typing import Final

from config import LIBRARY_BASE_PATH, ROMM_BASE_PATH
from config.config_manager import config_manager as cm

RESOURCES_BASE_PATH: Final = f"{ROMM_BASE_PATH}/resources"
DEFAULT_WIDTH_COVER_L: Final = 264  # Width of big cover of IGDB
DEFAULT_HEIGHT_COVER_L: Final = 352  # Height of big cover of IGDB
DEFAULT_WIDTH_COVER_S: Final = 90  # Width of small cover of IGDB
DEFAULT_HEIGHT_COVER_S: Final = 120  # Height of small cover of IGDB

LANGUAGES = [
    ("Ar", "Arabic"),
    ("Da", "Danish"),
    ("De", "German"),
    ("En", "English"),
    ("Es", "Spanish"),
    ("Fi", "Finnish"),
    ("Fr", "French"),
    ("It", "Italian"),
    ("Ja", "Japanese"),
    ("Ko", "Korean"),
    ("Nl", "Dutch"),
    ("No", "Norwegian"),
    ("Pl", "Polish"),
    ("Pt", "Portuguese"),
    ("Ru", "Russian"),
    ("Sv", "Swedish"),
    ("Zh", "Chinese"),
    ("nolang", "No Language"),
]

REGIONS = [
    ("A", "Australia"),
    ("AS", "Asia"),
    ("B", "Brazil"),
    ("C", "Canada"),
    ("CH", "China"),
    ("E", "Europe"),
    ("F", "France"),
    ("FN", "Finland"),
    ("G", "Germany"),
    ("GR", "Greece"),
    ("H", "Holland"),
    ("HK", "Hong Kong"),
    ("I", "Italy"),
    ("J", "Japan"),
    ("K", "Korea"),
    ("NL", "Netherlands"),
    ("NO", "Norway"),
    ("PD", "Public Domain"),
    ("R", "Russia"),
    ("S", "Spain"),
    ("SW", "Sweden"),
    ("T", "Taiwan"),
    ("U", "USA"),
    ("UK", "England"),
    ("UNK", "Unknown"),
    ("UNL", "Unlicensed"),
    ("W", "World"),
]

REGIONS_BY_SHORTCODE = {region[0].lower(): region[1] for region in REGIONS}
REGIONS_NAME_KEYS = [region[1].lower() for region in REGIONS]

LANGUAGES_BY_SHORTCODE = {lang[0].lower(): lang[1] for lang in LANGUAGES}
LANGUAGES_NAME_KEYS = [lang[1].lower() for lang in LANGUAGES]

TAG_REGEX = r"\(([^)]+)\)|\[([^]]+)\]"
EXTENSION_REGEX = r"\.(([a-z]+\.)*\w+)$"


class CoverSize(Enum):
    SMALL = "small"
    BIG = "big"


class Asset(Enum):
    SAVES = "saves"
    STATES = "states"
    SCREENSHOTS = "screenshots"


class FSHandler(ABC):
    def __init__(self) -> None:
        pass

    @staticmethod
    def get_fs_structure(fs_slug: str, folder: str = cm.config.ROMS_FOLDER_NAME):
        return (
            f"{folder}/{fs_slug}"
            if os.path.exists(cm.config.HIGH_PRIO_STRUCTURE_PATH)
            else f"{fs_slug}/{folder}"
        )

    @staticmethod
    def get_file_name_with_no_extension(file_name: str) -> str:
        return re.sub(EXTENSION_REGEX, "", file_name).strip()

    @staticmethod
    def get_file_name_with_no_tags(file_name: str) -> str:
        file_name_no_extension = re.sub(EXTENSION_REGEX, "", file_name).strip()
        return re.split(TAG_REGEX, file_name_no_extension)[0].strip()

    @staticmethod
    def parse_file_extension(file_name) -> str:
        match = re.search(EXTENSION_REGEX, file_name)
        return match.group(1) if match else ""

    @staticmethod
    def remove_file(file_name: str, file_path: str):
        try:
            os.remove(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")
        except IsADirectoryError:
            shutil.rmtree(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")

    def build_upload_file_path(
        self, fs_slug: str, folder: str = cm.config.ROMS_FOLDER_NAME
    ):
        rom_path = self.get_fs_structure(fs_slug, folder=folder)
        return f"{LIBRARY_BASE_PATH}/{rom_path}"
