import emoji
import socketio  # type: ignore
from rq import Queue

from logger.logger import log
from utils import fs, fastapi
from exceptions.fs_exceptions import PlatformsNotFoundException, RomsNotFoundException
from handler import dbh
from utils.socket import socket_server
from utils.cache import redis_client, redis_url
from endpoints.platform import PlatformSchema
from endpoints.rom import RomSchema
from config import ENABLE_EXPERIMENTAL_REDIS

scan_queue = Queue(connection=redis_client)


async def scan_platforms(
    platform_slugs: list[str], complete_rescan: bool, selected_roms: list[str]
):
    # Connect to external socketio server
    sm = (
        socketio.AsyncRedisManager(redis_url, write_only=True)
        if ENABLE_EXPERIMENTAL_REDIS
        else socket_server
    )

    # Scanning file system
    try:
        fs_platforms: list[str] = fs.get_platforms()
    except PlatformsNotFoundException as e:
        log.error(e)
        await sm.emit("scan:done_ko", e.message)
        return

    platform_list = [dbh.get_platform(s).fs_slug for s in platform_slugs]
    platform_list = platform_list or fs_platforms
    for p_slug in platform_list:
        try:
            # Verify that platform exists
            scanned_platform = fastapi.scan_platform(p_slug)
        except RomsNotFoundException as e:
            log.error(e)
            continue

        new_platform = dbh.add_platform(scanned_platform)
        await sm.emit(
            "scan:scanning_platform", PlatformSchema.from_orm(new_platform).dict()
        )

        dbh.add_platform(scanned_platform)

        # Scanning roms
        fs_roms = fs.get_roms(scanned_platform.fs_slug)
        for fs_rom in fs_roms:
            rom_id = dbh.rom_exists(scanned_platform.slug, fs_rom["file_name"])
            if rom_id and rom_id not in selected_roms and not complete_rescan:
                continue

            scanned_rom = fastapi.scan_rom(scanned_platform, fs_rom)
            if rom_id:
                scanned_rom.id = rom_id

            rom = dbh.add_rom(scanned_rom)
            await sm.emit(
                "scan:scanning_rom",
                {
                    "p_name": scanned_platform.name,
                    **RomSchema.from_orm(rom).dict(),
                },
            )

        dbh.purge_roms(scanned_platform.slug, [rom["file_name"] for rom in fs_roms])
        dbh.update_n_roms(scanned_platform.slug)
    dbh.purge_platforms(fs_platforms)

    await sm.emit("scan:done", {})


@socket_server.on("scan")
async def scan_handler(_sid: str, options: dict):
    """Scan platforms and roms and write them in database."""

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fs.store_default_resources()

    platform_slugs = options.get("platforms", [])
    complete_rescan = options.get("rescan", False)
    selected_roms = options.get("roms", [])

    # Run in worker if redis is available
    if ENABLE_EXPERIMENTAL_REDIS:
        return scan_queue.enqueue(
            scan_platforms, platform_slugs, complete_rescan, selected_roms
        )
    else:
        await scan_platforms(platform_slugs, complete_rescan, selected_roms)
