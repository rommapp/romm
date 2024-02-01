import emoji
import socketio  # type: ignore
from endpoints.platform import PlatformSchema
from endpoints.rom import RomSchema
from exceptions.fs_exceptions import (
    FolderStructureNotMatchException,
    RomsNotFoundException,
)
from handler import (
    db_platform_handler,
    db_rom_handler,
    fs_platform_handler,
    fs_resource_handler,
    fs_rom_handler,
    socket_handler,
)
from handler.redis_handler import high_prio_queue, redis_url
from handler.scan_handler import (
    scan_platform,
    scan_rom,
)
from logger.logger import log


def _get_socket_manager():
    # Connect to external socketio server
    return socketio.AsyncRedisManager(redis_url, write_only=True)


async def scan_platforms(
    platform_ids: list[int],
    complete_rescan: bool = False,
    rescan_unidentified: bool = False,
    selected_roms: list[str] = (),
):
    """Scan all the listed platforms and fetch metadata from different sources

    Args:
        platform_slugs (list[str]): List of platform slugs to be scanned
        complete_rescan (bool, optional): Flag to rescan already scanned platforms. Defaults to False.
        rescan_unidentified (bool, optional): Flag to rescan only unidentified roms. Defaults to False.
        selected_roms (list[str], optional): List of selected roms to be scanned. Defaults to ().
    """

    sm = _get_socket_manager()

    # Scanning file system
    try:
        fs_platforms: list[str] = fs_platform_handler.get_platforms()
    except FolderStructureNotMatchException as e:
        log.error(e)
        await sm.emit("scan:done_ko", e.message)
        return

    platform_list = [
        db_platform_handler.get_platforms(s).fs_slug for s in platform_ids
    ] or fs_platforms

    if len(platform_list) == 0:
        log.warn(
            "⚠️ No platforms found, verify that the folder structure is right and the volume is mounted correctly "
        )
    else:
        log.info(f"Found {len(platform_list)} platforms in file system ")

    for platform_slug in platform_list:
        platform = db_platform_handler.get_platform_by_slug(platform_slug)
        scanned_platform = scan_platform(platform_slug, fs_platforms)

        if platform:
            scanned_platform.id = platform.id

        platform = db_platform_handler.add_platform(scanned_platform)

        await sm.emit(
            "scan:scanning_platform",
            PlatformSchema.model_validate(platform).model_dump(),
        )

        # Scanning roms
        try:
            fs_roms = fs_rom_handler.get_roms(platform)
        except RomsNotFoundException as e:
            log.error(e)
            continue

        if len(fs_roms) == 0:
            log.warning(
                "  ⚠️ No roms found, verify that the folder structure is correct"
            )
        else:
            log.info(f"  {len(fs_roms)} roms found")

        for fs_rom in fs_roms:
            rom = db_rom_handler.get_rom_by_filename(platform.id, fs_rom["file_name"])
            if (
                not rom
                or rom.id in selected_roms
                or complete_rescan
                or (rescan_unidentified and not rom.igdb_id)
            ):
                scanned_rom = await scan_rom(platform, fs_rom)
                if rom:
                    scanned_rom.id = rom.id

                scanned_rom.platform_id = platform.id
                _added_rom = db_rom_handler.add_rom(scanned_rom)
                rom = db_rom_handler.get_roms(_added_rom.id)

                await sm.emit(
                    "scan:scanning_rom",
                    {
                        "platform_name": platform.name,
                        "platform_slug": platform.slug,
                        **RomSchema.model_validate(rom).model_dump(),
                    },
                )

            db_rom_handler.purge_roms(
                platform.id, [rom["file_name"] for rom in fs_roms]
            )
    db_platform_handler.purge_platforms(fs_platforms)

    log.info(emoji.emojize(":check_mark:  Scan completed "))

    await sm.emit("scan:done", {})


@socket_handler.socket_server.on("scan")
async def scan_handler(_sid: str, options: dict):
    """Scan socket endpoint

    Args:
        options (dict): Socket options
    """

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fs_resource_handler.store_default_resources()

    platform_slugs = options.get("platforms", [])
    complete_rescan = options.get("completeRescan", False)
    rescan_unidentified = options.get("rescanUnidentified", False)
    selected_roms = options.get("roms", [])

    # Run in worker if redis is available
    return high_prio_queue.enqueue(
        scan_platforms,
        platform_slugs,
        complete_rescan,
        rescan_unidentified,
        selected_roms,
        job_timeout=14400,  # Timeout after 4 hours
    )
