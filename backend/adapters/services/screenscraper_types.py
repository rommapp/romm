from typing import Literal, NotRequired, TypedDict


# Per-account limits returned in `response.ssuser`. Contributors/donors get a
# higher `maxthreads` allowance. All values arrive as strings.
# Reference: https://api.screenscraper.fr/webapi2.php
class SSUser(TypedDict):
    id: NotRequired[str]
    niveau: NotRequired[str]
    maxthreads: NotRequired[str]
    maxrequestspermin: NotRequired[str]
    maxrequestsperday: NotRequired[str]
    requeststoday: NotRequired[str]


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
