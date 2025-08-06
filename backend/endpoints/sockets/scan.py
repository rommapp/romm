from __future__ import annotations

from dataclasses import dataclass
from itertools import batched
from typing import Any, Final

import emoji
import socketio  # type: ignore
from config import DEV_MODE, REDIS_URL, SCAN_TIMEOUT
from endpoints.responses.platform import PlatformSchema
from endpoints.responses.rom import SimpleRomSchema
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
from handler.filesystem.roms_handler import FSRom
from handler.redis_handler import high_prio_queue, redis_client
from handler.scan_handler import (
    ScanType,
    scan_firmware,
    scan_platform,
    scan_rom,
)
from handler.socket_handler import socket_handler
from logger.formatter import BLUE, LIGHTYELLOW
from logger.formatter import highlight as hl
from logger.logger import log
from models.platform import Platform
from models.rom import Rom, RomFile
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
            raise NotImplementedError(
                f"Addition not implemented between ScanStats and {type(other)}"
            )

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


def _get_socket_manager() -> socketio.AsyncRedisManager:
    """Connect to external socketio server"""
    return socketio.AsyncRedisManager(str(REDIS_URL), write_only=True)


async def _identify_firmware(
    platform: Platform,
    fs_fw: str,
) -> ScanStats:
    scan_stats = ScanStats()

    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return scan_stats

    firmware = db_firmware_handler.get_firmware_by_filename(platform.id, fs_fw)

    scanned_firmware = await scan_firmware(
        platform=platform,
        file_name=fs_fw,
        firmware=firmware,
    )

    scan_stats.scanned_firmware += 1
    scan_stats.added_firmware += 1 if not firmware else 0

    scanned_firmware.missing_from_fs = False
    db_firmware_handler.add_firmware(scanned_firmware)
    return scan_stats


def _should_scan_rom(scan_type: ScanType, rom: Rom | None, roms_ids: list[int]) -> bool:
    """Decide if a rom should be scanned or not

    Args:
        scan_type (str): Type of scan to be performed.
        roms_ids (list[int], optional): List of selected roms to be scanned.
        metadata_sources (list[str], optional): List of metadata sources to be used
    """

    # This logic is tricky so only touch it if you know what you're doing"""
    return bool(
        (scan_type in {ScanType.NEW_PLATFORMS, ScanType.QUICK} and not rom)
        or (scan_type == ScanType.COMPLETE)
        or (scan_type == ScanType.HASHES)
        or (
            rom
            and (
                (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
                or (scan_type == ScanType.PARTIAL and rom.is_identified)
                or (rom.id in roms_ids)
            )
        )
    )


# There's an order of operations here that is important:
# 1. Read the list of roms from the filesystem
# 2. Check if ROM should be scanned based on the scan type
# 3. Create a new ROM entry if it doesn't exist
# 4. Build the ROM files and calculate the hashes
# 4. Scan the ROM and update its metadata
async def _identify_rom(
    platform: Platform,
    fs_rom: FSRom,
    rom: Rom | None,
    scan_type: ScanType,
    roms_ids: list[int],
    metadata_sources: list[str],
    socket_manager: socketio.AsyncRedisManager,
) -> ScanStats:
    scan_stats = ScanStats()

    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return scan_stats

    if not _should_scan_rom(scan_type=scan_type, rom=rom, roms_ids=roms_ids):
        if rom:
            if rom.fs_name != fs_rom["fs_name"]:
                # Just to update the filesystem data
                rom.fs_name = fs_rom["fs_name"]
                db_rom_handler.add_rom(rom)

            if rom.missing_from_fs:
                db_rom_handler.update_rom(rom.id, {"missing_from_fs": False})

        return scan_stats

    # Update properties that don't require metadata
    fs_regions, fs_revisions, fs_languages, fs_other_tags = fs_rom_handler.parse_tags(
        fs_rom["fs_name"]
    )
    roms_path = fs_rom_handler.get_roms_fs_structure(platform.fs_slug)

    # Create the entry early so we have the ID
    newly_added: bool = rom is None
    if not rom:
        rom = db_rom_handler.add_rom(
            Rom(
                fs_name=fs_rom["fs_name"],
                fs_path=roms_path,
                fs_name_no_tags=fs_rom_handler.get_file_name_with_no_tags(
                    fs_rom["fs_name"]
                ),
                fs_name_no_ext=fs_rom_handler.get_file_name_with_no_extension(
                    fs_rom["fs_name"]
                ),
                fs_extension=fs_rom_handler.parse_file_extension(fs_rom["fs_name"]),
                regions=fs_regions,
                revision=fs_revisions,
                languages=fs_languages,
                tags=fs_other_tags,
                platform_id=platform.id,
                name=fs_rom["fs_name"],
                multi=fs_rom["multi"],
                url_cover="",
                url_manual="",
                url_screenshots=[],
            )
        )

    # Silly checks to make the type checker happy
    if not rom:
        return scan_stats

    # Build rom files object before scanning
    rom_files, rom_crc_c, rom_md5_h, rom_sha1_h, rom_ra_h = (
        await fs_rom_handler.get_rom_files(rom)
    )
    fs_rom.update(
        {
            "files": rom_files,
            "crc_hash": rom_crc_c,
            "md5_hash": rom_md5_h,
            "sha1_hash": rom_sha1_h,
            "ra_hash": rom_ra_h,
        }
    )

    scanned_rom = await scan_rom(
        scan_type=scan_type,
        platform=platform,
        rom=rom,
        fs_rom=fs_rom,
        metadata_sources=metadata_sources,
        newly_added=newly_added,
    )

    scan_stats.scanned_roms += 1
    scan_stats.added_roms += 1 if not rom else 0
    scan_stats.metadata_roms += 1 if scanned_rom.is_identified else 0

    _added_rom = db_rom_handler.add_rom(scanned_rom)

    # Delete the existing rom files in the DB
    db_rom_handler.purge_rom_files(_added_rom.id)

    # Create each file entry for the rom
    new_rom_files = [
        RomFile(
            rom_id=_added_rom.id,
            file_name=file.file_name,
            file_path=file.file_path,
            file_size_bytes=file.file_size_bytes,
            last_modified=file.last_modified,
            category=file.category,
            crc_hash=file.crc_hash,
            md5_hash=file.md5_hash,
            sha1_hash=file.sha1_hash,
            ra_hash=file.ra_hash,
        )
        for file in rom_files
    ]
    for new_rom_file in new_rom_files:
        db_rom_handler.add_rom_file(new_rom_file)

    if _added_rom.ra_metadata:
        await fs_resource_handler.create_ra_resources_path(platform.id, _added_rom.id)

        # Store the achievements badges
        for ach in _added_rom.ra_metadata.get("achievements", []):
            # Store both normal and locked version
            badge_url_lock = ach.get("badge_url_lock", None)
            badge_path_lock = ach.get("badge_path_lock", None)
            if badge_url_lock and badge_path_lock:
                await fs_resource_handler.store_ra_badge(
                    badge_url_lock, badge_path_lock
                )
            badge_url = ach.get("badge_url", None)
            badge_path = ach.get("badge_path", None)
            if badge_url and badge_path:
                await fs_resource_handler.store_ra_badge(badge_url, badge_path)

    path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
        entity=_added_rom,
        overwrite=True,
        url_cover=_added_rom.url_cover,
    )

    path_manual = await fs_resource_handler.get_manual(
        rom=_added_rom,
        overwrite=True,
        url_manual=_added_rom.url_manual,
    )

    path_screenshots = await fs_resource_handler.get_rom_screenshots(
        rom=_added_rom,
        url_screenshots=_added_rom.url_screenshots,
    )

    _added_rom.path_cover_s = path_cover_s
    _added_rom.path_cover_l = path_cover_l
    _added_rom.path_screenshots = path_screenshots
    _added_rom.path_manual = path_manual
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
            "platform_fs_slug": platform.fs_slug,
            **SimpleRomSchema.from_orm_with_factory(_added_rom).model_dump(
                exclude={"created_at", "updated_at", "rom_user"}
            ),
        },
    )
    await socket_manager.emit("", None)

    return scan_stats


async def _identify_platform(
    platform_slug: str,
    scan_type: ScanType,
    fs_platforms: list[str],
    roms_ids: list[int],
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

    scanned_platform = await scan_platform(platform_slug, fs_platforms)
    if platform:
        scanned_platform.id = platform.id
        # Keep the existing ids if they exist on the platform
        scanned_platform.igdb_id = scanned_platform.igdb_id or platform.igdb_id
        scanned_platform.moby_id = scanned_platform.moby_id or platform.moby_id
        scanned_platform.launchbox_id = (
            scanned_platform.launchbox_id or platform.launchbox_id
        )

    scan_stats.scanned_platforms += 1
    scan_stats.added_platforms += 1 if not platform else 0
    scan_stats.metadata_platforms += 1 if scanned_platform.is_identified else 0

    platform = db_platform_handler.add_platform(scanned_platform)

    await socket_manager.emit(
        "scan:scanning_platform",
        PlatformSchema.model_validate(platform).model_dump(
            include={"id", "name", "slug", "fs_slug"}
        ),
    )
    await socket_manager.emit("", None)

    # Scanning firmware
    try:
        fs_firmware = await fs_firmware_handler.get_firmware(platform.fs_slug)
    except FirmwareNotFoundException:
        fs_firmware = []

    if len(fs_firmware) == 0:
        log.warning(
            emoji.emojize(
                f"{hl(':warning:', color=LIGHTYELLOW)}  No firmware found for {hl(platform.custom_name or platform.name, color=BLUE)}[{hl(platform.fs_slug)}]"
            )
        )
    else:
        log.info(f"{hl(str(len(fs_firmware)))} firmware files found")

    for fs_fw in fs_firmware:
        scan_stats += await _identify_firmware(
            platform=platform,
            fs_fw=fs_fw,
        )

    # Scanning roms
    try:
        fs_roms = await fs_rom_handler.get_roms(platform)
    except RomsNotFoundException as e:
        log.error(e)
        return scan_stats

    if len(fs_roms) == 0:
        log.warning(
            emoji.emojize(
                f"{hl(':warning:', color=LIGHTYELLOW)}  No roms found, verify that the folder structure is correct"
            )
        )
    else:
        log.info(f"{hl(str(len(fs_roms)))} roms found in the file system")

    for fs_roms_batch in batched(fs_roms, 200, strict=False):
        rom_by_filename_map = db_rom_handler.get_roms_by_fs_name(
            platform_id=platform.id,
            fs_names={fs_rom["fs_name"] for fs_rom in fs_roms_batch},
        )

        for fs_rom in fs_roms_batch:
            scan_stats += await _identify_rom(
                platform=platform,
                fs_rom=fs_rom,
                rom=rom_by_filename_map.get(fs_rom["fs_name"]),
                scan_type=scan_type,
                roms_ids=roms_ids,
                metadata_sources=metadata_sources,
                socket_manager=socket_manager,
            )

    missing_roms = db_rom_handler.mark_missing_roms(
        platform.id, [rom["fs_name"] for rom in fs_roms]
    )
    if len(missing_roms) > 0:
        log.warning(f"{hl('Missing')} roms from filesystem:")
        for r in missing_roms:
            log.warning(f" - {r.fs_name}")

    missing_firmware = db_firmware_handler.mark_missing_firmware(
        platform.id, [fw for fw in fs_firmware]
    )
    if len(missing_firmware) > 0:
        log.warning(f"{hl('Missing')} firmware from filesystem:")
        for f in missing_firmware:
            log.warning(f" - {f}")

    return scan_stats


@initialize_context()
async def scan_platforms(
    platform_ids: list[int],
    scan_type: ScanType = ScanType.QUICK,
    roms_ids: list[int] | None = None,
    metadata_sources: list[str] | None = None,
):
    """Scan all the listed platforms and fetch metadata from different sources

    Args:
        platform_slugs (list[str]): List of platform slugs to be scanned
        scan_type (str): Type of scan to be performed. Defaults to "quick".
        roms_ids (list[int], optional): List of selected roms to be scanned. Defaults to [].
        metadata_sources (list[str], optional): List of metadata sources to be used. Defaults to all sources.
    """

    if not roms_ids:
        roms_ids = []

    sm = _get_socket_manager()

    if not metadata_sources:
        log.error("No metadata sources provided")
        await sm.emit("scan:done_ko", "No metadata sources provided")
        return None

    try:
        fs_platforms: list[str] = await fs_platform_handler.get_platforms()
    except FolderStructureNotMatchException as e:
        log.error(e)
        await sm.emit("scan:done_ko", e.message)
        return None

    scan_stats = ScanStats()

    async def stop_scan():
        log.info(emoji.emojize(":stop_sign: Scan stopped manually"))
        await sm.emit("scan:done", scan_stats.__dict__)
        redis_client.delete(STOP_SCAN_FLAG)

    try:
        platform_list = [
            platform.fs_slug
            for s in platform_ids
            if (platform := db_platform_handler.get_platform(s)) is not None
        ] or fs_platforms
        platform_list = sorted(platform_list)

        if len(platform_list) == 0:
            log.warning(
                emoji.emojize(
                    f"{hl(':warning:', color=LIGHTYELLOW)}  No platforms found, verify that the folder structure is right and the volume is mounted correctly. \
                Check https://github.com/rommapp/romm?tab=readme-ov-file#folder-structure for more details."
                )
            )
        else:
            log.info(
                f"Found {hl(str(len(platform_list)))} platforms in the file system"
            )

        for platform_slug in platform_list:
            scan_stats += await _identify_platform(
                platform_slug=platform_slug,
                scan_type=scan_type,
                fs_platforms=fs_platforms,
                roms_ids=roms_ids,
                metadata_sources=metadata_sources,
                socket_manager=sm,
            )

        missed_platforms = db_platform_handler.mark_missing_platforms(fs_platforms)
        if len(missed_platforms) > 0:
            log.warning(f"{hl('Missing')} platforms from filesystem:")
            for p in missed_platforms:
                log.warning(f" - {p.slug}")

        log.info(emoji.emojize(":check_mark:  Scan completed "))
        await sm.emit("scan:done", scan_stats.__dict__)
    except ScanStoppedException:
        await stop_scan()
    except Exception as e:
        log.error(f"Error in scan_platform: {e}")
        # Catch all exceptions and emit error to the client
        await sm.emit("scan:done_ko", str(e))
        # Re-raise the exception to be caught by the error handler
        raise e


@socket_handler.socket_server.on("scan")  # type: ignore
async def scan_handler(_sid: str, options: dict[str, Any]):
    """Scan socket endpoint

    Args:
        options (dict): Socket options
    """

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning"))

    platform_ids = options.get("platforms", [])
    scan_type = ScanType[options.get("type", "quick").upper()]
    roms_ids = options.get("roms_ids", [])
    metadata_sources = options.get("apis", [])

    if DEV_MODE:
        return await scan_platforms(
            platform_ids=platform_ids,
            scan_type=scan_type,
            roms_ids=roms_ids,
            metadata_sources=metadata_sources,
        )

    return high_prio_queue.enqueue(
        scan_platforms,
        platform_ids,
        scan_type,
        roms_ids,
        metadata_sources,
        job_timeout=SCAN_TIMEOUT,  # Timeout (default of 4 hours)
    )


@socket_handler.socket_server.on("scan:stop")  # type: ignore
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
