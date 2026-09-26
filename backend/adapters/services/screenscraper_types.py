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
    region: NotRequired[str]
    crc: str
    md5: str
    sha1: str
    size: NotRequired[str]
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

    id: NotRequired[str]
    romfilename: NotRequired[str]
    romcrc: NotRequired[str]
    rommd5: NotRequired[str]
    romsha1: NotRequired[str]
    regions: NotRequired[SSRomRegions]
    langues: NotRequired[SSRomLanguages]
    # Sent as "1"/"0" strings, typed for the int some platforms send instead.
    # No `proto`: jeuInfos omits the key entirely, unlike `demo` and `unl`,
    # which it sends set to zero.
    beta: NotRequired[int | str]
    demo: NotRequired[int | str]
    trad: NotRequired[int | str]
    hack: NotRequired[int | str]
    unl: NotRequired[int | str]


# https://api.screenscraper.fr/webapi2.php#jeuInfos
# jeuRecherche results carry only some of these fields.
class SSGame(TypedDict):
    id: str
    romid: NotRequired[str]
    notgame: NotRequired[Literal["true", "false"]]
    noms: list[SSRegionalText]
    cloneof: NotRequired[str]
    systeme: SSTextID
    editeur: NotRequired[SSTextID]
    developpeur: NotRequired[SSTextID]
    joueurs: NotRequired[SSText]
    note: NotRequired[SSText]
    topstaff: str | None
    rotation: str
    synopsis: NotRequired[list[SSLanguageText]]
    classifications: NotRequired[list[SSGameClassification]]
    dates: NotRequired[list[SSGameDate]]
    genres: NotRequired[list[SSGameGenre]]
    modes: NotRequired[list[SSGameMode]]
    familles: NotRequired[list[SSGameFranchise]]
    medias: list[SSGameMedia]
    roms: NotRequired[list[SSGameRom]]
