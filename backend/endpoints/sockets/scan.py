import emoji
import socketio  # type: ignore
from config import ENABLE_EXPERIMENTAL_REDIS
from endpoints.platform import PlatformSchema
from endpoints.rom import RomSchema
from exceptions.fs_exceptions import FolderStructureNotMatchException, RomsNotFoundException
from handler import dbh, socketh, platformh, romh, resourceh, asseth
from handler.redis_handler import high_prio_queue, redis_url
from handler.scan_handler import (
    scan_platform,
    scan_rom,
    scan_save,
    scan_screenshot,
    scan_state,
)
from logger.logger import log


async def scan_platforms(
    platform_slugs: list[str],
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

    # Connect to external socketio server
    sm = (
        socketio.AsyncRedisManager(redis_url, write_only=True)
        if ENABLE_EXPERIMENTAL_REDIS
        else socketh.socket_server
    )

    # Scanning file system
    try:
        fs_platforms: list[str] = platformh.get_platforms()
    except FolderStructureNotMatchException as e:
        log.error(e)
        await sm.emit("scan:done_ko", e.message)
        return

    platform_list = [dbh.get_platform(s).fs_slug for s in platform_slugs]
    platform_list = platform_list or fs_platforms

    if len(platform_list) == 0:
        log.warn(
            "⚠️ No platforms found, verify that the folder structure is right and the volume is mounted correctly "
        )
    else:
        log.info(f"Found {len(platform_list)} platforms in file system ")

    for platform_slug in platform_list:
        scanned_platform = scan_platform(platform_slug, fs_platforms)
        _added_platform = dbh.add_platform(scanned_platform)
        platform = dbh.get_platform(_added_platform.id)

        await sm.emit(
            "scan:scanning_platform",
            PlatformSchema.model_validate(platform).model_dump(),
        )

        # Scanning roms
        try:
            fs_roms = romh.get_roms(platform.fs_slug)
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
            rom = dbh.get_rom_by_filename(platform.id, fs_rom["file_name"])
            if (rom and rom.id not in selected_roms and not complete_rescan) and not (
                rescan_unidentified and rom and not rom.igdb_id
            ):
                continue

            scanned_rom = await scan_rom(platform, fs_rom)
            if rom:
                scanned_rom.id = rom.id

            scanned_rom.platform_id = platform.id
            _added_rom = dbh.add_rom(scanned_rom)
            rom = dbh.get_rom(_added_rom.id)

            await sm.emit(
                "scan:scanning_rom",
                {
                    "p_name": platform.name,
                    **RomSchema.model_validate(rom).model_dump(),
                },
            )

        fs_assets = asseth.get_assets(platform.fs_slug)

        # Scanning saves
        log.info(f"\t · {len(fs_assets['saves'])} saves found")
        for fs_emulator, fs_save_filename in fs_assets["saves"]:
            scanned_save = scan_save(
                platform=platform,
                file_name=fs_save_filename,
                emulator=fs_emulator,
            )

            save = dbh.get_save_by_filename(platform.id, fs_save_filename)
            if save:
                # Update file size if changed
                if save.file_size_bytes != scanned_save.file_size_bytes:
                    dbh.update_save(
                        save.id, {"file_size_bytes": scanned_save.file_size_bytes}
                    )
                continue

            scanned_save.emulator = fs_emulator

            rom = dbh.get_rom_by_filename_no_tags(scanned_save.file_name_no_tags)
            if rom:
                scanned_save.rom_id = rom.id
                dbh.add_save(scanned_save)

        # Scanning states
        log.info(f"\t · {len(fs_assets['states'])} states found")
        for fs_emulator, fs_state_filename in fs_assets["states"]:
            scanned_state = scan_state(
                platform=platform,
                emulator=fs_emulator,
                file_name=fs_state_filename,
            )

            state = dbh.get_state_by_filename(platform.id, fs_state_filename)
            if state:
                # Update file size if changed
                if state.file_size_bytes != scanned_state.file_size_bytes:
                    dbh.update_state(
                        state.id, {"file_size_bytes": scanned_state.file_size_bytes}
                    )

                continue

            scanned_state.emulator = fs_emulator
            # scanned_state.platform_slug = scanned_platform.slug TODO: remove

            rom = dbh.get_rom_by_filename_no_tags(scanned_state.file_name_no_tags)
            if rom:
                scanned_state.rom_id = rom.id
                dbh.add_state(scanned_state)

        # Scanning screenshots
        log.info(f"\t · {len(fs_assets['screenshots'])} screenshots found")
        for fs_screenshot_filename in fs_assets["screenshots"]:
            scanned_screenshot = scan_screenshot(
                file_name=fs_screenshot_filename, platform=platform
            )

            screenshot = dbh.get_screenshot_by_filename(fs_screenshot_filename)
            if screenshot:
                # Update file size if changed
                if screenshot.file_size_bytes != scanned_screenshot.file_size_bytes:
                    dbh.update_screenshot(
                        screenshot.id,
                        {"file_size_bytes": scanned_screenshot.file_size_bytes},
                    )
                continue

            # scanned_screenshot.platform_slug = scanned_patform.slug TODO: remove

            rom = dbh.get_rom_by_filename_no_tags(scanned_screenshot.file_name_no_tags)
            if rom:
                scanned_screenshot.rom_id = rom.id
                dbh.add_screenshot(scanned_screenshot)

        dbh.purge_saves(platform.id, [s for _e, s in fs_assets["saves"]])
        dbh.purge_states(platform.id, [s for _e, s in fs_assets["states"]])
        dbh.purge_screenshots(platform.id, fs_assets["screenshots"])
        dbh.purge_roms(platform.id, [rom["file_name"] for rom in fs_roms])

    # Scanning screenshots outside platform folders
    fs_screenshots = asseth.get_screenshots()
    log.info("Screenshots")
    log.info(f" · {len(fs_screenshots)} screenshots found")
    for fs_platform, fs_screenshot_filename in fs_screenshots:
        scanned_screenshot = scan_screenshot(
            file_name=fs_screenshot_filename, fs_platform=fs_platform
        )

        screenshot = dbh.get_screenshot_by_filename(fs_screenshot_filename)
        if screenshot:
            # Update file size if changed
            if screenshot.file_size_bytes != scanned_screenshot.file_size_bytes:
                dbh.update_screenshot(
                    screenshot.id,
                    {"file_size_bytes": scanned_screenshot.file_size_bytes},
                )
            continue

        rom = dbh.get_rom_by_filename_no_tags(scanned_screenshot.file_name_no_tags)
        if rom:
            scanned_screenshot.rom_id = rom.id
            # scanned_screenshot.platform_slug = rom.platform_slug TODO: remove
            dbh.add_screenshot(scanned_screenshot)

    dbh.purge_screenshots([s for _e, s in fs_screenshots])
    dbh.purge_platforms(fs_platforms)

    log.info(emoji.emojize(":check_mark:  Scan completed "))

    await sm.emit("scan:done", {})


@socketh.socket_server.on("scan")
async def scan_handler(_sid: str, options: dict):
    """Scan socket endpoint

    Args:
        options (dict): Socket options
    """

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    resourceh.store_default_resources()

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
