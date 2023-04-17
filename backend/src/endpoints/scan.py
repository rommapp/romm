from fastapi import APIRouter
import emoji
import json

from logger.logger import log, COLORS
from utils import fs, fastapi
from handler import dbh
from models.platform import Platform

router = APIRouter()


@router.get("/scan")
def scan(platforms: str, full_scan: bool=False) -> dict:
    """Scan platforms and roms and write them in database."""

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fs.store_default_resources()
    fs_platforms: list[str] = fs.get_platforms()
    platforms: list[str] = json.loads(platforms) if len(json.loads(platforms)) > 0 else fs_platforms
    log.info(f"Platforms to be scanned: {', '.join(platforms)}")
    for p_slug in platforms:
        log.info(emoji.emojize(f":video_game: {p_slug} {COLORS['reset']}"))
        platform: Platform = fastapi.scan_platform(p_slug)
        if p_slug != str(platform): log.info(f"Identified as {COLORS['blue']}{platform}{COLORS['reset']}")
        dbh.add_platform(platform)
        log.info(f"Searching new roms")
        roms: list[dict] = fs.get_roms(p_slug, full_scan)
        for rom in roms:
            log.info(f"Getting {COLORS['orange']}{rom['file_name']}{COLORS['reset']} details")
            if rom['multi']: [log.info(f"\t - {COLORS['orange_i']}{file}{COLORS['reset']}") for file in rom['files']]
            rom = fastapi.scan_rom(platform, rom)
            dbh.add_rom(rom)    
    log.info(emoji.emojize(":wastebasket:  Purging database"))
    [dbh.purge_roms(p_slug, fs.get_roms(p_slug, True)) for p_slug in platforms]
    dbh.purge_platforms(fs_platforms)
    return {'msg': 'success'}