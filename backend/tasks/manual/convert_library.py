from dataclasses import dataclass

from adapters.services.rom_converto import rom_converto_service
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.database.base_handler import sync_session
from logger.logger import log
from tasks.tasks import Task, TaskType, update_job_meta
from utils.conversion_cache import TARGET_EXTENSIONS, get_or_convert
from utils.context import initialize_context


@dataclass
class ConvertLibraryStats:
    """Statistics for conversion cache pre-warming."""

    platform_id: int | None = None
    converted: int = 0
    skipped: int = 0
    failed: int = 0

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"conversion_stats": self.to_dict()})

    def to_dict(self) -> dict:
        return {
            "platform_id": self.platform_id,
            "converted": self.converted,
            "skipped": self.skipped,
            "failed": self.failed,
        }


class ConvertLibraryTask(Task):
    def __init__(self):
        super().__init__(
            title="Convert library to target formats",
            description="Pre-warm the conversion cache for ROMs covered by the per-platform format policy",
            task_type=TaskType.CONVERSION,
            enabled=True,
            manual_run=True,
            cron_string=None,
        )

    @initialize_context()
    async def run(self, platform_id: int | None = None) -> dict:
        """Pre-warm the conversion cache for every eligible single-file ROM."""
        log.info(f"Starting {self.title} task...")

        convertto = cm.get_config().CONVERTTO
        if not await rom_converto_service.is_enabled() or not convertto.platform_formats:
            log.info(
                "Conversion is not enabled or no platform formats configured, skipping"
            )
            return ConvertLibraryStats(platform_id=platform_id).to_dict()

        stats = ConvertLibraryStats(platform_id=platform_id)

        platforms = db_platform_handler.get_platforms()
        for platform in platforms:
            if platform_id is not None and platform.id != platform_id:
                continue
            target = convertto.platform_formats.get(platform.slug)
            if not target:
                continue

            with sync_session.begin() as session:
                roms = db_rom_handler.get_roms_scalar(
                    platform_ids=[platform.id], session=session
                )
                files_by_rom = db_rom_handler.get_files_for_roms(
                    [rom.id for rom in roms], session=session
                )
                candidates = []
                for rom in roms:
                    files = files_by_rom.get(rom.id, [])
                    # Equivalent of `has_simple_single_file` (exactly one file
                    # at the ROM root) without its deferred-column N+1.
                    if len(files) != 1 or files[0].file_path != rom.fs_path:
                        stats.update(skipped=stats.skipped + 1)
                        continue
                    rom_file = files[0]
                    # Skip pointless re-encodes of already-target-format files.
                    if (
                        f".{rom_file.file_extension.lower()}"
                        == TARGET_EXTENSIONS[target]
                    ):
                        stats.update(skipped=stats.skipped + 1)
                        continue
                    candidates.append((rom, rom_file))

            for rom, rom_file in candidates:
                log.info(
                    f"Pre-warming conversion of '{rom.fs_name}' [ID: {rom.id}] to {target}"
                )
                result = await get_or_convert(rom.id, rom_file, target)
                if result is None:
                    stats.update(failed=stats.failed + 1)
                else:
                    stats.update(converted=stats.converted + 1)

        log.info(
            f"{self.title} completed: {stats.converted} converted, "
            f"{stats.skipped} skipped, {stats.failed} failed"
        )
        return stats.to_dict()


convert_library_task = ConvertLibraryTask()
