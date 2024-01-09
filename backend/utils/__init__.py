import re
import requests
import subprocess as sp
from packaging.version import parse, InvalidVersion
from __version__ import __version__

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
    tags = [tag for subtags in tags for tag in subtags.split(",")]
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


def get_file_name_with_no_tags(file_name: str) -> str:
    file_name_no_extension = re.sub(EXTENSION_REGEX, "", file_name).strip()
    return re.sub(TAG_REGEX, "", file_name_no_extension).strip()


def normalize_search_term(search_term: str) -> str:
    return (
        search_term.replace("\u2122", "")  # Remove trademark symbol
        .replace("\u00ae", "")  # Remove registered symbol
        .replace("\u00a9", "")  # Remove copywrite symbol
        .replace("\u2120", "")  # Remove service mark symbol
        .strip()  # Remove leading and trailing spaces
    )


def get_file_extension(rom: dict) -> str:
    if rom["multi"]:
        return ""

    match = re.search(EXTENSION_REGEX, rom["file_name"])
    return match.group(1) if match else ""


def get_version() -> str | None:
    """Returns current version or branch name."""
    if not __version__ == "<version>":
        return __version__
    else:
        try:
            output = str(sp.check_output(["git", "branch"], universal_newlines=True))
        except sp.CalledProcessError:
            return None
        branch = [a for a in output.split("\n") if a.find("*") >= 0][0]
        return branch[branch.find("*") + 2 :]
    

def check_new_version() -> str | None:
    response = requests.get("https://api.github.com/repos/zurdi15/romm/releases/latest", timeout=0.5)
    try:
        last_version = response.json()["name"][1:] # remove leading 'v' from 'vX.X.X'
    except KeyError: # rate limit reached
        return None
    try:
        if parse(get_version()) < parse(last_version):
            return last_version
    except InvalidVersion:
        pass
    return None
