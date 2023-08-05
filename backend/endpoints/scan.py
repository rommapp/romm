import emoji
import socketio
from rq import Queue

from logger.logger import log
from utils import fs, fastapi
from utils.exceptions import PlatformsNotFoundException, RomsNotFoundException
from handler import dbh
from models.rom import Rom
from handler.socket_manager import socket_server
from worker import redis_conn, redis_url


scan_queue = Queue(connection=redis_conn)


async def scan_platforms(paltforms: str, complete_rescan: bool):
    # Connect to external socketio server
    sm = socketio.AsyncRedisManager(redis_url, write_only=True)

    # Scanning file system
    try:
        fs_platforms: list[str] = fs.get_platforms()
    except PlatformsNotFoundException as e:
        log.error(e)
        await socket_server.emit("scan:done_ko", e.message)
        return

    platform_list = paltforms.split(",") if paltforms else fs_platforms
    for p_slug in platform_list:
        try:
            # Verify that platform exists
            scanned_platform = fastapi.scan_platform(p_slug)
        except RomsNotFoundException as e:
            log.error(e)
            return

        await sm.emit(
            "scan:scanning_platform",
            {"p_name": scanned_platform.name, "p_slug": scanned_platform.slug},
        )

        dbh.add_platform(scanned_platform)

        # Scanning roms
        fs_roms: list[str] = fs.get_roms(scanned_platform.fs_slug)
        for rom in fs_roms:
            rom_id: int = dbh.rom_exists(scanned_platform.slug, rom["file_name"])
            if rom_id and not complete_rescan:
                continue

            scanned_rom: Rom = fastapi.scan_rom(scanned_platform, rom)
            await sm.emit(
                "scan:scanning_rom",
                {
                    "p_slug": scanned_platform.slug,
                    "p_name": scanned_platform.name,
                    "file_name": scanned_rom.file_name,
                    "r_name": scanned_rom.r_name,
                },
            )

            if rom_id:
                scanned_rom.id = rom_id

            dbh.add_rom(scanned_rom)
        dbh.purge_roms(scanned_platform.slug, [rom["file_name"] for rom in fs_roms])
    dbh.purge_platforms(fs_platforms)

    await sm.emit("scan:done", {})


@socket_server.on("scan")
async def scan_handler(_sid: str, platforms: str, complete_rescan: bool = True):
    """Scan platforms and roms and write them in database."""

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fs.store_default_resources()

    # Queue up a job for each platform
    scan_queue.enqueue(scan_platforms, platforms, complete_rescan)
