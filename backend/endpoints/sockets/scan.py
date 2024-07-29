from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import emoji
import socketio  # type: ignore
from config import SCAN_TIMEOUT
from endpoints.responses.platform import PlatformSchema
from endpoints.responses.rom import RomSchema
from exceptions.fs_exceptions import (
    FirmwareNotFoundException,
    FolderStructureNotMatchException,
    RomsNotFoundException,
)
from exceptions.socket_exceptions import ScanStoppedException
from handler.database import db_firmware_handler, db_platform_handler, db_rom_handler
from handler.filesystem import (
    fs_firmware_handler,
    fs_platform_handler,
    fs_resource_handler,
    fs_rom_handler,
)
from handler.metadata.igdb_handler import IGDB_API_ENABLED
from handler.metadata.moby_handler import MOBY_API_ENABLED
from handler.redis_handler import high_prio_queue, redis_client, redis_url
from handler.scan_handler import ScanType, scan_firmware, scan_platform, scan_rom
from handler.socket_handler import socket_handler
from logger.logger import log
from models.platform import Platform
from models.rom import Rom
from rq import Worker
from rq.job import Job
from sqlalchemy.inspection import inspect
from utils.context import initialize_context

STOP_SCAN_FLAG: Final = "scan:stop"


@dataclass
class ScanStats:
    scanned_platforms: int = 0
    added_platforms: int = 0
    metadata_platforms: int = 0
    scanned_roms: int = 0
    added_roms: int = 0
    metadata_roms: int = 0
    scanned_firmware: int = 0
    added_firmware: int = 0

    def __add__(self, other: Any) -> ScanStats:
        if not isinstance(other, ScanStats):
            return NotImplemented
        return ScanStats(
            scanned_platforms=self.scanned_platforms + other.scanned_platforms,
            added_platforms=self.added_platforms + other.added_platforms,
            metadata_platforms=self.metadata_platforms + other.metadata_platforms,
            scanned_roms=self.scanned_roms + other.scanned_roms,
            added_roms=self.added_roms + other.added_roms,
            metadata_roms=self.metadata_roms + other.metadata_roms,
            scanned_firmware=self.scanned_firmware + other.scanned_firmware,
            added_firmware=self.added_firmware + other.added_firmware,
        )


def _get_socket_manager():
    """Connect to external socketio server"""
    return socketio.AsyncRedisManager(redis_url, write_only=True)


def _should_scan_rom(scan_type: ScanType, rom: Rom, roms_ids: list):
    """Decide if a rom should be scanned or not

    Args:
        scan_type (str): Type of scan to be performed.
        roms_ids (list[str], optional): List of selected roms to be scanned.
        metadata_sources (list[str], optional): List of metadata sources to be used
    """

    # This logic is tricky so only touch it if you know what you're doing"""
    return (
        (scan_type in {ScanType.NEW_PLATFORMS, ScanType.QUICK} and not rom)
        or (scan_type == ScanType.COMPLETE)
        or (
            rom
            and (
                (
                    scan_type == ScanType.UNIDENTIFIED
                    and not (rom.igdb_id or rom.moby_id)
                )
                or (
                    scan_type == ScanType.PARTIAL
                    and (not rom.igdb_id or not rom.moby_id)
                )
                or (rom.id in roms_ids)
            )
        )
    )


@initialize_context()
async def scan_platforms(
    platform_ids: list[int],
    scan_type: ScanType = ScanType.QUICK,
    roms_ids: list[str] | None = None,
    metadata_sources: list[str] | None = None,
):
    """Scan all the listed platforms and fetch metadata from different sources

    Args:
        platform_slugs (list[str]): List of platform slugs to be scanned
        scan_type (str): Type of scan to be performed. Defaults to "quick".
        roms_ids (list[str], optional): List of selected roms to be scanned. Defaults to [].
        metadata_sources (list[str], optional): List of metadata sources to be used. Defaults to all sources.
    """

    if not roms_ids:
        roms_ids = []

    if not metadata_sources:
        metadata_sources = ["igdb", "moby"]

    sm = _get_socket_manager()

    if not IGDB_API_ENABLED and not MOBY_API_ENABLED:
        log.error("Search error: No metadata providers enabled")
        await sm.emit("scan:done_ko", "No metadata providers enabled")
        return

    try:
        fs_platforms: list[str] = fs_platform_handler.get_platforms()
    except FolderStructureNotMatchException as e:
        log.error(e)
        await sm.emit("scan:done_ko", e.message)
        return

    scan_stats = ScanStats()

    async def stop_scan():
        log.info(emoji.emojize(":stop_sign: Scan stopped manually"))
        await sm.emit("scan:done", scan_stats.__dict__)
        redis_client.delete(STOP_SCAN_FLAG)

    try:
        platform_list = [
            db_platform_handler.get_platform(s).fs_slug for s in platform_ids
        ] or fs_platforms

        if len(platform_list) == 0:
            log.warn(
                "⚠️ No platforms found, verify that the folder structure is right and the volume is mounted correctly "
            )
        else:
            log.info(f"Found {len(platform_list)} platforms in file system ")

        for platform_slug in platform_list:
            scan_stats += await _identify_platform(
                platform_slug=platform_slug,
                scan_type=scan_type,
                fs_platforms=fs_platforms,
                roms_ids=roms_ids,
                metadata_sources=metadata_sources,
                socket_manager=sm,
            )

        # Same protection for platforms
        if len(fs_platforms) > 0:
            db_platform_handler.purge_platforms(fs_platforms)

        log.info(emoji.emojize(":check_mark: Scan completed "))
        await sm.emit("scan:done", scan_stats.__dict__)
    except ScanStoppedException:
        await stop_scan()
        return
    except Exception as e:
        log.error(e)
        # Catch all exceptions and emit error to the client
        await sm.emit("scan:done_ko", str(e))
        return


async def _identify_platform(
    platform_slug: str,
    scan_type: ScanType,
    fs_platforms: list[str],
    roms_ids: list[str],
    metadata_sources: list[str],
    socket_manager: socketio.AsyncRedisManager,
) -> ScanStats:
    # Stop the scan if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        raise ScanStoppedException()

    scan_stats = ScanStats()

    platform = db_platform_handler.get_platform_by_fs_slug(platform_slug)
    if platform and scan_type == ScanType.NEW_PLATFORMS:
        return scan_stats

    scanned_platform = await scan_platform(
        platform_slug, fs_platforms, metadata_sources=metadata_sources
    )
    if platform:
        scanned_platform.id = platform.id
        # Keep the existing ids if they exist on the platform
        scanned_platform.igdb_id = scanned_platform.igdb_id or platform.igdb_id
        scanned_platform.moby_id = scanned_platform.moby_id or platform.moby_id

    scan_stats.scanned_platforms += 1
    scan_stats.added_platforms += 1 if not platform else 0
    scan_stats.metadata_platforms += (
        1 if scanned_platform.igdb_id or scanned_platform.moby_id else 0
    )

    platform = db_platform_handler.add_platform(scanned_platform)

    await socket_manager.emit(
        "scan:scanning_platform",
        PlatformSchema.model_validate(platform).model_dump(
            include={"id", "name", "slug"}
        ),
    )
    await socket_manager.emit("", None)

    # Scanning firmware
    try:
        fs_firmware = fs_firmware_handler.get_firmware(platform)
    except FirmwareNotFoundException:
        fs_firmware = []

    if len(fs_firmware) == 0:
        log.warning("  ⚠️ No firmware found, skipping firmware scan for this platform")
    else:
        log.info(f"  {len(fs_firmware)} firmware files found")

    for fs_fw in fs_firmware:
        scan_stats += await _identify_firmware(
            platform=platform,
            fs_fw=fs_fw,
        )

    # Scanning roms
    try:
        fs_roms = fs_rom_handler.get_roms(platform)
    except RomsNotFoundException as e:
        log.error(e)
        return scan_stats

    if len(fs_roms) == 0:
        log.warning("  ⚠️ No roms found, verify that the folder structure is correct")
    else:
        log.info(f"  {len(fs_roms)} roms found")

    for fs_rom in fs_roms:
        scan_stats += await _identify_rom(
            platform=platform,
            fs_rom=fs_rom,
            scan_type=scan_type,
            roms_ids=roms_ids,
            metadata_sources=metadata_sources,
            socket_manager=socket_manager,
        )

    # Only purge entries if there are some file remaining in the library
    # This protects against accidental deletion of entries when
    # the folder structure is not correct or the drive is not mounted

    if len(fs_roms) > 0:
        db_rom_handler.purge_roms(platform.id, [rom["file_name"] for rom in fs_roms])

    # Same protection for firmware
    if len(fs_firmware) > 0:
        db_firmware_handler.purge_firmware(platform.id, [fw for fw in fs_firmware])

    return scan_stats


async def _identify_firmware(
    platform: Platform,
    fs_fw: str,
) -> ScanStats:
    scan_stats = ScanStats()

    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return scan_stats

    firmware = db_firmware_handler.get_firmware_by_filename(platform.id, fs_fw)

    scanned_firmware = scan_firmware(
        platform=platform,
        file_name=fs_fw,
        firmware=firmware,
    )

    scan_stats.scanned_firmware += 1
    scan_stats.added_firmware += 1 if not firmware else 0

    db_firmware_handler.add_firmware(scanned_firmware)
    return scan_stats


async def _identify_rom(
    platform: Platform,
    fs_rom: dict,
    scan_type: ScanType,
    roms_ids: list[str],
    metadata_sources: list[str],
    socket_manager: socketio.AsyncRedisManager,
) -> ScanStats:
    scan_stats = ScanStats()

    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return scan_stats

    rom = db_rom_handler.get_rom_by_filename(platform.id, fs_rom["file_name"])

    if not _should_scan_rom(scan_type=scan_type, rom=rom, roms_ids=roms_ids):
        return scan_stats

    scanned_rom = await scan_rom(
        platform=platform,
        rom_attrs=fs_rom,
        scan_type=scan_type,
        rom=rom,
        metadata_sources=metadata_sources,
    )

    scan_stats.scanned_roms += 1
    scan_stats.added_roms += 1 if not rom else 0
    scan_stats.metadata_roms += 1 if scanned_rom.igdb_id or scanned_rom.moby_id else 0

    _added_rom = db_rom_handler.add_rom(scanned_rom)

    path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
        overwrite=True,
        entity=_added_rom,
        url_cover=_added_rom.url_cover,
    )

    path_screenshots = await fs_resource_handler.get_rom_screenshots(
        rom=_added_rom,
        url_screenshots=_added_rom.url_screenshots,
    )

    _added_rom.path_cover_s = path_cover_s
    _added_rom.path_cover_l = path_cover_l
    _added_rom.path_screenshots = path_screenshots
    # Update the scanned rom with the cover and screenshots paths and update database
    db_rom_handler.update_rom(
        _added_rom.id,
        {
            c: getattr(_added_rom, c)
            for c in inspect(_added_rom).mapper.column_attrs.keys()
        },
    )

    await socket_manager.emit(
        "scan:scanning_rom",
        {
            "platform_name": platform.name,
            "platform_slug": platform.slug,
            **RomSchema.model_validate(_added_rom).model_dump(
                exclude={"created_at", "updated_at", "rom_user"}
            ),
        },
    )
    await socket_manager.emit("", None)

    return scan_stats


@socket_handler.socket_server.on("scan")
async def scan_handler(_sid: str, options: dict):
    """Scan socket endpoint

    Args:
        options (dict): Socket options
    """

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))

    platform_ids = options.get("platforms", [])
    scan_type = ScanType[options.get("type", "quick").upper()]
    roms_ids = options.get("roms_ids", [])
    metadata_sources = options.get("apis", [])

    return high_prio_queue.enqueue(
        scan_platforms,
        platform_ids,
        scan_type,
        roms_ids,
        metadata_sources,
        job_timeout=SCAN_TIMEOUT,  # Timeout (default of 4 hours)
    )


@socket_handler.socket_server.on("scan:stop")
async def stop_scan_handler(_sid: str):
    """Stop scan socket endpoint"""

    log.info(emoji.emojize(":stop_button: Stop scan requested..."))

    async def cancel_job(job: Job):
        job.cancel()
        redis_client.set(STOP_SCAN_FLAG, 1)
        log.info(emoji.emojize(":stop_button: Job found, stopping scan..."))

    existing_jobs = high_prio_queue.get_jobs()
    for job in existing_jobs:
        if job.func_name == "scan_platform" and job.is_started:
            return await cancel_job(job)

    workers = Worker.all(connection=redis_client)
    for worker in workers:
        current_job = worker.get_current_job()
        if (
            current_job
            and current_job.func_name == "endpoints.sockets.scan.scan_platforms"
            and current_job.is_started
        ):
            return await cancel_job(current_job)

    log.info(emoji.emojize(":stop_button: No running scan to stop"))
