import emoji
from fastapi import APIRouter, Request
from typing_extensions import TypedDict

from logger.logger import log
from handler import igdbh, dbh
from handler.igdb_handler import IGDBRomType
from utils.oauth import protected_route

router = APIRouter()


class RomSearchResponse(TypedDict):
    msg: str
    roms: list[IGDBRomType]


@protected_route(router.put, "/search/roms/igdb", ["roms.read"])
async def search_rom_igdb(
    request: Request, rom_id: str, query: str = None, field: str = "Name"
) -> RomSearchResponse:
    """Search IGDB for ROMs"""

    rom = dbh.get_rom(rom_id)
    query = query or rom.file_name_no_tags

    log.info(emoji.emojize(":magnifying_glass_tilted_right: IGDB Searching"))
    matched_roms: list = []

    log.info(f"Searching by {field}: {query}")
    log.info(emoji.emojize(f":video_game: {rom.platform_slug}: {rom.file_name}"))
    if query.lower() == "id":
        matched_roms = igdbh.get_matched_roms_by_id(int(field))
    elif query.lower() == "name":
        matched_roms = igdbh.get_matched_roms_by_name(field, rom.platform.igdb_id)

    log.info("Results:")
    for m_rom in matched_roms:
        log.info(f"\t - {m_rom['name']}")

    return {"roms": matched_roms, "msg": "success"}
