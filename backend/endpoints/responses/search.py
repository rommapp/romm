from handler.igdb_handler import IGDBRomType
from typing_extensions import TypedDict


class RomSearchResponse(TypedDict):
    msg: str
    roms: list[IGDBRomType]
