from fastapi import APIRouter, Request
import emoji

from logger.logger import log, COLORS
from handler import igdbh

router = APIRouter()


@router.put("/search/roms/igdb", status_code=200)
async def search_rom_igdb(
    req: Request, search_term: str = "", search_by: str = ""
) -> dict:
    """Get all the roms matched from igdb."""

    data: dict = await req.json()
    rom: dict = data["rom"]
    log.info(emoji.emojize(":magnifying_glass_tilted_right: IGDB Searching"))
    matched_roms: list = []

    if search_term:
        log.info(f"Searching by {search_by}: {search_term}")
        if search_by == "ID":
            matched_roms = igdbh.get_matched_roms_by_id(search_term)
        elif search_by == "Name":
            matched_roms = igdbh.get_matched_roms_by_name(search_term, rom["p_igdb_id"])
    else:
        log.info(
            emoji.emojize(
                f":video_game: {rom['p_slug']}: {COLORS['orange']}{rom['file_name']}{COLORS['reset']}"
            )
        )
        matched_roms = igdbh.get_matched_roms(rom["file_name"], rom["p_igdb_id"])

    log.info("Results:")

    [
        log.info(f"\t - {COLORS['blue']}{rom['r_name']}{COLORS['reset']}")
        for rom in matched_roms
    ]

    return {"roms": matched_roms, "msg": "success"}
