import re
import numpy as np

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


def parse_tags(file_name: str) -> tuple:
    rev = ""
    regs = []
    langs = []
    other_tags = []
    tags = [tag[0] or tag[1] for tag in re.findall(TAG_REGEX, file_name)]
    tags = np.array([tag.split(",") for tag in tags]).flatten()
    tags = [tag.strip() for tag in tags]

    for tag in tags:
        if tag.lower() in REGIONS_BY_SHORTCODE.keys():
            regs.append(REGIONS_BY_SHORTCODE[tag.lower()])
            continue

        if tag.lower() in REGIONS_NAME_KEYS:
            regs.append(tag)
            continue

        if tag.lower() in LANGUAGES_BY_SHORTCODE.keys():
            langs.append(LANGUAGES_BY_SHORTCODE[tag.lower()])
            continue

        if tag.lower() in LANGUAGES_NAME_KEYS:
            langs.append(tag)
            continue

        if "reg" in tag.lower():
            match = re.match(r"^reg[\s|-](.*)$", tag, re.IGNORECASE)
            if match:
                regs.append(
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
    return regs, rev, langs, other_tags


def get_file_name_with_no_extension(file_name: str) -> str:
    return re.sub(EXTENSION_REGEX, "", file_name).strip()


def get_file_name_with_no_tags(file_name: str) -> str:
    file_name_no_extension = get_file_name_with_no_extension(file_name)
    return re.split(TAG_REGEX, file_name_no_extension)[0].strip()


def get_file_extension(file_name: str) -> str:
    return re.search(EXTENSION_REGEX, file_name).group(1)
