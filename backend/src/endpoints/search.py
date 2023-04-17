from fastapi import APIRouter, Request
import emoji

from logger.logger import log, COLORS
from handler import igdbh

router = APIRouter()


@router.put("/search/roms/igdb")
async def search_rom_igdb(req: Request, igdb_id: str = None) -> dict:
    """Get all the roms matched from igdb."""

    data: dict = await req.json()
    log.info(emoji.emojize(":magnifying_glass_tilted_right: IGDB Searching"))
    if igdb_id:
        log.info(f"Searching by id: {igdb_id}")
        matched_roms = igdbh.get_matched_roms_by_id(igdb_id)
    else:
        log.info(emoji.emojize(f":video_game: {data['rom']['p_slug']}: {COLORS['orange']}{data['rom']['file_name']}{COLORS['reset']}"))
        matched_roms = igdbh.get_matched_roms(data['rom']['file_name'], data['rom']['p_igdb_id'], data['rom']['p_slug'])
    log.info("Results:")
    [log.info(f"\t - {COLORS['blue']}{rom['r_name']}{COLORS['reset']}") for rom in matched_roms]
    return {'data': matched_roms}
