import emoji
from fastapi import APIRouter, Request
from starlette.authentication import requires

from logger.logger import log
from handler import igdbh

router = APIRouter()


@router.put("/search/roms/igdb")
@requires(["roms.read"])
async def search_rom_igdb(
    request: Request, search_term: str = "", search_by: str = ""
) -> dict:
    """Get all the roms matched from igdb."""

    data: dict = await request.json()
    rom: dict = data["rom"]
    log.info(emoji.emojize(":magnifying_glass_tilted_right: IGDB Searching"))
    matched_roms: list = []

    log.info(f"Searching by {search_by}: {search_term}")
    log.info(emoji.emojize(f":video_game: {rom['p_slug']}: {rom['file_name']}"))
    if search_by.lower() == "id":
        matched_roms = igdbh.get_matched_roms_by_id(int(search_term))
    elif search_by.lower() == "name":
        matched_roms = igdbh.get_matched_roms_by_name(search_term, rom["p_igdb_id"])

    log.info("Results:")
    for rom in matched_roms:
        log.info(f"\t - {rom['r_name']}")

    return {"roms": matched_roms, "msg": "success"}
