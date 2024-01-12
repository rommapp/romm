from enum import Enum
from typing import Final

from config import ROMM_BASE_PATH

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
