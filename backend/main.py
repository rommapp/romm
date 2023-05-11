import uvicorn
import emoji
import json
from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_socketio import SocketManager

from config import DEV_PORT, DEV_HOST
from logger.logger import log, COLORS
from utils import fs, fastapi
from utils.exceptions import PlatformsNotFoundException, RomsNotFoundException
from handler import dbh
from models.platform import Platform
from models.rom import Rom
from endpoints import search, platform, rom

app = FastAPI()
socket_manager = SocketManager(app=app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(search.router)
app.include_router(platform.router)
app.include_router(rom.router)


@app.sio.on("scan")
async def scan(sid, platforms: str, complete_rescan: bool=True):
    """Scan platforms and roms and write them in database."""

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fs.store_default_resources()

    try: # Scanning platforms
        fs_platforms: list[str] = fs.get_platforms()
    except PlatformsNotFoundException as e:
        error: str = f"{e}" 
        log.warning(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    
    platforms: list[str] = json.loads(platforms) if len(json.loads(platforms)) > 0 else fs_platforms
    log.info(f"Platforms to be scanned: {', '.join(platforms)}")
    for platform in platforms:
        await app.sio.emit('scanning_platform', platform)
        await app.sio.emit('') # Workaround to emit in real-time
        log.info(emoji.emojize(f":video_game: {platform} {COLORS['reset']}"))
        scanned_platform: Platform = fastapi.scan_platform(platform)
        if platform != str(scanned_platform): log.info(f"Identified as {COLORS['blue']}{scanned_platform}{COLORS['reset']}")
        dbh.add_platform(scanned_platform)

        try: # Scanning roms
            fs_roms: list[str] = fs.get_roms(scanned_platform.fs_slug)
        except RomsNotFoundException as e:
            error: str = f"{e}" 
            log.warning(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        for rom in fs_roms:
            rom_id: int = dbh.rom_exists(scanned_platform.slug, rom['file_name'])
            if rom_id and not complete_rescan: continue
            await app.sio.emit('scanning_rom', rom['file_name'])
            await app.sio.emit('') # Workaround to emit in real-time
            log.info(f"Scanning {COLORS['orange']}{rom['file_name']}{COLORS['reset']}")
            if rom['multi']: [log.info(f"\t - {COLORS['orange_i']}{file}{COLORS['reset']}") for file in rom['files']]
            scanned_rom: Rom = fastapi.scan_rom(scanned_platform, rom)
            if rom_id: scanned_rom.id = rom_id
            dbh.add_rom(scanned_rom)
        dbh.purge_roms(scanned_platform.slug, [rom['file_name'] for rom in fs_roms])
    dbh.purge_platforms(fs_platforms)
    await app.sio.emit('done')


@app.on_event("startup")
def startup() -> None:
    """Startup application."""
    pass


if __name__ == '__main__':
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
    # uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=False, workers=2)
