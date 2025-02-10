import fnmatch
import os
import re
from enum import Enum

from config.config_manager import config_manager as cm

TAG_REGEX = re.compile(r"\(([^)]+)\)|\[([^]]+)\]")
EXTENSION_REGEX = re.compile(r"\.(([a-z]+\.)*\w+)$")

LANGUAGES = (
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
)

REGIONS = (
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
)

REGIONS_BY_SHORTCODE = {region[0].lower(): region[1] for region in REGIONS}
REGIONS_NAME_KEYS = frozenset(region[1].lower() for region in REGIONS)

LANGUAGES_BY_SHORTCODE = {lang[0].lower(): lang[1] for lang in LANGUAGES}
LANGUAGES_NAME_KEYS = frozenset(lang[1].lower() for lang in LANGUAGES)


class CoverSize(Enum):
    SMALL = "small"
    BIG = "big"


class Asset(Enum):
    SAVES = "saves"
    STATES = "states"
    SCREENSHOTS = "screenshots"


class FSHandler:
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
        return EXTENSION_REGEX.sub("", file_name).strip()

    def get_file_name_with_no_tags(self, file_name: str) -> str:
        file_name_no_extension = self.get_file_name_with_no_extension(file_name)
        return TAG_REGEX.split(file_name_no_extension)[0].strip()

    def parse_file_extension(self, file_name) -> str:
        match = EXTENSION_REGEX.search(file_name)
        return match.group(1) if match else ""

    def _exclude_files(self, files, filetype) -> list[str]:
        cnfg = cm.get_config()
        excluded_extensions = getattr(cnfg, f"EXCLUDED_{filetype.upper()}_EXT")
        excluded_names = getattr(cnfg, f"EXCLUDED_{filetype.upper()}_FILES")
        excluded_files: list = []

        for file_name in files:
            # Split the file name to get the extension.
            ext = self.parse_file_extension(file_name)

            # Exclude the file if it has no extension or the extension is in the excluded list.
            if not ext or ext in excluded_extensions:
                excluded_files.append(file_name)

            # Additionally, check if the file name mathes a pattern in the excluded list.
            if len(excluded_names) > 0:
                for name in excluded_names:
                    if file_name == name or fnmatch.fnmatch(file_name, name):
                        excluded_files.append(file_name)

        # Return files that are not in the filtered list.
        return [f for f in files if f not in excluded_files]
