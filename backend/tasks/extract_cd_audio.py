"""Extracting CD audio in the background once a scan ends, when config.yml asks."""

from collections.abc import Sequence
from typing import Final

from rq import get_current_job
from rq.job import Job

from handler.cd_audio import (
    DISC_IMAGE_EXTENSIONS,
    CdAudioUnavailableException,
    cd_audio_status,
    extract_cd_audio,
    flac_available,
)
from handler.database import db_rom_handler
from handler.redis_handler import low_prio_queue
from handler.scan_jobs import get_running_scan_job
from logger.formatter import highlight as hl
from logger.logger import log

# A job cut short keeps the tracks it wrote, and the next scan queues the rest.
EXTRACTION_TIMEOUT_SECONDS: Final = 4 * 60 * 60


async def extract_cd_audio_after_scan(rom_ids: list[int]) -> None:
    """Extract the CD audio tracks the given ROMs' soundtracks are missing."""
    if not flac_available():
        log.warning("Skipping CD audio extraction: the flac encoder is not installed")
        return

    for rom_id in rom_ids:
        # Moving a lone CHD into a folder mid-scan would get it marked missing,
        # and the scan queues a job of its own when it ends.
        if get_running_scan_job() is not None:
            log.info("A scan started, so CD audio extraction waits for it to end")
            return

        rom = db_rom_handler.get_rom(rom_id)
        if rom is None or rom.missing_from_fs:
            continue

        try:
            status = await cd_audio_status(rom)
            if not status.extractable or status.extracted >= status.tracks:
                continue
            await extract_cd_audio(rom)
        except CdAudioUnavailableException as exc:
            log.warning(f"Skipping CD audio of {hl(rom.fs_name)}: {exc}")
        except Exception as exc:
            log.error(f"Error extracting CD audio of {hl(rom.fs_name)}", exc_info=exc)


def queue_cd_audio_extraction(
    *, platform_ids: Sequence[int] = (), rom_ids: Sequence[int] = ()
) -> Job | None:
    """Queue extraction for the disc images on `platform_ids` or among `rom_ids`.

    Returns:
        The queued job, or None when no ROM there has a disc image.
    """
    candidates = db_rom_handler.get_rom_ids_with_game_files_ending(
        DISC_IMAGE_EXTENSIONS, platform_ids=platform_ids, rom_ids=rom_ids
    )
    if not candidates:
        return None

    log.info(f"Queueing CD audio extraction for {hl(str(len(candidates)))} roms")
    return low_prio_queue.enqueue(
        extract_cd_audio_after_scan,
        kwargs={"rom_ids": candidates},
        job_timeout=EXTRACTION_TIMEOUT_SECONDS,
        result_ttl=0,
        meta={"task_name": "CD audio extraction"},
        # Held until the queueing scan finishes, since it would otherwise read as
        # a scan still running and stop the extraction.
        depends_on=get_current_job(),
    )
