import emoji
from fastapi import APIRouter, Request

from logger.logger import log
from handler import igdbh, dbh
from utils.oauth import protected_route

router = APIRouter()


@protected_route(router.put, "/search/roms/igdb", ["roms.read"])
async def search_rom_igdb(request: Request) -> dict:
    """Search IGDB for ROMs"""

    data: dict = await request.json()
    romId: dict = data["romId"]
    rom = dbh.get_rom(romId)

    query: str = data.get("query", rom.file_name_no_tags)
    field: str = data.get("field", "Name")

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
