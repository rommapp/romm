import os
import re
from abc import ABC
from enum import Enum
from typing import Final

from config.config_manager import config_manager as cm

TAG_REGEX = r"\(([^)]+)\)|\[([^]]+)\]"
EXTENSION_REGEX = r"\.(([a-z]+\.)*\w+)$"

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

    def get_roms_fs_structure(self, fs_slug: str) -> str:
        cnfg = cm.get_config()
        return (
            f"{cnfg.ROMS_FOLDER_NAME}/{fs_slug}"
            if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else f"{fs_slug}/{cnfg.ROMS_FOLDER_NAME}"
        )

    def get_firmware_fs_structure(self, fs_slug: str) -> str:
        cnfg = cm.get_config()
        return (
            f"{cnfg.FIRMWARE_FOLDER_NAME}/{fs_slug}"
            if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else f"{fs_slug}/{cnfg.FIRMWARE_FOLDER_NAME}"
        )

    def get_file_name_with_no_extension(self, file_name: str) -> str:
        return re.sub(EXTENSION_REGEX, "", file_name).strip()

    def get_file_name_with_no_tags(self, file_name: str) -> str:
        file_name_no_extension = self.get_file_name_with_no_extension(file_name)
        return re.split(TAG_REGEX, file_name_no_extension)[0].strip()

    def parse_file_extension(self, file_name) -> str:
        match = re.search(EXTENSION_REGEX, file_name)
        return match.group(1) if match else ""
