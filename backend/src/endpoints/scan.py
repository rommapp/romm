from fastapi import APIRouter, status, HTTPException
import emoji
import json

from logger.logger import log, COLORS
from utils import fs, fastapi
from utils.exceptions import PlatformsNotFoundException, RomsNotFoundException
from handler import dbh
from models.platform import Platform
from models.rom import Rom

router = APIRouter()


@router.get("/scan", status_code=200)
def scan(platforms: str, complete_rescan: bool=False) -> dict:
    """Scan platforms and roms and write them in database."""

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fs.store_default_resources()

    # Scanning platforms
    try:
        fs_platforms: list[str] = fs.get_platforms()
    except PlatformsNotFoundException as e:
        error: str = f"{e}" 
        log.warning(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    
    platforms: list[str] = json.loads(platforms) if len(json.loads(platforms)) > 0 else fs_platforms
    log.info(f"Platforms to be scanned: {', '.join(platforms)}")
    for platform in platforms:
        log.info(emoji.emojize(f":video_game: {platform} {COLORS['reset']}"))
        scanned_platform: Platform = fastapi.scan_platform(platform)
        if platform != str(scanned_platform): log.info(f"Identified as {COLORS['blue']}{scanned_platform}{COLORS['reset']}")
        dbh.add_platform(scanned_platform)

        # Scanning roms
        try:
            fs_roms: list[str] = fs.get_roms(scanned_platform.fs_slug)
        except RomsNotFoundException as e:
            error: str = f"{e}" 
            log.warning(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        for rom in fs_roms:
            rom_id: int = dbh.rom_exists(scanned_platform.slug, rom['file_name'])
            if rom_id and not complete_rescan: continue
            log.info(f"Scanning {COLORS['orange']}{rom['file_name']}{COLORS['reset']}")
            if rom['multi']: [log.info(f"\t - {COLORS['orange_i']}{file}{COLORS['reset']}") for file in rom['files']]
            scanned_rom: Rom = fastapi.scan_rom(scanned_platform, rom)
            if rom_id: scanned_rom.id = rom_id
            dbh.add_rom(scanned_rom)
        dbh.purge_roms(scanned_platform.slug, [rom['file_name'] for rom in fs_roms])
    dbh.purge_platforms(fs_platforms)
    return {'msg': 'Scan completed successfully!'}