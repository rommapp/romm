from typing import Literal, NotRequired, TypedDict


# Per-account limits returned in `response.ssuser`
# Reference: https://api.screenscraper.fr/webapi2.php
class SSUser(TypedDict):
    id: NotRequired[str]
    niveau: NotRequired[str]
    maxthreads: NotRequired[str]
    maxrequestspermin: NotRequired[str]
    maxrequestsperday: NotRequired[str]
    requeststoday: NotRequired[str]
    maxrequestskoperday: NotRequired[str]
    requestskotoday: NotRequired[str]
    maxdownloadspeed: NotRequired[str]


class SSText(TypedDict):
    text: str


class SSTextID(TypedDict):
    id: str
    text: str


class SSRegionalText(TypedDict):
    region: str
    text: str


class SSLanguageText(TypedDict):
    langue: str
    text: str


class SSGameClassification(TypedDict):
    type: str
    text: str


class SSGameDate(TypedDict):
    region: str
    text: str


class SSGameGenre(TypedDict):
    id: str
    nomcourt: str
    principale: str
    parentid: str
    noms: list[SSLanguageText]


class SSGameMode(TypedDict):
    id: str
    nomcourt: str
    principale: str
    parentid: str
    noms: list[SSLanguageText]


class SSGameFranchise(TypedDict):
    id: str
    nomcourt: str
    principale: str
    parentid: str
    noms: list[SSLanguageText]


class SSGameMedia(TypedDict):
    type: str
    parent: str
    url: str
    region: str
    crc: str
    md5: str
    sha1: str
    size: str
    format: str


class SSRomRegions(TypedDict):
    """Parallel arrays, one entry per region, keyed by name language."""

    regions_shortname: NotRequired[list[str]]
    regions_en: NotRequired[list[str]]


class SSRomLanguages(TypedDict):
    """Parallel arrays, one entry per language, keyed by name language."""

    langues_shortname: NotRequired[list[str]]
    langues_en: NotRequired[list[str]]


class SSGameRom(TypedDict):
    """One dump of a game, as `jeu.roms` lists every dump ScreenScraper knows."""

    id: NotRequired[int]
    romfilename: NotRequired[str]
    romcrc: NotRequired[str]
    rommd5: NotRequired[str]
    romsha1: NotRequired[str]
    regions: NotRequired[SSRomRegions]
    langues: NotRequired[SSRomLanguages]
    # Sent as "1"/"0" strings. No `proto`: jeuInfos omits the key entirely,
    # unlike `demo` and `unl`, which it sends set to zero.
    beta: NotRequired[int]
    demo: NotRequired[int]
    trad: NotRequired[int]
    hack: NotRequired[int]
    unl: NotRequired[int]


# https://api.screenscraper.fr/webapi2.php#jeuInfos
class SSGame(TypedDict):
    id: int
    romid: str
    notgame: Literal["true", "false"]
    noms: list[SSRegionalText]
    cloneof: str
    systeme: SSTextID
    editeur: SSTextID
    developpeur: SSTextID
    joueurs: SSText
    note: SSText
    topstaff: str
    rotation: str
    synopsis: list[SSLanguageText]
    classifications: list[SSGameClassification]
    dates: list[SSGameDate]
    genres: list[SSGameGenre]
    modes: list[SSGameMode]
    familles: list[SSGameFranchise]
    medias: list[SSGameMedia]
    roms: NotRequired[list[SSGameRom]]
