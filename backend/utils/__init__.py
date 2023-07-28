import re


LANGUAGES = [
    "Ar",
    "Da",
    "De",
    "En",
    "En-US",
    "Es",
    "Fi",
    "Fr",
    "It",
    "Ja",
    "Ko",
    "Nl",
    "Pl",
    "Pt",
    "Pt-BR",
    "Ru",
    "Sv",
    "Zh",
    "Zh-Hans",
    "Zh-Hant",
    "nolang",
]

REGIONS = [
    ("U", "USA"),
    ("E", "Europe"),
    ("J", "Japan"),
    ("K", "Korea"),
    ("T", "Taiwan"),
    ("G", "Germany"),
    ("B", "Brazil"),
    ("A", "Australia"),
    ("CH", "China"),
    ("NL", "Netherlands"),
    ("PD", "Public Domain"),
    ("F", "France"),
    ("S", "Spain"),
    ("W", "World"),
    ("C", "Canada"),
    ("SW", "Sweden"),
    ("FN", "Finland"),
    ("UK", "England"),
    ("GR", "Greece"),
    ("UNK", "Unknown"),
    ("HK", "Hong Kong"),
    ("I", "Italy"),
    ("H", "Holland"),
    ("UNL", "Unlicensed"),
    ("AS", "Asia"),
    ("R", "Russia"),
    ("NO", "Norway"),
]

REGIONS_BY_SHORTCODE = {region[0].lower(): region[1] for region in REGIONS}
REGIONS_NAME_KEYS = [region[1].lower() for region in REGIONS]


def parse_tags(file_name: str) -> tuple:
    reg = ""
    rev = ""
    other_tags = []
    tags = re.findall("\(([^)]+)", file_name)

    for tag in tags:
        if tag.lower() in REGIONS_BY_SHORTCODE.keys():
            reg = REGIONS_BY_SHORTCODE[tag.lower()]
        elif tag.lower() in REGIONS_NAME_KEYS:
            reg = tag
        # Explicit support for "Rev A/Rev 1" tags
        elif "rev " in tag.lower():
            rev = tag.split(" ")[1]
        else:
            other_tags.append(tag)
    return reg, rev, other_tags


def get_file_name_with_no_tags(file_name: str) -> str:
    # Use .rsplit to remove only the file extension
    return re.sub("[\(\[].*?[\)\]]", "", file_name.rsplit(".", 1)[0])


def get_file_extension(rom: dict) -> str:
    return rom["file_name"].split(".")[-1] if not rom["multi"] else ""
