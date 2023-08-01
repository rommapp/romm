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


def parse_tags(file_name: str) -> tuple:
    reg = ""
    rev = ""
    other_tags = []
    tags = re.findall("\(([^)]+)", file_name)

    for tag in tags:
        if tag.lower() in REGIONS_BY_SHORTCODE.keys():
            reg = REGIONS_BY_SHORTCODE[tag.lower()]
            continue

        if tag.lower() in REGIONS_NAME_KEYS:
            reg = tag
            continue

        if "reg" in tag.lower():
            match = re.match("^reg[\s|-](.*)$", tag, re.IGNORECASE)
            if match:
                reg = (
                    REGIONS_BY_SHORTCODE[match.group(1).lower()]
                    if match.group(1).lower() in REGIONS_BY_SHORTCODE.keys()
                    else match.group(1)
                )
                continue

        if "rev" in tag.lower():
            match = re.match("^rev[\s|-](.*)$", tag, re.IGNORECASE)
            if match:
                rev = match.group(1)
                continue

        other_tags.append(tag)
    return reg, rev, other_tags


def get_file_name_with_no_tags(file_name: str) -> str:
    # Use .rsplit to remove only the file extension
    return re.sub("[\(\[].*?[\)\]]", "", file_name.rsplit(".", 1)[0])


def get_file_extension(rom: dict) -> str:
    return rom["file_name"].split(".")[-1] if not rom["multi"] else ""
