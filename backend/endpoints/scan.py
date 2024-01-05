import emoji
import socketio  # type: ignore

from logger.logger import log
from exceptions.fs_exceptions import PlatformsNotFoundException, RomsNotFoundException
from handler import dbh
from utils.fastapi import (
    scan_platform,
    scan_rom,
    scan_save,
    scan_state,
    scan_bios,
    scan_screenshot,
)
from utils.socket import socket_server
from utils.fs import (
    get_platforms,
    get_roms,
    store_default_resources,
    get_assets,
    get_screenshots,
)
from utils.redis import high_prio_queue, redis_url
from endpoints.platform import PlatformSchema
from endpoints.rom import RomSchema
from config import ENABLE_EXPERIMENTAL_REDIS


async def scan_platforms(
    platform_slugs: list[str],
    complete_rescan: bool = False,
    rescan_unidentified: bool = False,
    selected_roms: list[str] = (),
):
    # Connect to external socketio server
    sm = (
        socketio.AsyncRedisManager(redis_url, write_only=True)
        if ENABLE_EXPERIMENTAL_REDIS
        else socket_server
    )

    # Scanning file system
    try:
        fs_platforms: list[str] = get_platforms()
    except PlatformsNotFoundException as e:
        log.error(e)
        await sm.emit("scan:done_ko", e.message)
        return

    platform_list = [dbh.get_platform(s).fs_slug for s in platform_slugs]
    platform_list = platform_list or fs_platforms

    if (len(platform_list) == 0):
        log.warn("⚠️ No platforms found, verify that the folder structure is right and the volume is mounted correctly ")
    else:
        log.info(f"Found {len(platform_list)} platforms in file system ")

    for platform_slug in platform_list:
        scanned_platform = scan_platform(platform_slug, fs_platforms)
        _new_platform = dbh.add_platform(scanned_platform)
        new_platform = dbh.get_platform(_new_platform.slug)

        await sm.emit(
            "scan:scanning_platform",
            PlatformSchema.model_validate(new_platform).model_dump(),
        )

        dbh.add_platform(scanned_platform)

        # Scanning roms
        try:
            fs_roms = get_roms(scanned_platform.fs_slug)
        except RomsNotFoundException as e:
            log.error(e)
            continue

        if (len(fs_roms) == 0):
            log.warning("  ⚠️ No roms found, verify that the folder structure is correct")
        else:
            log.warn(f"  {len(fs_roms)} roms found")

        for fs_rom in fs_roms:
            rom = dbh.get_rom_by_filename(scanned_platform.slug, fs_rom["file_name"])
            if (rom and rom.id not in selected_roms and not complete_rescan) and not (rescan_unidentified and rom and not rom.igdb_id):
                continue

            scanned_rom = await scan_rom(scanned_platform, fs_rom)
            if rom:
                scanned_rom.id = rom.id

            _new_rom = dbh.add_rom(scanned_rom)
            new_rom = dbh.get_rom(_new_rom.id)

            await sm.emit(
                "scan:scanning_rom",
                {
                    "p_name": scanned_platform.name,
                    **RomSchema.model_validate(new_rom).model_dump(),
                },
            )

        fs_assets = get_assets(scanned_platform.fs_slug)

        # Scanning saves
        log.info("\t · Saves")
        for fs_emulator, fs_save_filename in fs_assets["saves"]:
            scanned_save = scan_save(
                platform=scanned_platform,
                emulator=fs_emulator,
                file_name=fs_save_filename,
            )

            save = dbh.get_save_by_filename(scanned_platform.slug, fs_save_filename)
            if save:
                dbh.update_save(
                    save.id, {"file_size_bytes": scanned_save.file_size_bytes}
                )
                continue

            scanned_save.emulator = fs_emulator
            scanned_save.platform_slug = scanned_platform.slug

            rom = dbh.get_rom_by_filename_no_tags(scanned_save.file_name_no_tags)
            if rom:
                scanned_save.rom_id = rom.id
                dbh.add_save(scanned_save)

        # Scanning states
        log.info("\t · States")
        for fs_emulator, fs_state_filename in fs_assets["states"]:
            scanned_state = scan_state(
                platform=scanned_platform,
                emulator=fs_emulator,
                file_name=fs_state_filename,
            )

            state = dbh.get_state_by_filename(scanned_platform.slug, fs_state_filename)
            if state:
                dbh.update_state(
                    state.id, {"file_size_bytes": scanned_state.file_size_bytes}
                )
                continue

            scanned_state.emulator = fs_emulator
            scanned_state.platform_slug = scanned_platform.slug

            rom = dbh.get_rom_by_filename_no_tags(scanned_state.file_name_no_tags)
            if rom:
                scanned_state.rom_id = rom.id
                dbh.add_state(scanned_state)

        # Scanning bios
        log.info("\t · Firmware")
        for fs_bios_filename in fs_assets["bios"]:
            scanned_bios = scan_bios(
                platform=scanned_platform, file_name=fs_bios_filename
            )

            bios = dbh.get_bios_by_filename(scanned_platform.slug, fs_bios_filename)
            if bios:
                dbh.update_bios(
                    bios.id, {"file_size_bytes": scanned_bios.file_size_bytes}
                )
                continue

            scanned_bios.platform_slug = scanned_platform.slug
            dbh.add_bios(scanned_bios)

        # Scanning emulators
        log.info("\t · Emulators")
        for fs_emulator_filename in fs_assets["emulators"]:
            scanned_emulator = scan_bios(
                platform=scanned_platform, file_name=fs_emulator_filename
            )

            emulator = dbh.get_emulator_by_filename(
                scanned_platform.slug, fs_emulator_filename
            )
            if emulator:
                dbh.update_emulator(
                    emulator.id, {"file_size_bytes": scanned_emulator.file_size_bytes}
                )
                continue

            scanned_emulator.platform_slug = scanned_platform.slug
            dbh.add_emulator(scanned_emulator)

        dbh.purge_saves(scanned_platform.slug, [s for e, s in fs_assets["saves"]])
        dbh.purge_states(scanned_platform.slug, [s for e, s in fs_assets["states"]])
        dbh.purge_bios(scanned_platform.slug, fs_assets["bios"])
        dbh.purge_emulators(scanned_platform.slug, fs_assets["emulators"])
        dbh.purge_roms(scanned_platform.slug, [rom["file_name"] for rom in fs_roms])

    # Scanning screenshots
    log.info("\t · Screenshots")
    fs_screenshots = get_screenshots()
    for fs_screenshot_filename in fs_screenshots:
        scanned_screenshot = scan_screenshot(fs_screenshot_filename)

        screenshot = dbh.get_screenshot_by_filename(fs_screenshot_filename)
        if screenshot:
            dbh.update_screenshot(
                screenshot.id, {"file_size_bytes": scanned_screenshot.file_size_bytes}
            )
            continue

        rom = dbh.get_rom_by_filename_no_tags(scanned_screenshot.file_name_no_tags)
        if rom:
            scanned_screenshot.rom_id = rom.id
            dbh.add_screenshot(scanned_screenshot)

    dbh.purge_platforms(fs_platforms)
    dbh.purge_screenshots(fs_screenshots)

    log.info(emoji.emojize(":check_mark:  Scan completed "))

    await sm.emit("scan:done", {})


@socket_server.on("scan")
async def scan_handler(_sid: str, options: dict):
    """Scan platforms and roms and write them in database."""

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    store_default_resources()

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
        await scan_platforms(platform_slugs, complete_rescan, rescan_unidentified, selected_roms)
