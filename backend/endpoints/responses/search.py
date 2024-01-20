from handler.igdb_handler import IGDBRom
from typing_extensions import TypedDict


class RomSearchResponse(TypedDict):
    msg: str
    roms: list[IGDBRom]
