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
    dbplatformh,
    dbromh,
    dbsaveh,
    dbscreenshotsh,
    dbstateh,
    fsasseth,
    fsplatformh,
    fsresourceh,
    fsromh,
    socketh,
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
        else socketh.socket_server
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
        fs_platforms: list[str] = fsplatformh.get_platforms()
    except FolderStructureNotMatchException as e:
        log.error(e)
        await sm.emit("scan:done_ko", e.message)
        await sm.emit("scan:done_ko_s", e.message)
        return

    platform_list = [
        dbplatformh.get_platforms(s).fs_slug for s in platform_ids
    ] or fs_platforms

    if len(platform_list) == 0:
        log.warn(
            "⚠️ No platforms found, verify that the folder structure is right and the volume is mounted correctly "
        )
    else:
        log.info(f"Found {len(platform_list)} platforms in file system ")

    for platform_slug in platform_list:
        platform = dbplatformh.get_platform_by_slug(platform_slug)
        scanned_platform = scan_platform(platform_slug, fs_platforms)

        if platform:
            scanned_platform.id = platform.id

        platform = dbplatformh.add_platform(scanned_platform)

        await sm.emit(
            "scan:scanning_platform",
            PlatformSchema.model_validate(platform).model_dump(),
        )

        # Scanning roms
        try:
            fs_roms = fsromh.get_roms(platform)
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
            rom = dbromh.get_rom_by_filename(platform.id, fs_rom["file_name"])
            if (rom and rom.id not in selected_roms and not complete_rescan) and not (
                rescan_unidentified and rom and not rom.igdb_id
            ):
                continue

            scanned_rom = await scan_rom(platform, fs_rom)
            if rom:
                scanned_rom.id = rom.id

            scanned_rom.platform_id = platform.id
            _added_rom = dbromh.add_rom(scanned_rom)
            rom = dbromh.get_roms(_added_rom.id)

            await sm.emit(
                "scan:scanning_rom",
                {
                    "platform_name": platform.name,
                    "platform_slug": platform.slug,
                    **RomSchema.model_validate(rom).model_dump(),
                },
            )

            # Scanning saves
            fs_saves = fsasseth.get_assets(
                platform.fs_slug, rom.file_name_no_tags, Asset.SAVES
            )
            log.info(f"\t · {len(fs_saves)} saves found")
            for fs_emulator, fs_save_filename in fs_saves:
                scanned_save = scan_save(
                    platform=platform,
                    file_name=fs_save_filename,
                    emulator=fs_emulator,
                )

                save = dbsaveh.get_save_by_filename(rom.id, fs_save_filename)
                if save:
                    # Update file size if changed
                    if save.file_size_bytes != scanned_save.file_size_bytes:
                        dbsaveh.update_save(
                            save.id, {"file_size_bytes": scanned_save.file_size_bytes}
                        )
                    continue

                scanned_save.emulator = fs_emulator

                if rom:
                    scanned_save.rom_id = rom.id
                    dbsaveh.add_save(scanned_save)

            # Scanning states
            fs_states = fsasseth.get_assets(
                platform.fs_slug, rom.file_name_no_tags, Asset.STATES
            )
            log.info(f"\t · {len(fs_states)} states found")
            for fs_emulator, fs_state_filename in fs_states:
                scanned_state = scan_state(
                    platform=platform,
                    emulator=fs_emulator,
                    file_name=fs_state_filename,
                )

                state = dbstateh.get_state_by_filename(rom.id, fs_state_filename)
                if state:
                    # Update file size if changed
                    if state.file_size_bytes != scanned_state.file_size_bytes:
                        dbstateh.update_state(
                            state.id, {"file_size_bytes": scanned_state.file_size_bytes}
                        )

                    continue

                scanned_state.emulator = fs_emulator

                if rom:
                    scanned_state.rom_id = rom.id
                    dbstateh.add_state(scanned_state)

            # Scanning screenshots
            fs_screenshots = fsasseth.get_assets(
                platform.fs_slug, rom.file_name_no_tags, Asset.SCREENSHOTS
            )
            log.info(f"\t · {len(fs_screenshots)} screenshots found")
            for fs_screenshot_filename in fs_screenshots:
                scanned_screenshot = scan_screenshot(
                    file_name=fs_screenshot_filename, platform=platform
                )

                screenshot = dbscreenshotsh.get_screenshot_by_filename(
                    fs_screenshot_filename
                )
                if screenshot:
                    # Update file size if changed
                    if screenshot.file_size_bytes != scanned_screenshot.file_size_bytes:
                        dbscreenshotsh.update_screenshot(
                            screenshot.id,
                            {"file_size_bytes": scanned_screenshot.file_size_bytes},
                        )
                    continue

                if rom:
                    scanned_screenshot.rom_id = rom.id
                    dbscreenshotsh.add_screenshot(scanned_screenshot)

            dbsaveh.purge_saves(rom.id, [s for _e, s in fs_saves])
            dbstateh.purge_states(rom.id, [s for _e, s in fs_states])
            dbscreenshotsh.purge_screenshots(rom.id, fs_screenshots)
            dbromh.purge_roms(platform.id, [rom["file_name"] for rom in fs_roms])

    # Scanning screenshots outside platform folders
    fs_screenshots = fsasseth.get_screenshots()
    log.info("Screenshots")
    log.info(f" · {len(fs_screenshots)} screenshots found")
    for fs_platform, fs_screenshot_filename in fs_screenshots:
        scanned_screenshot = scan_screenshot(
            file_name=fs_screenshot_filename, fs_platform=fs_platform
        )

        screenshot = dbscreenshotsh.get_screenshot_by_filename(fs_screenshot_filename)
        if screenshot:
            # Update file size if changed
            if screenshot.file_size_bytes != scanned_screenshot.file_size_bytes:
                dbscreenshotsh.update_screenshot(
                    screenshot.id,
                    {"file_size_bytes": scanned_screenshot.file_size_bytes},
                )
            continue

        rom = dbromh.get_rom_by_filename_no_tags(scanned_screenshot.file_name_no_tags)
        if rom:
            scanned_screenshot.rom_id = rom.id
            dbscreenshotsh.add_screenshot(scanned_screenshot)

    # dbscreenshotsh.purge_screenshots([s for _e, s in fs_screenshots])
    dbplatformh.purge_platforms(fs_platforms)

    log.info(emoji.emojize(":check_mark:  Scan completed "))

    await sm.emit("scan:done", {})


@socketh.socket_server.on("scan")
async def scan_handler(_sid: str, options: dict):
    """Scan socket endpoint

    Args:
        options (dict): Socket options
    """

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fsresourceh.store_default_resources()

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
