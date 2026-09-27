from dataclasses import asdict, dataclass

from adapters.services.rom_converto import resolve_operation, rom_converto_service
from config import SCAN_TIMEOUT
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.database.base_handler import sync_session
from logger.logger import log
from models.rom import RomFile
from tasks.scheduled.convert_images_to_webp import ConversionStats
from tasks.tasks import Task, TaskType
from utils.context import initialize_context
from utils.conversion_cache import get_or_convert, has_room_for


@dataclass
class ConvertLibraryStats:
    platform_id: int | None = None
    converted: int = 0
    skipped: int = 0
    failed: int = 0


class ConvertLibraryTask(Task):
    def __init__(self) -> None:
        super().__init__(
            title="Convert library to target formats",
            description="Pre-warm the conversion cache for ROMs covered by the per-platform format policy",
            task_type=TaskType.CONVERSION,
            enabled=True,
            manual_run=True,
            cron_string=None,
            # One conversion after another, each up to ROM_CONVERTO_TIMEOUT.
            timeout=SCAN_TIMEOUT,
        )

    @initialize_context()
    async def run(self, platform_id: int | None = None) -> dict[str, int | None]:
        """Pre-warm the conversion cache for every eligible single-file ROM."""
        log.info(f"Starting {self.title} task...")

        stats = ConvertLibraryStats(platform_id=platform_id)
        converto = cm.get_config().CONVERTO
        if (
            not converto.download_conversion_enabled
            or not converto.platform_formats
            or not await rom_converto_service.is_enabled()
        ):
            log.info(
                "Download conversion is not enabled or no platform formats "
                "configured, skipping"
            )
            return asdict(stats)

        # (rom id, rom fs name, file, platform slug, target)
        candidates: list[tuple[int, str, RomFile, str, str]] = []
        for platform in db_platform_handler.get_platforms():
            if platform_id is not None and platform.id != platform_id:
                continue
            target = converto.platform_formats.get(platform.slug)
            if not target:
                continue

            with sync_session.begin() as session:
                roms = db_rom_handler.get_roms_scalar(
                    platform_ids=[platform.id], session=session
                )
                files_by_rom = db_rom_handler.get_files_for_roms(
                    [rom.id for rom in roms], session=session
                )
                for rom in roms:
                    files = files_by_rom.get(rom.id, [])
                    # Equivalent of `has_simple_single_file` (exactly one file
                    # at the ROM root) without its deferred-column N+1.
                    if (
                        len(files) != 1
                        or files[0].file_path != rom.fs_path
                        or resolve_operation(platform.slug, target, files[0].file_name)
                        is None
                    ):
                        stats.skipped += 1
                        continue
                    candidates.append(
                        (rom.id, rom.fs_name, files[0], platform.slug, target)
                    )

        progress = ConversionStats()
        progress.update(total=len(candidates))
        for index, (rom_id, fs_name, rom_file, slug, target) in enumerate(candidates):
            if not has_room_for(rom_file.file_size_bytes or 0):
                log.warning(
                    "Conversion cache is full, stopping the pre-warm; raise "
                    "ROM_CONVERTO_CACHE_MAX_SIZE_GB to convert more"
                )
                stats.skipped += len(candidates) - index
                return self._finish(stats)
            log.info(
                f"Pre-warming conversion of '{fs_name}' [ID: {rom_id}] to {target}"
            )
            result = await get_or_convert(rom_id, rom_file, slug, target)
            if result is None:
                stats.failed += 1
            else:
                stats.converted += 1
            progress.update(processed=index + 1, errors=stats.failed)

        return self._finish(stats)

    def _finish(self, stats: ConvertLibraryStats) -> dict[str, int | None]:
        log.info(
            f"{self.title} completed: {stats.converted} converted, "
            f"{stats.skipped} skipped, {stats.failed} failed"
        )
        return asdict(stats)


convert_library_task = ConvertLibraryTask()
