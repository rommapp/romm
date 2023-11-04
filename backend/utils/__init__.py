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

TAG_REGEX = r"\(([^)]+)\)|\[([^]]+)\]"
EXTENSION_REGEX = r"\.(\w+(\.\w+)*)$"


def parse_tags(file_name: str) -> tuple:
    reg = ""
    rev = ""
    other_tags = []
    tags = re.findall(TAG_REGEX, file_name)

    for p_tag, s_tag in tags:
        tag = p_tag or s_tag

        if tag.lower() in REGIONS_BY_SHORTCODE.keys():
            reg = REGIONS_BY_SHORTCODE[tag.lower()]
            continue

        if tag.lower() in REGIONS_NAME_KEYS:
            reg = tag
            continue

        if "reg" in tag.lower():
            match = re.match(r"^reg[\s|-](.*)$", tag, re.IGNORECASE)
            if match:
                reg = (
                    REGIONS_BY_SHORTCODE[match.group(1).lower()]
                    if match.group(1).lower() in REGIONS_BY_SHORTCODE.keys()
                    else match.group(1)
                )
                continue

        if "rev" in tag.lower():
            match = re.match(r"^rev[\s|-](.*)$", tag, re.IGNORECASE)
            if match:
                rev = match.group(1)
                continue

        other_tags.append(tag)
    return reg, rev, other_tags


def get_file_name_with_no_tags(file_name: str) -> str:
    file_name_no_extension = re.sub(EXTENSION_REGEX, "", file_name).strip()
    return re.sub(TAG_REGEX, "", file_name_no_extension).strip()


def get_file_extension(rom: dict) -> str:
    return (
        re.search(EXTENSION_REGEX, rom["file_name"]).group(1)
        if not rom["multi"]
        else ""
    )
