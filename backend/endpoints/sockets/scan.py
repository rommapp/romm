import emoji
import socketio  # type: ignore
from config import ENABLE_EXPERIMENTAL_REDIS
from endpoints.platform import PlatformSchema
from endpoints.rom import RomSchema
from exceptions.fs_exceptions import (
    FolderStructureNotMatchException,
    RomsNotFoundException,
)
from handler import (
    db_platform_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
    fs_asset_handler,
    fs_platform_handler,
    fs_resource_handler,
    fs_rom_handler,
    socket_handler,
)
from handler.fs_handler import Asset
from handler.redis_handler import high_prio_queue, redis_url
from handler.scan_handler import (
    scan_platform,
    scan_rom,
    scan_save,
    scan_screenshot,
    scan_state,
)
from logger.logger import log


def _get_socket_manager():
    # Connect to external socketio server
    return (
        socketio.AsyncRedisManager(redis_url, write_only=True)
        if ENABLE_EXPERIMENTAL_REDIS
        else socket_handler.socket_server
    )


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
            if not rom or rom.id in selected_roms or complete_rescan or (rescan_unidentified and not rom.igdb_id):
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

            # Scanning saves
            fs_saves = fs_asset_handler.get_assets(
                platform.fs_slug, rom.file_name_no_ext, Asset.SAVES
            )
            if len(fs_saves) > 0:
                log.info(f"\t · {len(fs_saves)} saves found")
           
            for fs_emulator, fs_save_filename in fs_saves:
                scanned_save = scan_save(
                    platform=platform,
                    file_name=fs_save_filename,
                    emulator=fs_emulator,
                )

                save = db_save_handler.get_save_by_filename(rom.id, fs_save_filename)
                if save:
                    # Update file size if changed
                    if save.file_size_bytes != scanned_save.file_size_bytes:
                        db_save_handler.update_save(
                            save.id, {"file_size_bytes": scanned_save.file_size_bytes}
                        )
                    continue

                scanned_save.emulator = fs_emulator

                if rom:
                    scanned_save.rom_id = rom.id
                    db_save_handler.add_save(scanned_save)

            # Scanning states
            fs_states = fs_asset_handler.get_assets(
                platform.fs_slug, rom.file_name_no_ext, Asset.STATES
            )
            if len(fs_states) > 0:
                log.info(f"\t · {len(fs_states)} states found")

            for fs_emulator, fs_state_filename in fs_states:
                scanned_state = scan_state(
                    platform=platform,
                    emulator=fs_emulator,
                    file_name=fs_state_filename,
                )

                state = db_state_handler.get_state_by_filename(rom.id, fs_state_filename)
                if state:
                    # Update file size if changed
                    if state.file_size_bytes != scanned_state.file_size_bytes:
                        db_state_handler.update_state(
                            state.id, {"file_size_bytes": scanned_state.file_size_bytes}
                        )

                    continue

                scanned_state.emulator = fs_emulator

                if rom:
                    scanned_state.rom_id = rom.id
                    db_state_handler.add_state(scanned_state)

            # Scanning screenshots
            fs_screenshots = fs_asset_handler.get_assets(
                platform.fs_slug, rom.file_name_no_ext, Asset.SCREENSHOTS
            )
            if len(fs_screenshots) > 0:
                log.info(f"\t · {len(fs_screenshots)} screenshots found")
            
            for _, fs_screenshot_filename in fs_screenshots:
                scanned_screenshot = scan_screenshot(
                    file_name=fs_screenshot_filename, platform_slug=platform.fs_slug
                )

                screenshot = db_screenshot_handler.get_screenshot_by_filename(
                    fs_screenshot_filename
                )
                if screenshot:
                    # Update file size if changed
                    if screenshot.file_size_bytes != scanned_screenshot.file_size_bytes:
                        db_screenshot_handler.update_screenshot(
                            screenshot.id,
                            {"file_size_bytes": scanned_screenshot.file_size_bytes},
                        )
                    continue

                if rom:
                    scanned_screenshot.rom_id = rom.id
                    db_screenshot_handler.add_screenshot(scanned_screenshot)

            db_save_handler.purge_saves(rom.id, [s for _e, s in fs_saves])
            db_state_handler.purge_states(rom.id, [s for _e, s in fs_states])
            db_screenshot_handler.purge_screenshots(rom.id, [s for _e, s in fs_screenshots])
            db_rom_handler.purge_roms(platform.id, [rom["file_name"] for rom in fs_roms])

    # Scanning screenshots outside platform folders
    fs_screenshots = fs_asset_handler.get_screenshots()
    log.info("Screenshots")
    log.info(f" · {len(fs_screenshots)} screenshots found")
    for fs_platform, fs_screenshot_filename in fs_screenshots:
        scanned_screenshot = scan_screenshot(
            file_name=fs_screenshot_filename, platform_slug=fs_platform
        )

        screenshot = db_screenshot_handler.get_screenshot_by_filename(fs_screenshot_filename)
        if screenshot:
            # Update file size if changed
            if screenshot.file_size_bytes != scanned_screenshot.file_size_bytes:
                db_screenshot_handler.update_screenshot(
                    screenshot.id,
                    {"file_size_bytes": scanned_screenshot.file_size_bytes},
                )
            continue

        rom = db_rom_handler.get_rom_by_filename_no_tags(scanned_screenshot.file_name_no_tags)
        if rom:
            scanned_screenshot.rom_id = rom.id
            db_screenshot_handler.add_screenshot(scanned_screenshot)

    # db_screenshot_handler.purge_screenshots([s for _e, s in fs_screenshots])
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
    if ENABLE_EXPERIMENTAL_REDIS:
        return high_prio_queue.enqueue(
            scan_platforms,
            platform_slugs,
            complete_rescan,
            rescan_unidentified,
            selected_roms,
            job_timeout=14400,  # Timeout after 4 hours
        )
    else:
        await scan_platforms(
            platform_slugs, complete_rescan, rescan_unidentified, selected_roms
        )
