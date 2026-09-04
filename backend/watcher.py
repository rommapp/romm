import enum
import fnmatch
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import sentry_sdk
from opentelemetry import trace

from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    LIBRARY_BASE_PATH,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    SCAN_TIMEOUT,
    SENTRY_DSN,
    TASK_RESULT_TTL,
)
from config.config_manager import config_manager as cm
from endpoints.sockets.scan import report_scan_failure, scan_job_meta, scan_platforms
from handler.database import db_platform_handler
from handler.metadata import (
    meta_csdb_handler,
    meta_demozoo_handler,
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_libretro_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_pouet_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_steam_handler,
    meta_tgdb_handler,
)
from handler.redis_handler import get_job_kwargs, scan_queue
from handler.scan_handler import MetadataSource, ScanType
from handler.scan_jobs import get_pending_scan_jobs
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from utils import get_version

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)
tracer = trace.get_tracer(__name__)


@enum.unique
class EventType(enum.StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


VALID_EVENTS = frozenset(
    (
        EventType.ADDED,
        EventType.DELETED,
    )
)

# A change is a tuple representing a file change, first element is the event type, second is the
# path of the file or directory that changed.
Change = tuple[EventType, str]


@dataclass(frozen=True)
class PendingScanCoverage:
    """What the scans already in flight cover, so a rescan is not duplicated."""

    full_library: int
    platform_ids: frozenset[int]
    platform_fs_slugs: frozenset[str]


def get_pending_scan_coverage() -> PendingScanCoverage:
    """Summarise what the scans waiting to run already cover.

    Returns:
        PendingScanCoverage: How many pending scans cover the whole library, and
            the platforms and folders the rest are scoped to.
    """
    full_library = 0
    platform_ids: set[int] = set()
    platform_fs_slugs: set[str] = set()

    for job in get_pending_scan_jobs():
        kwargs = get_job_kwargs(job)
        if kwargs is None:
            # Nothing is known about what an unreadable scan covers, and a
            # duplicate scan costs less than a rescan that never happens.
            continue

        # A scan of named roms resolves them from the database and never walks
        # the filesystem, so it covers no change on disk, not even one under the
        # platform it names.
        if kwargs.get("roms_ids"):
            continue

        # Scans are enqueued with keywords only. A task-driven scan names no
        # scope at all, and covers everything.
        job_platform_ids = kwargs.get("platform_ids") or []
        job_platform_fs_slugs = kwargs.get("platform_fs_slugs") or []
        if not (job_platform_ids or job_platform_fs_slugs):
            full_library += 1
            continue

        platform_ids.update(job_platform_ids)
        platform_fs_slugs.update(job_platform_fs_slugs)

    return PendingScanCoverage(
        full_library=full_library,
        platform_ids=frozenset(platform_ids),
        platform_fs_slugs=frozenset(platform_fs_slugs),
    )


def process_changes(changes: Sequence[Change]) -> None:
    if not ENABLE_RESCAN_ON_FILESYSTEM_CHANGE:
        return

    # Filter for valid events, applying the same exclusion rules as the scanner:
    # exact-match and fnmatch patterns for files, plus excluded directory names
    # checked against every path component so events inside excluded dirs are ignored.
    cnfg = cm.get_config()
    structure_level = 1 if cnfg.has_structure_path_b else 2
    excluded_patterns = (
        cnfg.EXCLUDED_SINGLE_FILES
        + cnfg.EXCLUDED_MULTI_FILES
        + cnfg.EXCLUDED_MULTI_PARTS_FILES
    )

    def _is_excluded(path: str) -> bool:
        parts = path.strip("/").split("/")
        for part in parts:
            if part.startswith(".romm_tmp_"):
                return True
            if any(
                part == pat or fnmatch.fnmatch(part, pat) for pat in excluded_patterns
            ):
                return True
        return False

    changes = [
        change
        for change in changes
        if change[0] in VALID_EVENTS
        and not _is_excluded(os.fsdecode(change[1]).split(LIBRARY_BASE_PATH)[-1])
    ]
    if not changes:
        return

    with tracer.start_as_current_span("process_changes"):
        # Find affected platform slugs
        fs_slugs: set[str] = set()
        changes_platform_directory = False
        for change in changes:
            event_type, change_path = change
            src_path = os.fsdecode(change_path)
            event_src = src_path.split(LIBRARY_BASE_PATH)[-1]
            event_src_parts = event_src.split("/")
            if len(event_src_parts) <= structure_level:
                log.warning(
                    f"Filesystem event path '{event_src}' does not have enough segments for structure_level {structure_level}. Skipping event."
                )
                continue

            if len(event_src_parts) == structure_level + 1:
                changes_platform_directory = True

            log.info(f"Filesystem event: {event_type} {event_src}")
            fs_slugs.add(event_src_parts[structure_level])

        if not fs_slugs:
            log.info("No valid filesystem slugs found in changes, exiting...")
            return

        # Check whether any metadata source is enabled
        source_mapping: dict[str, bool] = {
            MetadataSource.IGDB: meta_igdb_handler.is_enabled(),
            MetadataSource.SS: meta_ss_handler.is_enabled(),
            MetadataSource.MOBY: meta_moby_handler.is_enabled(),
            MetadataSource.RA: meta_ra_handler.is_enabled(),
            MetadataSource.LAUNCHBOX: meta_launchbox_handler.is_enabled(),
            MetadataSource.HASHEOUS: meta_hasheous_handler.is_enabled(),
            MetadataSource.PLAYMATCH: meta_playmatch_handler.is_enabled(),
            MetadataSource.SGDB: meta_sgdb_handler.is_enabled(),
            MetadataSource.FLASHPOINT: meta_flashpoint_handler.is_enabled(),
            MetadataSource.HLTB: meta_hltb_handler.is_enabled(),
            MetadataSource.DEMOZOO: meta_demozoo_handler.is_enabled(),
            MetadataSource.POUET: meta_pouet_handler.is_enabled(),
            MetadataSource.CSDB: meta_csdb_handler.is_enabled(),
            MetadataSource.STEAM: meta_steam_handler.is_enabled(),
            MetadataSource.TGDB: meta_tgdb_handler.is_enabled(),
            MetadataSource.LIBRETRO: meta_libretro_handler.is_enabled(),
        }
        metadata_sources = [source for source, flag in source_mapping.items() if flag]
        if not metadata_sources:
            log.warning("No metadata sources enabled, skipping rescan")
            return

        pending = get_pending_scan_coverage()
        if pending.full_library:
            log.info(f"Full rescan already pending ({pending.full_library} job(s))")
            return

        time_delta = timedelta(minutes=RESCAN_ON_FILESYSTEM_CHANGE_DELAY)
        rescan_in_msg = f"rescanning in {hl(str(RESCAN_ON_FILESYSTEM_CHANGE_DELAY), color=CYAN)} minutes."

        def schedule_rescan(platform_ids: list[int], scan_type: ScanType) -> None:
            scan_queue.enqueue_in(
                time_delta,
                scan_platforms,
                platform_ids=platform_ids,
                metadata_sources=metadata_sources,
                scan_type=scan_type,
                on_failure=report_scan_failure,
                job_timeout=SCAN_TIMEOUT,
                result_ttl=TASK_RESULT_TTL,
                meta=scan_job_meta(scan_type),
            )

        # Any change to a platform directory should trigger a full rescan
        if changes_platform_directory:
            log.info(f"Platform directory changed, {rescan_in_msg}")
            schedule_rescan([], ScanType.UPDATE)
            return

        # Otherwise, process each platform slug
        for fs_slug in fs_slugs:
            # TODO: Query platforms from the database in bulk
            db_platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if not db_platform:
                continue

            if (
                db_platform.id in pending.platform_ids
                or fs_slug in pending.platform_fs_slugs
            ):
                log.info(f"Scan already pending for {hl(fs_slug)}")
                continue

            log.info(f"Change detected in {hl(fs_slug)} folder, {rescan_in_msg}")
            schedule_rescan([db_platform.id], ScanType.QUICK)


if __name__ == "__main__":
    changes = cast(list[Change], json.loads(os.getenv("WATCHFILES_CHANGES", "[]")))
    if changes:
        process_changes(changes)
