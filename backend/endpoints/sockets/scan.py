from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import batched
from typing import Any, Final

import socketio  # type: ignore
from redis import Redis
from rq import get_current_job
from rq.exceptions import AbandonedJobError
from rq.job import Job, JobStatus
from sqlalchemy.exc import IntegrityError

from adapters.services.sigil import SWITCH_PLATFORM_SLUGS
from config import DEV_MODE, REDIS_URL, SCAN_TIMEOUT, SCAN_WORKERS, TASK_RESULT_TTL
from config.config_manager import MetadataMediaType
from config.config_manager import config_manager as cm
from endpoints.responses import TaskType
from endpoints.responses.platform import PlatformSchema
from endpoints.responses.rom import SimpleRomSchema
from endpoints.sockets.activity import get_authenticated_user
from exceptions.fs_exceptions import (
    FOLDER_STRUCT_MSG,
    FirmwareNotFoundException,
    FolderStructureNotMatchException,
    RomsNotFoundException,
)
from exceptions.socket_exceptions import ScanStoppedException
from handler.auth.constants import Scope
from handler.database import (
    db_collection_handler,
    db_firmware_handler,
    db_platform_handler,
    db_rom_handler,
)
from handler.filesystem import (
    fs_firmware_handler,
    fs_platform_handler,
    fs_resource_handler,
    fs_rom_handler,
)
from handler.filesystem.roms_handler import FSRom, ParsedRomFiles
from handler.metadata import (
    meta_gamelist_handler,
    meta_hltb_handler,
    meta_launchbox_handler,
)
from handler.metadata.launchbox_handler.types import LAUNCHBOX_PLATFORMS_DIR
from handler.metadata.ss_handler import begin_scan as begin_ss_scan
from handler.metadata.ss_handler import log_quota as log_ss_quota
from handler.metadata.ss_handler import log_scan_summary as log_ss_scan_summary
from handler.recommendation import top_up_similarity
from handler.redis_handler import (
    cancel_job,
    get_job_status,
    redis_client,
    scan_queue,
)
from handler.rom_files import loaded_rom_files, refresh_rom_files
from handler.scan_handler import (
    MetadataSource,
    ScanType,
    build_hashless_fs_rom,
    download_rom_resources,
    persist_soundtrack_cover,
    scan_firmware,
    scan_platform,
    scan_rom,
)
from handler.scan_jobs import (
    get_blocking_library_scans,
    get_queued_scan_jobs,
    get_running_scan_job,
    get_scheduled_scan_jobs,
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
from utils.audio_tags import remove_persisted_cover
from utils.context import initialize_context
from utils.gamelist_exporter import GamelistExporter
from utils.pegasus_exporter import PegasusExporter

STOP_SCAN_FLAG: Final = "scan:stop"


def scan_job_meta(scan_type: ScanType) -> dict[str, Any]:
    """What a scan job carries so a client can tell which scan is running."""
    return {
        "task_name": f"{scan_type.value.replace('_', ' ').title()} Scan",
        "task_type": TaskType.SCAN.value,
    }


def report_scan_failure(
    job: Job, connection: Redis, exc_type: type, exc_value: BaseException, tb: Any
) -> None:
    """Tell the clients a scan is over when the scan could not say so itself.

    A worker killed mid-scan never reaches the handler that emits this, so the
    clients would keep showing a scan that no longer exists.
    """
    # Every other failure is reported by the scan as it unwinds, and emitting
    # here too would report it twice.
    if exc_type is not AbandonedJobError:
        return

    log.warning(f"{emoji.EMOJI_STOP_SIGN} Scan {job.id} was abandoned by its worker")
    try:
        asyncio.run(
            _get_socket_manager().emit(
                "scan:done_ko", "the worker running it stopped unexpectedly"
            )
        )
    except Exception:
        # RQ re-raises out of the registry sweep that calls this, which would
        # leave the abandoned scans in the registry and stop the worker.
        log.error(f"Could not report abandoned scan {job.id}", exc_info=True)


def _scan_job_label(job: Job) -> str:
    """How to refer to a scan job when reporting it to a client."""
    return str(job.meta.get("task_name") or "A scan")


def _scan_in_flight_message(running: Job | None, queued: list[Job]) -> str:
    """Say which scan is in the way, so the client knows what to wait on."""
    if running is None:
        return f"{_scan_job_label(queued[0])} is already queued"

    stopping = (JobStatus.CANCELED, JobStatus.STOPPED)
    if get_job_status(running, refresh=False) in stopping:
        return f"{_scan_job_label(running)} is still stopping, try again in a moment"

    return f"{_scan_job_label(running)} is already running"


# A scan reports once per rom, and each report is a synchronous redis write plus
# a publish. Coalescing keeps that cost off the per-rom path.
SCAN_STATS_PUBLISH_INTERVAL = 0.25


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
    updated_roms: int = 0
    new_files: int = 0

    def __post_init__(self):
        # Lock for thread-safe updates
        self._lock = asyncio.Lock()
        self._unpublished = False
        # None until the first report, so a scan never coalesces away its first.
        self._published_at: float | None = None

    async def _publish(
        self, socket_manager: socketio.AsyncRedisManager, *, force: bool
    ) -> None:
        """Tell the clients where the scan is. The caller holds the lock."""
        now = time.monotonic()
        if (
            not force
            and self._published_at is not None
            and now - self._published_at < SCAN_STATS_PUBLISH_INTERVAL
        ):
            self._unpublished = True
            return

        self._unpublished = False
        self._published_at = now
        stats = self.to_dict()
        update_job_meta({"scan_stats": stats})
        await socket_manager.emit("scan:update_stats", stats)

    async def update(self, socket_manager: socketio.AsyncRedisManager, **kwargs):
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

            # Totals and platform counts land at phase boundaries, rarely enough
            # to report as they happen.
            await self._publish(socket_manager, force=True)

    async def increment(self, socket_manager: socketio.AsyncRedisManager, **kwargs):
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    current_value = getattr(self, key)
                    setattr(self, key, current_value + value)

            await self._publish(socket_manager, force=False)

    async def flush(self, socket_manager: socketio.AsyncRedisManager) -> None:
        """Publish counters a coalesced increment left unreported."""
        async with self._lock:
            if self._unpublished:
                await self._publish(socket_manager, force=True)

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
            "updated_roms": self.updated_roms,
            "new_files": self.new_files,
        }


def _get_socket_manager() -> socketio.AsyncRedisManager:
    """Connect to external socketio server"""
    return socketio.AsyncRedisManager(REDIS_URL, write_only=True)


async def _identify_firmware(
    platform: Platform,
    fs_fw: str,
    scan_type: ScanType,
) -> int:
    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return 0

    firmware = db_firmware_handler.get_firmware_by_filename(platform.id, fs_fw)

    # The row is consulted before the filesystem, so an entry that could never
    # be skipped costs no stat.
    if firmware and not _should_hash_firmware(scan_type, firmware):
        # The file is stat'd where it was just enumerated, never at the path the
        # row recorded. A row whose path predates a change in the library layout
        # is rebuilt below instead, which is what refreshes it.
        firmware_path = fs_firmware_handler.get_firmware_fs_structure(platform.fs_slug)
        if firmware.file_path == firmware_path:
            file_size = await fs_firmware_handler.get_file_size(
                f"{firmware_path}/{fs_fw}"
            )
            if file_size == firmware.file_size_bytes:
                # Only written when it actually flips, keeping `updated_at`
                # usable as an incremental signal.
                if firmware.missing_from_fs:
                    db_firmware_handler.update_firmware(
                        firmware.id, {"missing_from_fs": False}
                    )
                return 0

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


# `files` is left out so a scan does not ship every file row of every rom.
SCANNING_ROM_EXCLUDE: Final = {
    "created_at",
    "updated_at",
    "rom_user",
    "last_modified",
    "files",
    "sibling_roms",
}


async def _emit_scanning_rom(
    socket_manager: socketio.AsyncRedisManager, rom: Rom
) -> None:
    await socket_manager.emit(
        "scan:scanning_rom",
        SimpleRomSchema.from_orm_with_factory(rom).model_dump(
            exclude=SCANNING_ROM_EXCLUDE
        ),
    )


def should_scan_rom(
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

    # When roms_ids is provided, the scan is scoped to those roms only
    if roms_ids:
        return bool(rom and rom.id in roms_ids)

    # This logic is tricky so only touch it if you know what you're doing"""
    should_scan = bool(
        # New platforms only looks for roms it has never seen
        (scan_type == ScanType.NEW_PLATFORMS and not rom)
        # Quick adds new roms and reconciles the files of the ones it knows
        or (scan_type == ScanType.QUICK)
        # Complete rescan should scan all roms
        or (scan_type == ScanType.COMPLETE)
        # Hashes rescan should scan all roms to update the hashes
        or (scan_type == ScanType.HASHES)
        or (
            rom
            and (
                # Update scan should scan ROMs identified by the selected metadata sources
                (
                    scan_type == ScanType.UPDATE
                    and rom.is_identified
                    and any(
                        getattr(rom, f"{source}_id", None)
                        for source in metadata_sources
                    )
                )
                # Unmatched scan should scan ROMs that are not identified by the selected metadata sources
                or (
                    scan_type == ScanType.UNMATCHED
                    and any(
                        not getattr(rom, f"{source}_id", None)
                        for source in metadata_sources
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

    return bool(
        newly_added
        or (scan_type == ScanType.COMPLETE)
        or (scan_type == ScanType.HASHES)
        or (rom and rom.id in roms_ids)
    )


def _should_extract_title_ids(scan_type: ScanType, rom: Rom) -> bool:
    """Decide if a rescan should re-read title ids out of a rom's binaries.

    Extraction is a native parse of every ROM file, so it is not repeated for a
    rom that already carries an id. A scan that re-reads the bytes refreshes it
    regardless, since replaced files would otherwise keep the old id next to
    the new hashes. The Switch family always re-reads because the same parse is
    what settles its per-file categories.

    Args:
        scan_type (ScanType): Type of scan to be performed.
        rom (Rom): The existing rom being rescanned.
    """

    return bool(
        scan_type in (ScanType.COMPLETE, ScanType.HASHES)
        or not rom.title_id
        or rom.platform_slug in SWITCH_PLATFORM_SLUGS
    )


def _should_reparse_tags(
    scan_type: ScanType,
    rom: Rom,
    roms_ids: list[int],
) -> bool:
    """Decide if filename tags should be re-read onto an existing rom

    A rom parses its tags when it is first inserted and again when the edit
    endpoint renames it, but never in between, so a change to `parse_tags` only
    reaches rows that were scanned after it. A complete rescan or an explicit
    per-rom selection re-reads them; a hashes rescan does not, since it is
    scoped to re-reading file bytes.

    Args:
        scan_type (ScanType): Type of scan to be performed.
        rom (Rom): The rom whose tags may be re-read.
        roms_ids (list[int]): List of selected roms to be scanned.
    """

    return bool(scan_type == ScanType.COMPLETE or (rom and rom.id in roms_ids))


def _should_hash_incrementally(
    scan_type: ScanType,
    rom: Rom | None,
    roms_ids: list[int],
) -> bool:
    """Decide if a selected rom's unchanged files may keep their stored hashes

    Only COMPLETE and HASHES promise to re-read every byte. A quick scan does
    not reach here: it reconciles an existing rom through `refresh_rom_files`.

    Args:
        scan_type (ScanType): Type of scan to be performed.
        rom (Rom | None): The rom whose files are rebuilt.
        roms_ids (list[int]): List of selected roms to be scanned.
    """

    return bool(
        scan_type in (ScanType.UPDATE, ScanType.UNMATCHED)
        and rom
        and rom.id in roms_ids
    )


def _should_hash_firmware(
    scan_type: ScanType,
    firmware: Firmware | None,
) -> bool:
    """Decide if a firmware file's hashes should be recalculated or not

    The firmware counterpart of `_should_get_rom_files`: bytes are only re-read
    for a new entry or a scan that asked for hashes. An entry with no stored
    hash is treated as new.

    Args:
        scan_type (ScanType): Type of scan to be performed.
        firmware (Firmware | None): The firmware entry already in the database.
    """

    return bool(
        firmware is None
        or not firmware.md5_hash
        or (scan_type == ScanType.COMPLETE)
        or (scan_type == ScanType.HASHES)
    )


async def _rebuild_rom_files(
    rom: Rom,
    fs_rom: FSRom,
    calculate_hashes: bool,
    extract_title_ids: bool,
    embed_title_ids: bool,
    existing_files: Sequence[RomFile] | None = None,
) -> ParsedRomFiles:
    """Re-read a rom's files onto `fs_rom`, embedding title ids when enabled."""
    parsed = await fs_rom_handler.get_rom_files(
        rom,
        calculate_hashes=calculate_hashes,
        extract_title_ids=extract_title_ids,
        existing_files=existing_files,
    )

    renamed_rom_fs_name = (
        await fs_rom_handler.embed_switch_title_ids(parsed) if embed_title_ids else None
    )

    fs_rom.update(
        {
            "files": parsed.rom_files,
            "crc_hash": parsed.crc_hash,
            "md5_hash": parsed.md5_hash,
            "sha1_hash": parsed.sha1_hash,
            "ra_hash": parsed.ra_hash,
            "identity": parsed.identity,
        }
    )
    if renamed_rom_fs_name:
        fs_rom["fs_name"] = renamed_rom_fs_name

    return parsed


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
    launchbox_remote_enabled: bool,
    playmatch_enabled: bool,
    socket_manager: socketio.AsyncRedisManager,
    scan_stats: ScanStats,
    scanned_rom_ids: set[int],
) -> None:
    # Break early if the flag is set
    if redis_client.get(STOP_SCAN_FLAG):
        return

    # A quick scan only reconciles an existing entry's files with disk, so it
    # needs none of the metadata prelude below.
    if rom is not None and scan_type == ScanType.QUICK:
        refreshed = await refresh_rom_files(rom)
        await scan_stats.increment(
            socket_manager=socket_manager,
            scanned_roms=1,
            updated_roms=1 if refreshed.changed else 0,
            new_files=refreshed.new_files,
        )
        if refreshed.changed:
            log.info(
                f"Files of {hl(rom.name or rom.fs_name, color=BLUE)} refreshed: "
                f"{refreshed.new_files} new, {refreshed.updated_files} updated, "
                f"{refreshed.removed_files} removed"
            )
            hydrated_rom = db_rom_handler.get_rom_simple(rom.id)
            if hydrated_rom is not None:
                await _emit_scanning_rom(socket_manager, hydrated_rom)
        return

    # Update properties that don't require metadata
    parsed_tags = fs_rom_handler.parse_tags(fs_rom["fs_name"])
    roms_path = fs_rom_handler.get_roms_fs_structure(platform.fs_slug)

    rom_attrs = {
        "fs_name": fs_rom["fs_name"],
        "fs_path": roms_path,
        "regions": parsed_tags.regions,
        "revision": parsed_tags.revision,
        "version": parsed_tags.version,
        "languages": parsed_tags.languages,
        "tags": parsed_tags.other_tags,
        "platform_id": platform.id,
        "name": fs_rom_handler.get_file_name_with_no_tags(fs_rom["fs_name"]),
        "url_cover": "",
        "url_manual": "",
        "url_screenshots": [],
    }

    cnfg = cm.get_config()
    calculate_hashes = not cnfg.SKIP_HASH_CALCULATION
    extract_title_ids = not cnfg.SKIP_TITLE_ID_EXTRACTION
    embed_title_ids = cnfg.EMBED_SWITCH_TITLE_IDS

    newly_added: bool = rom is None
    reassociated: bool = False
    files_built: bool = False

    if rom is None:
        # No entry matches this filename. Before treating it as new, hash
        # the files and check whether they belong to an existing entry that went
        # missing (a renamed or moved ROM), so its collections, notes, and
        # uploaded assets carry over instead of being orphaned on a duplicate.
        parsed_rom_files = await _rebuild_rom_files(
            Rom(
                **rom_attrs,
                platform=platform,
            ),
            fs_rom,
            calculate_hashes=calculate_hashes,
            extract_title_ids=extract_title_ids,
            embed_title_ids=embed_title_ids,
        )
        # The new-entry insert reads its name from rom_attrs, not fs_rom.
        rom_attrs["fs_name"] = fs_rom["fs_name"]
        files_built = True

        missing_match = db_rom_handler.get_matching_missing_rom(
            platform_id=platform.id,
            crc_hash=parsed_rom_files.crc_hash,
            md5_hash=parsed_rom_files.md5_hash,
            sha1_hash=parsed_rom_files.sha1_hash,
            title_id=parsed_rom_files.identity.title_id,
        )
        if missing_match is not None:
            # Move the existing entry onto the new file, clearing its missing state.
            rom = db_rom_handler.update_rom(
                missing_match.id,
                {
                    "fs_name": fs_rom["fs_name"],
                    "fs_path": roms_path,
                    "regions": parsed_tags.regions,
                    "revision": parsed_tags.revision,
                    "version": parsed_tags.version,
                    "languages": parsed_tags.languages,
                    "tags": parsed_tags.other_tags,
                    "missing_from_fs": False,
                },
            )
            reassociated = True
            newly_added = False
            log.info(
                f"Reassociated {hl(fs_rom['fs_name'])} with existing entry "
                f"{hl(rom.name or rom.fs_name, color=BLUE)} by file hash"
            )
        else:
            try:
                rom = db_rom_handler.add_rom(Rom(**rom_attrs))
            except IntegrityError:
                # A concurrent scan already created this ROM, so skip it here.
                log.debug(
                    f"Skipping {hl(fs_rom['fs_name'])}: already created by a concurrent scan"
                )
                return

    # Re-read the filename tags onto an existing entry. Written onto the instance
    # rather than through update_rom because scan_rom carries these columns
    # forward from the rom it is handed, and merging its result is what persists
    # them.
    if not newly_added and _should_reparse_tags(scan_type, rom, roms_ids):
        rom.regions = parsed_tags.regions
        rom.languages = parsed_tags.languages
        rom.tags = parsed_tags.other_tags
        rom.revision = parsed_tags.revision
        rom.version = parsed_tags.version

    # Build rom files object before scanning. A reassociated ROM always rebuilds
    # its files so the stale paths from the old filename are replaced.
    should_update_files = reassociated or _should_get_rom_files(
        scan_type=scan_type,
        rom=rom,
        newly_added=newly_added,
        roms_ids=roms_ids,
    )
    if should_update_files and not files_built:
        # Get hash calculation setting from config
        if calculate_hashes:
            log.debug(f"Calculating file hashes for {rom.fs_name}...")

        await _rebuild_rom_files(
            rom,
            fs_rom,
            calculate_hashes=calculate_hashes,
            extract_title_ids=extract_title_ids
            and _should_extract_title_ids(scan_type, rom),
            embed_title_ids=embed_title_ids,
            existing_files=(
                loaded_rom_files(rom)
                if _should_hash_incrementally(scan_type, rom, roms_ids)
                else None
            ),
        )
        # Keep the in-memory rom's name matching the renamed file.
        rom.fs_name = fs_rom["fs_name"]

    # For a COMPLETE rescan, wipe all downloaded resources before re-fetching so
    # stale files (e.g. a cover from the wrong region) can't be reused. The
    # post-scan download steps below skip downloads when a file already exists or
    # when the source URL is unchanged, so the on-disk files must be removed here.
    if not newly_added and scan_type == ScanType.COMPLETE:
        try:
            await fs_resource_handler.remove_cover(rom)
        except FileNotFoundError:
            pass

        try:
            await fs_resource_handler.remove_manual(rom)
        except FileNotFoundError:
            pass

        try:
            await fs_resource_handler.remove_directory(
                f"{rom.fs_resources_path}/screenshots"
            )
        except FileNotFoundError:
            pass

        for media_type in MetadataMediaType:
            try:
                await fs_resource_handler.remove_media_resources_path(
                    platform.id, rom.id, media_type
                )
            except FileNotFoundError:
                pass

    log.debug(f"Scanning {rom.fs_name}...")
    scanned_rom = await scan_rom(
        scan_type=scan_type,
        platform=platform,
        rom=rom,
        fs_rom=fs_rom,
        metadata_sources=metadata_sources,
        newly_added=newly_added,
        launchbox_remote_enabled=launchbox_remote_enabled,
        playmatch_enabled=playmatch_enabled,
        socket_manager=socket_manager,
    )

    await scan_stats.increment(
        socket_manager=socket_manager,
        scanned_roms=1,
        new_roms=1 if newly_added else 0,
        identified_roms=1 if scanned_rom.is_identified else 0,
    )

    _added_rom = db_rom_handler.add_rom(scanned_rom)
    scanned_rom_ids.add(_added_rom.id)

    if _added_rom.is_identified:
        await _emit_scanning_rom(socket_manager, _added_rom)

    if should_update_files:
        # Reconcile against the existing rows instead of replacing them, so file
        # ids survive a rescan and anything keyed on them (track metadata,
        # persisted soundtrack covers) stays valid.
        synced = db_rom_handler.sync_rom_files(_added_rom.id, fs_rom["files"])
        for cover_path in synced.orphaned_cover_paths:
            remove_persisted_cover(cover_path)
        for saved in synced.files:
            persist_soundtrack_cover(saved, _added_rom)

    # Short circuit if the scan type is hashes
    if scan_type == ScanType.HASHES:
        return

    await download_rom_resources(
        added_rom=_added_rom,
        previous_url_cover=rom.url_cover,
        previous_url_manual=rom.url_manual,
        previous_url_screenshots=rom.url_screenshots,
        metadata_sources=metadata_sources,
    )

    await _emit_scanning_rom(socket_manager, _added_rom)


async def _scan_selected_roms(
    platform: Platform,
    roms: list[Rom],
    scan_type: ScanType,
    roms_ids: list[int],
    metadata_sources: list[str],
    launchbox_remote_enabled: bool,
    playmatch_enabled: bool,
    socket_manager: socketio.AsyncRedisManager,
    scan_stats: ScanStats,
    scanned_rom_ids: set[int],
) -> ScanStats:
    """Scan a hand-picked set of ROMs without touching the rest of their platform.

    The work is resolved from the database rather than the filesystem, so none of
    the platform-wide reconciliation `_identify_platform` does (directory
    listings, the firmware pass, the missing-file sync, a skip-and-mark-present
    pass over every other entry) applies here.
    """
    if redis_client.get(STOP_SCAN_FLAG):
        raise ScanStoppedException()

    # Gamelist matches are served from a per-platform cache, so it has to be
    # warm before any of these ROMs is scanned.
    if MetadataSource.GAMELIST in metadata_sources:
        await meta_gamelist_handler.populate_cache(platform)

    await scan_stats.increment(
        socket_manager=socket_manager,
        scanned_platforms=1,
        identified_platforms=1 if platform.is_identified else 0,
    )

    scan_semaphore = asyncio.Semaphore(SCAN_WORKERS)

    async def scan_rom_with_semaphore(rom: Rom) -> None:
        async with scan_semaphore:
            # A library scan learns this from splitting the platform folder into
            # files and directories; with no listing to consult, ask the path.
            is_flat = await fs_rom_handler.file_exists(rom.full_path)
            if not is_flat and not await fs_rom_handler.directory_exists(rom.full_path):
                # A library scan never reaches an entry whose file is gone, since
                # it walks the filesystem. Reaching one here must not resurrect
                # it: scanning marks a ROM present unconditionally.
                log.warning(
                    f"{hl(rom.fs_name)} is {hl('missing', color=LIGHTYELLOW)} from the "
                    "filesystem, skipping"
                )
                db_rom_handler.update_rom(rom.id, {"missing_from_fs": True})
                await scan_stats.increment(
                    socket_manager=socket_manager, scanned_roms=1
                )
                return

            await _identify_rom(
                platform=platform,
                fs_rom=build_hashless_fs_rom(rom.fs_name, flat=is_flat),
                rom=rom,
                scan_type=scan_type,
                roms_ids=roms_ids,
                metadata_sources=metadata_sources,
                launchbox_remote_enabled=launchbox_remote_enabled,
                playmatch_enabled=playmatch_enabled,
                socket_manager=socket_manager,
                scan_stats=scan_stats,
                scanned_rom_ids=scanned_rom_ids,
            )

    results = await asyncio.gather(
        *[scan_rom_with_semaphore(rom) for rom in roms], return_exceptions=True
    )
    for result, rom in zip(results, roms, strict=False):
        if isinstance(result, Exception):
            log.error(f"Error scanning ROM {rom.fs_name}: {result}")

    # `_identify_rom` returns rather than raises when the flag is set, so a scan
    # stopped mid-gather would otherwise fall through to the post-scan work and
    # report itself done, leaving the flag set behind it.
    if redis_client.get(STOP_SCAN_FLAG):
        raise ScanStoppedException()

    if MetadataSource.SS in metadata_sources:
        log_ss_quota()

    return scan_stats


async def _identify_platform(
    platform_slug: str,
    scan_type: ScanType,
    fs_platforms: list[str],
    roms_ids: list[int],
    metadata_sources: list[str],
    launchbox_remote_enabled: bool,
    playmatch_enabled: bool,
    socket_manager: socketio.AsyncRedisManager,
    scan_stats: ScanStats,
    scanned_rom_ids: set[int],
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
    if MetadataSource.GAMELIST in metadata_sources:
        await meta_gamelist_handler.populate_cache(platform)

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
            scan_type=scan_type,
        )

    # `new_firmware_count` is scoped to this scan: the client reports what the
    # scan discovered, not the platform's total firmware library.
    await socket_manager.emit(
        "scan:scanning_platform",
        {
            **PlatformSchema.model_validate(platform).model_dump(
                include={
                    "id",
                    "name",
                    "display_name",
                    "slug",
                    "fs_slug",
                    "is_identified",
                }
            ),
            "new_firmware_count": new_firmware,
        },
    )

    # This reduces the number of socket emissions
    await scan_stats.increment(
        socket_manager=socket_manager,
        scanned_firmware=len(fs_firmware),
        new_firmware=new_firmware,
    )

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

    # Snapshot the missing entries before the sync below clears the flag for any
    # whose file is back, so the skip path can still tell the client about them.
    previously_missing_rom_ids = db_rom_handler.get_missing_rom_ids(platform.id)

    # Flag entries whose file is gone before identifying files, so a renamed or
    # moved ROM (a new file with no fs_name match) can be reassociated by hash
    # with its now-missing entry instead of spawning a duplicate. The end-of-scan
    # call below re-syncs and logs, unmarking any entry that got reassociated.
    db_rom_handler.mark_missing_roms(platform.id, [rom["fs_name"] for rom in fs_roms])

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
                launchbox_remote_enabled=launchbox_remote_enabled,
                playmatch_enabled=playmatch_enabled,
                socket_manager=socket_manager,
                scan_stats=scan_stats,
                scanned_rom_ids=scanned_rom_ids,
            )

    for fs_roms_batch in batched(fs_roms, 200, strict=False):
        roms_by_fs_name = db_rom_handler.get_roms_by_fs_name(
            platform_id=platform.id,
            fs_names={fs_rom["fs_name"] for fs_rom in fs_roms_batch},
            with_files=scan_type == ScanType.QUICK,
        )

        # Separate skipped ROMs from those that need scanning
        skipped_rom_ids: list[int] = []
        restored_roms: list[Rom] = []
        roms_to_scan: list[tuple[FSRom, Rom | None]] = []

        for fs_rom in fs_roms_batch:
            rom = roms_by_fs_name.get(fs_rom["fs_name"])
            if rom and rom.id in previously_missing_rom_ids:
                restored_roms.append(rom)
            if should_scan_rom(
                scan_type=scan_type,
                rom=rom,
                roms_ids=roms_ids,
                metadata_sources=metadata_sources,
            ):
                roms_to_scan.append((fs_rom, rom))
            elif rom:
                skipped_rom_ids.append(rom.id)

        # Bulk update all skipped ROMs in one query instead of per-ROM updates
        if skipped_rom_ids:
            db_rom_handler.bulk_mark_present(platform.id, skipped_rom_ids)
            await scan_stats.increment(
                socket_manager=socket_manager,
                scanned_roms=len(skipped_rom_ids),
            )

        # A ROM whose file came back would otherwise keep its stale "missing"
        # badge in an open gallery: a skipped one emits nothing, and a scanned
        # one only emits when its files changed. Reload since the scan-loop
        # lookup only eager-loads the platform.
        for restored_rom in restored_roms:
            log.info(
                f"{hl(restored_rom.fs_name)} is back in the filesystem, "
                f"no longer {hl('missing', color=LIGHTYELLOW)}"
            )
            hydrated_rom = db_rom_handler.get_rom_simple(restored_rom.id)
            if hydrated_rom is None:
                continue

            await _emit_scanning_rom(socket_manager, hydrated_rom)

        # Process only ROMs that actually need scanning
        scan_tasks = [
            scan_rom_with_semaphore(fs_rom=fs_rom, rom=rom)
            for fs_rom, rom in roms_to_scan
        ]

        if scan_tasks:
            batched_results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            for result, (fs_rom, _) in zip(batched_results, roms_to_scan, strict=False):
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

    if MetadataSource.SS in metadata_sources:
        log_ss_quota()

    return scan_stats


@initialize_context()
async def scan_platforms(
    platform_ids: list[int],
    metadata_sources: list[str],
    scan_type: ScanType = ScanType.QUICK,
    roms_ids: list[int] | None = None,
    launchbox_remote_enabled: bool = True,
    playmatch_enabled: bool = True,
    platform_fs_slugs: list[str] | None = None,
) -> ScanStats:
    """Scan all the listed platforms and fetch metadata from different sources

    Args:
        platform_ids (list[int]): List of platform ids to be scanned
        metadata_sources (list[str]): List of metadata sources to be used
        scan_type (ScanType): Type of scan to be performed.
        roms_ids (list[int], optional): List of selected roms to be scanned.
        platform_fs_slugs (list[str], optional): Folders to scan with no database row.
    """
    # The flag is cleared by the scan that observes it, so one set against a
    # scan that ended first would otherwise stop this one before it began. A
    # scan still on a worker owns the flag though, and clearing it there would
    # let a stopped scan carry on.
    running_job = get_running_scan_job()
    current_job = get_current_job()
    if running_job is None or (
        current_job is not None and running_job.id == current_job.id
    ):
        redis_client.delete(STOP_SCAN_FLAG)

    if not roms_ids:
        roms_ids = []

    if not platform_fs_slugs:
        platform_fs_slugs = []

    socket_manager = _get_socket_manager()
    scan_stats = ScanStats()

    # Filled in by the ROM pass, and read by the post-scan work that has to know
    # which entries changed rather than how many.
    scanned_rom_ids: set[int] = set()

    async def finish(event: str, payload: Any) -> None:
        """End the scan, reporting whatever a coalesced increment held back."""
        await scan_stats.flush(socket_manager)
        await socket_manager.emit(event, payload)

    # A ROM-id-scoped scan resolves its work from the database, so it neither
    # needs nor can afford the filesystem walk a library scan starts with.
    scoped_roms_by_platform: dict[int, list[Rom]] = {}
    if roms_ids:
        for rom in db_rom_handler.get_roms_by_ids(roms_ids):
            scoped_roms_by_platform.setdefault(rom.platform_id, []).append(rom)

    # ScreenScraper's scan state is process-global, so a scan that never touches
    # it must leave it alone: under DEV_MODE scans run in-process and can
    # overlap, and resetting would drop the other scan's limits and skips.
    if MetadataSource.SS in metadata_sources:
        await begin_ss_scan()

    fs_platforms: list[str] = []
    if not roms_ids:
        try:
            fs_platforms = await fs_platform_handler.get_platforms()
        except FolderStructureNotMatchException as e:
            log.error(e)
            await finish("scan:done_ko", e.message)
            return scan_stats

    # Clear the gamelist cache to ensure we're using fresh gamelist.xml data
    meta_gamelist_handler.clear_cache()

    # Initialize HLTB handler (fetches current search endpoint and security token)
    if MetadataSource.HLTB in metadata_sources:
        await meta_hltb_handler.initialize()

    # A local install is read on every lookup; the per-scan switch only decides
    # whether the cloud store is consulted as well. Both can be empty, and a
    # lookup against an absent source is silent, so what LaunchBox can actually
    # read is recorded here rather than left to be inferred from a platform's
    # worth of empty results.
    if MetadataSource.LAUNCHBOX in metadata_sources:
        local_available = meta_launchbox_handler.is_local_enabled()
        store_available = launchbox_remote_enabled and (
            await meta_launchbox_handler.is_remote_store_populated()
        )
        readable = [
            name
            for name, present in (
                (f"a {hl('local')} install", local_available),
                (f"the {hl('cloud')} store", store_available),
            )
            if present
        ]
        if readable:
            log.info(f"LaunchBox is reading {' and '.join(readable)}")
        elif launchbox_remote_enabled:
            log.warning(
                f"{hl(emoji.EMOJI_WARNING, color=LIGHTYELLOW)} LaunchBox has nothing "
                f"to read: no install at {hl(str(LAUNCHBOX_PLATFORMS_DIR))} and the "
                "cloud store is empty. Run the LaunchBox metadata update task."
            )
        else:
            log.warning(
                f"{hl(emoji.EMOJI_WARNING, color=LIGHTYELLOW)} LaunchBox is set to "
                f"local only and no install was found at "
                f"{hl(str(LAUNCHBOX_PLATFORMS_DIR))}, so it will match nothing. "
                "Switch it to cloud, or mount an install there."
            )

    # Resolve the platforms that will actually be scanned. When no platform ids
    # are provided, every filesystem platform is scanned.
    db_platforms = db_platform_handler.get_platforms()
    db_platforms_by_slug = {p.fs_slug: p for p in db_platforms}
    db_platforms_by_id = {p.id: p for p in db_platforms}

    if roms_ids:
        # A rom whose platform row is gone can't be scanned, so drop it here
        # rather than count it toward a total the scan will never reach.
        scoped_roms_by_platform = {
            platform_id: scoped_roms
            for platform_id, scoped_roms in scoped_roms_by_platform.items()
            if platform_id in db_platforms_by_id
        }
        platform_list = sorted(
            db_platforms_by_id[platform_id].fs_slug
            for platform_id in scoped_roms_by_platform
        )
        total_platforms = len(scoped_roms_by_platform)
        total_roms = sum(len(roms) for roms in scoped_roms_by_platform.values())
    else:
        # Selected platforms arrive as database ids and/or filesystem slugs.
        selected_slugs = [p.fs_slug for p in db_platforms if p.id in platform_ids]
        for fs_slug in platform_fs_slugs:
            if fs_slug in selected_slugs:
                continue
            if fs_slug in db_platforms_by_slug or fs_slug in fs_platforms:
                selected_slugs.append(fs_slug)

        has_selection = bool(platform_ids or platform_fs_slugs)
        platform_list = sorted(selected_slugs if has_selection else fs_platforms)

        # A "new platforms" scan skips platforms that already exist in the database,
        # so they must be excluded from the totals to keep the tracker accurate. This
        # mirrors the existence check done per-platform in _identify_platform, reusing
        # the platforms already fetched above instead of querying again per platform.
        platforms_to_scan = platform_list
        if scan_type == ScanType.NEW_PLATFORMS:
            platforms_to_scan = [
                platform_slug
                for platform_slug in platform_list
                if db_platforms_by_slug.get(platform_slug) is None
            ]

        total_platforms = len(platforms_to_scan)
        total_roms = 0
        for platform_slug in platforms_to_scan:
            try:
                total_roms += await fs_rom_handler.count_roms(
                    Platform(fs_slug=platform_slug)
                )
            except RomsNotFoundException as e:
                log.error(e)

    await scan_stats.update(
        socket_manager=socket_manager,
        total_platforms=total_platforms,
        total_roms=total_roms,
    )

    async def stop_scan():
        log.info(f"{emoji.EMOJI_STOP_SIGN} Scan stopped manually")
        await finish("scan:done", scan_stats.to_dict())
        redis_client.delete(STOP_SCAN_FLAG)

    try:
        if roms_ids:
            log.info(f"Scanning {hl(str(total_roms))} selected roms")

            for platform_id, scoped_roms in scoped_roms_by_platform.items():
                scan_stats = await _scan_selected_roms(
                    platform=db_platforms_by_id[platform_id],
                    roms=scoped_roms,
                    scan_type=scan_type,
                    roms_ids=roms_ids,
                    metadata_sources=metadata_sources,
                    launchbox_remote_enabled=launchbox_remote_enabled,
                    playmatch_enabled=playmatch_enabled,
                    socket_manager=socket_manager,
                    scan_stats=scan_stats,
                    scanned_rom_ids=scanned_rom_ids,
                )
        else:
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
                    launchbox_remote_enabled=launchbox_remote_enabled,
                    playmatch_enabled=playmatch_enabled,
                    socket_manager=socket_manager,
                    scan_stats=scan_stats,
                    scanned_rom_ids=scanned_rom_ids,
                )

            missed_platforms = db_platform_handler.mark_missing_platforms(fs_platforms)
            if len(missed_platforms) > 0:
                log.warning(f"{hl('Missing')} platforms from filesystem:")
                for p in missed_platforms:
                    log.warning(f" - {p.slug} ({p.fs_slug})")

        if MetadataSource.SS in metadata_sources:
            log_ss_scan_summary()

        log.info(f"{emoji.EMOJI_CHECK_MARK} Scan completed")

        # The library changed; drop cached filter values.
        db_rom_handler.invalidate_filter_values_cache()

        # Smart collection membership is derived from the library, and is no
        # longer recomputed while serving a gallery page. A scan scoped to a
        # handful of ROMs only has to recount the collections those ROMs touch.
        # The scan itself is done, so a failure here must not report it as one.
        try:
            if roms_ids:
                db_collection_handler.refresh_smart_collections_for_roms(roms_ids)
            else:
                db_collection_handler.refresh_smart_collections()
        except Exception as e:
            log.error(f"Couldn't refresh smart collections after the scan: {e}")

        # Otherwise the games scanned today have an empty "Similar games"
        # section until the nightly build. Threaded: the scoring is CPU-bound.
        try:
            await asyncio.to_thread(top_up_similarity, scanned_rom_ids)
        except Exception as e:
            log.error(f"Couldn't update recommendations after the scan: {e}")

        # Export metadata files if enabled in config
        config = cm.get_config()

        # Update the list of platforms after the scan to ensure we have the latest data
        db_platforms = db_platform_handler.get_platforms()
        db_platforms_by_slug = {p.fs_slug: p for p in db_platforms}

        if config.GAMELIST_AUTO_EXPORT_ON_SCAN:
            log.info("Auto-exporting gamelist.xml for all platforms...")
            gamelist_exporter = GamelistExporter(local_export=True)
            for platform_slug in platform_list:
                platform = db_platforms_by_slug.get(platform_slug)
                if platform:
                    export_success = await gamelist_exporter.export_platform_to_file(
                        platform.id,
                        request=None,
                    )
                    if export_success:
                        log.info(
                            f"Auto-exported gamelist.xml for platform {platform.name} after scan"
                        )
                    else:
                        log.warning(
                            f"Failed to auto-export gamelist.xml for platform {platform.name} after scan"
                        )
            log.info("Gamelist.xml auto-export completed.")

        if config.PEGASUS_AUTO_EXPORT_ON_SCAN:
            log.info("Auto-exporting metadata.pegasus.txt for all platforms...")
            pegasus_exporter = PegasusExporter(local_export=True)
            for platform_slug in platform_list:
                platform = db_platforms_by_slug.get(platform_slug)
                if platform:
                    export_success = await pegasus_exporter.export_platform_to_file(
                        platform.id,
                        request=None,
                    )
                    if export_success:
                        log.info(
                            f"Auto-exported metadata.pegasus.txt for platform {platform.name} after scan"
                        )
                    else:
                        log.warning(
                            f"Failed to auto-export metadata.pegasus.txt for platform {platform.name} after scan"
                        )
            log.info("Pegasus metadata auto-export completed.")

        await finish("scan:done", scan_stats.to_dict())
    except ScanStoppedException:
        await stop_scan()
    except Exception as e:
        log.error(f"Error in scan_platform: {e}")
        # Catch all exceptions and emit error to the client
        await finish("scan:done_ko", str(e))
        # Re-raise the exception to be caught by the error handler
        raise e

    return scan_stats


async def reject_unauthorized_scan(sid: str) -> bool:
    """Return ``True`` (and notify the caller) if the socket may not run scans.

    Scans are a privileged, destructive operation, so gate them on the same
    ``TASKS_RUN`` scope the REST task endpoints require, resolved from the
    server-side session (never from the client payload).
    """
    user = await get_authenticated_user(sid)
    if user is not None and Scope.TASKS_RUN in user.oauth_scopes:
        return False

    log.warning(f"{emoji.EMOJI_STOP_SIGN} Unauthorized scan request rejected")
    await socket_handler.socket_server.emit(
        "scan:done_ko",
        "You are not authorized to run scans",
        to=sid,
    )
    return True


@socket_handler.socket_server.on("scan")  # type: ignore
async def scan_handler(sid: str, options: dict[str, Any]):
    """Scan socket endpoint

    Args:
        options (dict): Socket options
    """

    if await reject_unauthorized_scan(sid):
        return

    platform_ids = options.get("platforms", [])
    platform_fs_slugs = options.get("platform_fs_slugs", [])
    scan_type = ScanType[options.get("type", "quick").upper()]
    roms_ids = options.get("roms_ids", [])

    # Pressing scan again after losing the progress socket would queue a second
    # pass over the library; a scan of named roms is not that, so it may queue.
    if not DEV_MODE and not roms_ids:
        running_job, queued_jobs = get_blocking_library_scans()
        if running_job is not None or queued_jobs:
            message = _scan_in_flight_message(running_job, queued_jobs)
            log.info(f"{emoji.EMOJI_STOP_SIGN} {message}, ignoring request")
            await socket_handler.socket_server.emit(
                "scan:done_ko",
                message,
                to=sid,
            )
            return

    log.info(f"{emoji.EMOJI_MAGNIFYING_GLASS_TILTED_RIGHT} Scanning")

    metadata_sources = options.get("apis", [])
    launchbox_remote_enabled = bool(options.get("launchbox_remote_enabled", True))
    playmatch_enabled = bool(options.get("playmatch_enabled", True))

    if DEV_MODE:
        return await scan_platforms(
            platform_ids=platform_ids,
            metadata_sources=metadata_sources,
            scan_type=scan_type,
            roms_ids=roms_ids,
            launchbox_remote_enabled=launchbox_remote_enabled,
            playmatch_enabled=playmatch_enabled,
            platform_fs_slugs=platform_fs_slugs,
        )

    return scan_queue.enqueue(
        scan_platforms,
        # A scan of named roms resolves its work from the database and is done
        # in seconds, so it goes ahead of any library scan already waiting.
        at_front=bool(roms_ids),
        on_failure=report_scan_failure,
        platform_ids=platform_ids,
        metadata_sources=metadata_sources,
        scan_type=scan_type,
        roms_ids=roms_ids,
        launchbox_remote_enabled=launchbox_remote_enabled,
        playmatch_enabled=playmatch_enabled,
        platform_fs_slugs=platform_fs_slugs,
        job_timeout=SCAN_TIMEOUT,  # Timeout (default of 4 hours)
        result_ttl=TASK_RESULT_TTL,
        meta=scan_job_meta(scan_type),
    )


@socket_handler.socket_server.on("scan:stop")  # type: ignore
async def stop_scan_handler(sid: str):
    """Stop scan socket endpoint"""

    if await reject_unauthorized_scan(sid):
        return

    log.info(f"{emoji.EMOJI_STOP_BUTTON} Stop scan requested...")

    # Queued scans have not started, so cancelling them is enough. They have to
    # go too: stopping only the running scan would hand the worker the next one.
    queued_jobs = get_queued_scan_jobs()
    scheduled_jobs = get_scheduled_scan_jobs()
    for job in queued_jobs + scheduled_jobs:
        cancel_job(job)

    # A running scan cannot be interrupted from here, it polls the stop flag
    # between platforms and ROMs and unwinds itself.
    running_job = get_running_scan_job()
    if running_job is not None:
        cancel_job(running_job)
        redis_client.set(STOP_SCAN_FLAG, 1)

    if running_job is None and not queued_jobs and not scheduled_jobs:
        log.info(f"{emoji.EMOJI_STOP_BUTTON} No running scan to stop")
        return

    log.info(
        f"{emoji.EMOJI_STOP_BUTTON} Stopping scan "
        f"({int(running_job is not None)} running, {len(queued_jobs)} queued, "
        f"{len(scheduled_jobs)} scheduled)"
    )
