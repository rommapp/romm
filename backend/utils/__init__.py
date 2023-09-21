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
    tags = re.findall(r"\(([^)]+)", file_name)

    for tag in tags:
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
    # \[[^\]]+\]: Matches tags enclosed in square brackets, e.g., [rel-1]
    # \([^)]+\): Matches tags enclosed in parentheses, e.g., (USA)
    # (\.\w+)+$: Matches one or more file extensions, e.g., .zip or .nkit.iso
    tags_extension_regex = r"(\s*\[[^\]]+\]\s*|\s*\([^)]+\)\s*)*(\.\w+)+$"

    # The regex is aggressive and may remove some of the title,
    # but that's prefered over leaving tags/extensions in the title
    return re.sub(tags_extension_regex, "", file_name).strip()


def get_file_extension(rom: dict) -> str:
    extension_regex = r"(\.\w+)+$"
    return (
        re.search(extension_regex, rom["file_name"]).group(0)
        if not rom["multi"]
        else ""
    )
