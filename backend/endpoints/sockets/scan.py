from __future__ import annotations

import asyncio
from dataclasses import dataclass
from itertools import batched
from typing import Any, Final

import socketio  # type: ignore
from rq import Worker
from rq.job import Job

from config import DEV_MODE, REDIS_URL, SCAN_TIMEOUT, SCAN_WORKERS, TASK_RESULT_TTL
from config.config_manager import config_manager as cm
from endpoints.responses import TaskType
from endpoints.responses.platform import PlatformSchema
from endpoints.responses.rom import SimpleRomSchema
from exceptions.fs_exceptions import (
    FOLDER_STRUCT_MSG,
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
from handler.metadata import meta_gamelist_handler
from handler.metadata.ss_handler import get_preferred_media_types
from handler.redis_handler import get_job_func_name, high_prio_queue, redis_client
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
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom, RomFile
from tasks.tasks import update_job_meta
from utils import emoji
from utils.context import initialize_context

STOP_SCAN_FLAG: Final = "scan:stop"


@dataclass
class ScanStats:
    total_platforms: int = 0
    total_roms: int = 0
    scanned_platforms: int = 0
    new_platforms: int = 0
    identified_platforms: int = 0
    scanned_roms: int = 0
    new_roms: int = 0
    identified_roms: int = 0
    scanned_firmware: int = 0
    new_firmware: int = 0

    def __post_init__(self):
        # Lock for thread-safe updates
        self._lock = asyncio.Lock()

    async def update(self, socket_manager: socketio.AsyncRedisManager, **kwargs):
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

            update_job_meta({"scan_stats": self.to_dict()})
            await socket_manager.emit("scan:update_stats", self.to_dict())

    async def increment(self, socket_manager: socketio.AsyncRedisManager, **kwargs):
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    current_value = getattr(self, key)
                    setattr(self, key, current_value + value)

            update_job_meta({"scan_stats": self.to_dict()})
            await socket_manager.emit("scan:update_stats", self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_platforms": self.total_platforms,
            "total_roms": self.total_roms,
            "scanned_platforms": self.scanned_platforms,
            "new_platforms": self.new_platforms,
            "identified_platforms": self.identified_platforms,
            "scanned_roms": self.scanned_roms,
            "new_roms": self.new_roms,
            "identified_roms": self.identified_roms,
            "scanned_firmware": self.scanned_firmware,
            "new_firmware": self.new_firmware,
        }


def _get_socket_manager() -> socketio.AsyncRedisManager:
    """Connect to external socketio server"""
    return socketio.AsyncRedisManager(REDIS_URL, write_only=True)


async def _identify_firmware(
    platform: Platform,
    fs_fw: str,
) -> int:
    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return 0

    firmware = db_firmware_handler.get_firmware_by_filename(platform.id, fs_fw)

    scanned_firmware = await scan_firmware(
        platform=platform,
        file_name=fs_fw,
        firmware=firmware,
    )

    is_verified = Firmware.verify_file_hashes(
        platform_slug=platform.slug,
        file_name=fs_fw,
        file_size_bytes=scanned_firmware.file_size_bytes,
        md5_hash=scanned_firmware.md5_hash,
        sha1_hash=scanned_firmware.sha1_hash,
        crc_hash=scanned_firmware.crc_hash,
    )

    scanned_firmware.missing_from_fs = False
    scanned_firmware.is_verified = is_verified
    db_firmware_handler.add_firmware(scanned_firmware)

    return 1 if not firmware else 0


def _should_scan_rom(
    scan_type: ScanType,
    rom: Rom | None,
    roms_ids: list[int],
    metadata_sources: list[str],
) -> bool:
    """Decide if a rom should be scanned or not

    Args:
        scan_type (ScanType): Type of scan to be performed.
        rom (Rom | None): The rom to be scanned.
        roms_ids (list[int]): List of selected roms to be scanned.
        metadata_sources (list[str]): List of metadata sources to be used.
    """

    # This logic is tricky so only touch it if you know what you're doing"""
    should_scan = bool(
        # Any new roms should be scanned
        (scan_type in {ScanType.NEW_PLATFORMS, ScanType.QUICK} and not rom)
        # Complete rescan should scan all roms
        or (scan_type == ScanType.COMPLETE)
        # Hashes rescan should scan all roms to update the hashes
        or (scan_type == ScanType.HASHES)
        or (
            rom
            and (
                # Selected ROMs are always scanned
                (rom.id in roms_ids)
                # Update scan should scan ROMs identified by the selected metadata sources
                or (
                    scan_type == ScanType.UPDATE
                    and rom.is_identified
                    and any(getattr(rom, f"{source}_id") for source in metadata_sources)
                )
                # Unmatched scan should scan ROMs that are not identified by the selected metadata sources
                or (
                    scan_type == ScanType.UNMATCHED
                    and any(
                        not getattr(rom, f"{source}_id") for source in metadata_sources
                    )
                )
            )
        )
    )

    return should_scan


def _should_get_rom_files(
    scan_type: ScanType,
    rom: Rom,
    newly_added: bool,
    roms_ids: list[int],
) -> bool:
    """Decide if the files of a rom should be rebuilt or not

    Args:
        scan_type (ScanType): Type of scan to be performed.
        rom (Rom): The rom to be rebuilt.
        newly_added (bool): Whether the rom is newly added.
        roms_ids (list[int]): List of selected roms to be scanned.
    """
    # Get hash calculation setting from config
    calculate_hashes = not cm.get_config().SKIP_HASH_CALCULATION

    # Skip file processing entirely if hashes are disabled (except for HASHES scan type)
    if not calculate_hashes and scan_type != ScanType.HASHES:
        return False

    return bool(
        (scan_type in {ScanType.NEW_PLATFORMS, ScanType.QUICK} and newly_added)
        or (scan_type == ScanType.COMPLETE)
        or (scan_type == ScanType.HASHES)
        or (rom and rom.id in roms_ids)
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
    scan_stats: ScanStats,
    calculate_hashes: bool = True,
) -> None:
    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return

    if not _should_scan_rom(
        scan_type=scan_type,
        rom=rom,
        roms_ids=roms_ids,
        metadata_sources=metadata_sources,
    ):
        if rom:
            # Just to update the filesystem data
            db_rom_handler.update_rom(
                rom.id, {"fs_name": fs_rom["fs_name"], "missing_from_fs": False}
            )

        return

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
                url_cover="",
                url_manual="",
                url_screenshots=[],
            )
        )

    # Build rom files object before scanning
    should_update_files = _should_get_rom_files(
        scan_type=scan_type,
        rom=rom,
        newly_added=newly_added,
        roms_ids=roms_ids,
    )
    if should_update_files:
        # Get hash calculation setting from config
        calculate_hashes = not cm.get_config().SKIP_HASH_CALCULATION
        if calculate_hashes:
            log.debug(f"Calculating file hashes for {rom.fs_name}...")
        (
            rom_files,
            rom_crc_c,
            rom_md5_h,
            rom_sha1_h,
            rom_ra_h,
        ) = await fs_rom_handler.get_rom_files(rom, calculate_hashes=calculate_hashes)
        fs_rom.update(
            {
                "files": rom_files,
                "crc_hash": rom_crc_c,
                "md5_hash": rom_md5_h,
                "sha1_hash": rom_sha1_h,
                "ra_hash": rom_ra_h,
            }
        )

    log.debug(f"Scanning {rom.fs_name}...")
    scanned_rom = await scan_rom(
        scan_type=scan_type,
        platform=platform,
        rom=rom,
        fs_rom=fs_rom,
        metadata_sources=metadata_sources,
        newly_added=newly_added,
        socket_manager=socket_manager,
    )

    await scan_stats.increment(
        socket_manager=socket_manager,
        scanned_roms=1,
        new_roms=1 if newly_added else 0,
        identified_roms=1 if scanned_rom.is_identified else 0,
    )

    _added_rom = db_rom_handler.add_rom(scanned_rom)

    if _added_rom.is_identified:
        await socket_manager.emit(
            "scan:scanning_rom",
            SimpleRomSchema.from_orm_with_factory(_added_rom).model_dump(
                exclude={"created_at", "updated_at", "rom_user"}
            ),
        )

    if should_update_files:
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
            for file in fs_rom["files"]
        ]
        for new_rom_file in new_rom_files:
            db_rom_handler.add_rom_file(new_rom_file)

    # Short circuit if the scan type is hashes
    if scan_type == ScanType.HASHES:
        return

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
        overwrite=True,
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
            "path_cover_s": path_cover_s,
            "path_cover_l": path_cover_l,
            "path_screenshots": path_screenshots,
            "path_manual": path_manual,
        },
    )

    # Handle special media files from Screenscraper
    if _added_rom.ss_metadata:
        preferred_media_types = get_preferred_media_types()
        for media_type in preferred_media_types:
            if _added_rom.ss_metadata.get(f"{media_type.value}_path"):
                await fs_resource_handler.store_media_file(
                    _added_rom.ss_metadata[f"{media_type.value}_url"],
                    _added_rom.ss_metadata[f"{media_type.value}_path"],
                )

    # Handle special media files from ES-DE gamelist.xml
    if _added_rom.gamelist_metadata:
        preferred_media_types = get_preferred_media_types()
        for media_type in preferred_media_types:
            if _added_rom.gamelist_metadata.get(f"{media_type.value}_path"):
                await fs_resource_handler.store_media_file(
                    _added_rom.gamelist_metadata[f"{media_type.value}_url"],
                    _added_rom.gamelist_metadata[f"{media_type.value}_path"],
                )

    # Store normal and locked badges
    if _added_rom.ra_metadata:
        for ach in _added_rom.ra_metadata.get("achievements", []):
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

    await socket_manager.emit(
        "scan:scanning_rom",
        SimpleRomSchema.from_orm_with_factory(_added_rom).model_dump(
            exclude={"created_at", "updated_at", "rom_user"}
        ),
    )


async def _identify_platform(
    platform_slug: str,
    scan_type: ScanType,
    fs_platforms: list[str],
    roms_ids: list[int],
    metadata_sources: list[str],
    socket_manager: socketio.AsyncRedisManager,
    scan_stats: ScanStats,
    calculate_hashes: bool = True,
) -> ScanStats:
    # Stop the scan if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        raise ScanStoppedException()

    platform = db_platform_handler.get_platform_by_fs_slug(platform_slug)
    if platform and scan_type == ScanType.NEW_PLATFORMS:
        return scan_stats

    scanned_platform = await scan_platform(platform_slug, fs_platforms)
    if platform:
        scanned_platform.id = platform.id

    await scan_stats.increment(
        socket_manager=socket_manager,
        scanned_platforms=1,
        new_platforms=1 if not platform else 0,
        identified_platforms=1 if scanned_platform.is_identified else 0,
    )

    platform = db_platform_handler.add_platform(scanned_platform)

    # Preparse the platform's gamelist.xml file and cache it
    await meta_gamelist_handler.populate_cache(platform)

    await socket_manager.emit(
        "scan:scanning_platform",
        PlatformSchema.model_validate(platform).model_dump(
            include={"id", "name", "display_name", "slug", "fs_slug", "is_identified"}
        ),
    )

    # Scanning firmware
    try:
        fs_firmware = await fs_firmware_handler.get_firmware(platform.fs_slug)
    except FirmwareNotFoundException:
        fs_firmware = []

    if len(fs_firmware) == 0:
        log.warning(
            f"{hl(emoji.EMOJI_WARNING, color=LIGHTYELLOW)} No firmware found for {hl(platform.custom_name or platform.name, color=BLUE)}[{hl(platform.fs_slug)}]"
        )
    else:
        log.info(f"{hl(str(len(fs_firmware)))} firmware files found")

    new_firmware = 0
    for fs_fw in fs_firmware:
        new_firmware += await _identify_firmware(
            platform=platform,
            fs_fw=fs_fw,
        )

    # This reduces the number of socket emissions
    await scan_stats.increment(
        socket_manager=socket_manager,
        scanned_firmware=len(fs_firmware),
        new_firmware=new_firmware,
    )

    # Scanning roms
    try:
        fs_roms = await fs_rom_handler.get_roms(platform)
    except RomsNotFoundException as e:
        log.error(e)
        return scan_stats

    if len(fs_roms) == 0:
        log.warning(
            f"{hl(emoji.EMOJI_WARNING, color=LIGHTYELLOW)} No roms found, verify that the folder structure is correct"
        )
    else:
        log.info(f"{hl(str(len(fs_roms)))} roms found in the file system")

    # Create semaphore to limit concurrent ROM scanning
    scan_semaphore = asyncio.Semaphore(SCAN_WORKERS)

    async def scan_rom_with_semaphore(fs_rom: FSRom, rom: Rom | None) -> None:
        """Scan a single ROM with semaphore limiting"""
        async with scan_semaphore:
            await _identify_rom(
                platform=platform,
                fs_rom=fs_rom,
                rom=rom,
                scan_type=scan_type,
                roms_ids=roms_ids,
                metadata_sources=metadata_sources,
                socket_manager=socket_manager,
                scan_stats=scan_stats,
                calculate_hashes=calculate_hashes,
            )

    for fs_roms_batch in batched(fs_roms, 200, strict=False):
        roms_by_fs_name = db_rom_handler.get_roms_by_fs_name(
            platform_id=platform.id,
            fs_names={fs_rom["fs_name"] for fs_rom in fs_roms_batch},
        )

        # Process ROMs concurrently within the batch
        scan_tasks = [
            scan_rom_with_semaphore(
                fs_rom=fs_rom, rom=roms_by_fs_name.get(fs_rom["fs_name"])
            )
            for fs_rom in fs_roms_batch
        ]

        # Wait for all ROMs in the batch to complete
        batched_results = await asyncio.gather(*scan_tasks, return_exceptions=True)
        for result, fs_rom in zip(batched_results, fs_roms_batch, strict=False):
            if isinstance(result, Exception):
                log.error(f"Error scanning ROM {fs_rom['fs_name']}: {result}")

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
    metadata_sources: list[str],
    scan_type: ScanType = ScanType.QUICK,
    roms_ids: list[int] | None = None,
) -> ScanStats:
    """Scan all the listed platforms and fetch metadata from different sources

    Args:
        platform_ids (list[int]): List of platform ids to be scanned
        metadata_sources (list[str]): List of metadata sources to be used
        scan_type (ScanType): Type of scan to be performed.
        roms_ids (list[int], optional): List of selected roms to be scanned.
    """

    # Get hash calculation setting from config
    calculate_hashes = not cm.get_config().SKIP_HASH_CALCULATION

    if not roms_ids:
        roms_ids = []

    socket_manager = _get_socket_manager()
    scan_stats = ScanStats()

    try:
        fs_platforms: list[str] = await fs_platform_handler.get_platforms()
    except FolderStructureNotMatchException as e:
        log.error(e)
        await socket_manager.emit("scan:done_ko", e.message)
        return scan_stats

    # Clear the gamelist cache  to ensure we're using fresh gamelist.xml data
    meta_gamelist_handler.clear_cache()

    # Precalculate total platforms and ROMs
    total_roms = 0
    for platform_slug in fs_platforms:
        fs_roms = await fs_rom_handler.get_roms(Platform(fs_slug=platform_slug))
        total_roms += len(fs_roms)
    await scan_stats.update(
        socket_manager=socket_manager,
        total_platforms=len(fs_platforms),
        total_roms=total_roms,
    )

    async def stop_scan():
        log.info(f"{emoji.EMOJI_STOP_SIGN} Scan stopped manually")
        await socket_manager.emit("scan:done", scan_stats.to_dict())
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
                f"{hl(emoji.EMOJI_WARNING, color=LIGHTYELLOW)} No platforms found, verify that the folder structure is right and the volume is mounted correctly."
                f"{FOLDER_STRUCT_MSG}"
            )
        else:
            log.info(
                f"Found {hl(str(len(platform_list)))} platforms in the file system"
            )

        for platform_slug in platform_list:
            scan_stats = await _identify_platform(
                platform_slug=platform_slug,
                scan_type=scan_type,
                fs_platforms=fs_platforms,
                roms_ids=roms_ids,
                metadata_sources=metadata_sources,
                socket_manager=socket_manager,
                scan_stats=scan_stats,
                calculate_hashes=calculate_hashes,
            )

        missed_platforms = db_platform_handler.mark_missing_platforms(fs_platforms)
        if len(missed_platforms) > 0:
            log.warning(f"{hl('Missing')} platforms from filesystem:")
            for p in missed_platforms:
                log.warning(f" - {p.slug} ({p.fs_slug})")

        log.info(f"{emoji.EMOJI_CHECK_MARK} Scan completed")
        await socket_manager.emit("scan:done", scan_stats.to_dict())
    except ScanStoppedException:
        await stop_scan()
    except Exception as e:
        log.error(f"Error in scan_platform: {e}")
        # Catch all exceptions and emit error to the client
        await socket_manager.emit("scan:done_ko", str(e))
        # Re-raise the exception to be caught by the error handler
        raise e

    return scan_stats


@socket_handler.socket_server.on("scan")  # type: ignore
async def scan_handler(_sid: str, options: dict[str, Any]):
    """Scan socket endpoint

    Args:
        options (dict): Socket options
    """

    log.info(f"{emoji.EMOJI_MAGNIFYING_GLASS_TILTED_RIGHT} Scanning")

    platform_ids = options.get("platforms", [])
    scan_type = ScanType[options.get("type", "quick").upper()]
    roms_ids = options.get("roms_ids", [])
    metadata_sources = options.get("apis", [])

    if DEV_MODE:
        return await scan_platforms(
            platform_ids=platform_ids,
            metadata_sources=metadata_sources,
            scan_type=scan_type,
            roms_ids=roms_ids,
        )

    return high_prio_queue.enqueue(
        scan_platforms,
        platform_ids=platform_ids,
        metadata_sources=metadata_sources,
        scan_type=scan_type,
        roms_ids=roms_ids,
        job_timeout=SCAN_TIMEOUT,  # Timeout (default of 4 hours)
        result_ttl=TASK_RESULT_TTL,
        meta={
            "task_name": f"{scan_type.value.capitalize()} Scan",
            "task_type": TaskType.SCAN,
        },
    )


@socket_handler.socket_server.on("scan:stop")  # type: ignore
async def stop_scan_handler(_sid: str):
    """Stop scan socket endpoint"""

    log.info(f"{emoji.EMOJI_STOP_BUTTON} Stop scan requested...")

    async def cancel_job(job: Job):
        job.cancel()
        redis_client.set(STOP_SCAN_FLAG, 1)
        log.info(f"{emoji.EMOJI_STOP_BUTTON} Job found, stopping scan...")

    existing_jobs = high_prio_queue.get_jobs()
    for job in existing_jobs:
        if get_job_func_name(job) == "scan_platform" and job.is_started:
            return await cancel_job(job)

    workers = Worker.all(connection=redis_client)
    for worker in workers:
        current_job = worker.get_current_job()
        if (
            current_job
            and get_job_func_name(current_job)
            == "endpoints.sockets.scan.scan_platforms"
            and current_job.is_started
        ):
            return await cancel_job(current_job)

    log.info(f"{emoji.EMOJI_STOP_BUTTON} No running scan to stop")
