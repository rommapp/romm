"""Convert each matched ROM to its platform's library format, in place."""

import asyncio
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from adapters.services.rom_converto import (
    Operation,
    RomConvertoError,
    RomConvertoOperationError,
    file_format,
    resolve_operation,
    rom_converto_service,
)
from config import SCAN_TIMEOUT
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.rom_conversion import STAGE_PREFIX
from handler.rom_files import refresh_rom_files
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom, RomFile, RomFileCategory
from tasks.scheduled.convert_images_to_webp import ConversionStats
from tasks.tasks import Task, TaskType
from utils.context import initialize_context

_CUE_FILE_LINE: Final = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))', re.IGNORECASE)
_PLAYLIST_EXT: Final = ".m3u"


@dataclass
class ConvertLibraryStats:
    converted: int = 0
    already_converted: int = 0
    # Converted files no longer hash-match a DAT, so only matched roms convert.
    unmatched: int = 0
    unsupported: int = 0
    failed: int = 0
    bytes_saved: int = 0


def _cue_tracks(cue: Path) -> list[Path]:
    """The track files a cue sheet references, all beside it."""
    tracks: list[Path] = []
    for line in cue.read_text(errors="replace").splitlines():
        match = _CUE_FILE_LINE.match(line)
        if match is None:
            continue
        name = match.group(1) or match.group(2)
        # A track outside the cue's folder isn't this rom's to delete.
        if Path(name).name != name:
            raise ValueError(f"{cue.name} references a track outside its folder")
        tracks.append(cue.with_name(name))
    return tracks


def _rewrite_playlists(folder: Path, renames: dict[str, str]) -> None:
    """Point each playlist entry for a converted file at its new name."""
    for playlist in folder.iterdir():
        if playlist.suffix.lower() != _PLAYLIST_EXT or not playlist.is_file():
            continue
        lines = playlist.read_text(errors="replace").splitlines()
        rewritten = [renames.get(line.strip(), line) for line in lines]
        if rewritten != lines:
            playlist.write_text("\n".join(rewritten) + "\n")


def _sources(src: Path, final: Path, input_ext: str) -> list[Path]:
    """The files a conversion of `src` replaces, refusing one that would overwrite."""
    if final.exists():
        raise FileExistsError(f"{final.name} already exists")
    return [src, *(_cue_tracks(src) if input_ext == ".cue" else [])]


def _publish(stage_dir: Path, final: Path) -> None:
    if [p.name for p in stage_dir.iterdir()] != [final.name]:
        raise RomConvertoOperationError(
            f"rom-converto did not write exactly {final.name}"
        )
    os.replace(stage_dir / final.name, final)


def _replace_sources(sources: list[Path], final: Path) -> int:
    """Delete the converted files and return the bytes the conversion saved."""
    saved = sum(p.stat().st_size for p in sources if p.exists()) - final.stat().st_size
    for path in sources:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log.warning(
                f"Converted to {hl(final.name)} but could not delete {path}: {exc}"
            )
    return saved


async def _convert_in_place(
    src: Path, operation: Operation, input_ext: str
) -> tuple[Path, int]:
    """Convert `src` beside itself, then delete it and any tracks it references.

    Raises only while the original is untouched.

    Returns:
        The converted file and the bytes the conversion saved.
    """
    final = src.with_name(operation.output_name(src, input_ext))
    sources = await asyncio.to_thread(_sources, src, final, input_ext)
    stage_dir = Path(
        await asyncio.to_thread(tempfile.mkdtemp, prefix=STAGE_PREFIX, dir=src.parent)
    )
    try:
        await rom_converto_service.convert(
            operation, src=src, out=stage_dir / final.name
        )
        await asyncio.to_thread(_publish, stage_dir, final)
    finally:
        await asyncio.to_thread(shutil.rmtree, stage_dir, True)
    return final, await asyncio.to_thread(_replace_sources, sources, final)


def _game_files(rom: Rom) -> list[RomFile]:
    return [
        f
        for f in rom.files
        if f.is_top_level
        and not f.missing_from_fs
        and f.category in (None, RomFileCategory.GAME)
    ]


class ConvertLibraryTask(Task):
    def __init__(self) -> None:
        super().__init__(
            title="Convert library",
            description=(
                "Convert each matched ROM to its platform's library format, "
                "replacing the original files"
            ),
            task_type=TaskType.CONVERSION,
            enabled=True,
            manual_run=True,
            cron_string=None,
            # One conversion after another, each up to ROM_CONVERTO_TIMEOUT.
            timeout=SCAN_TIMEOUT,
        )

    @staticmethod
    def _name_taken(rom: Rom, operation: Operation, input_ext: str) -> bool:
        """Whether another rom row already holds the name this rom converts to."""
        name = operation.output_name(Path(rom.fs_name), input_ext)
        taken = f"{rom.fs_path}/{name}" in db_rom_handler.get_roms_by_fs_name(
            rom.platform_id, [name]
        )
        if taken:
            log.warning(f"Not converting {hl(rom.fs_name)}: a rom named {name} exists")
        return taken

    async def _convert_rom(
        self, rom: Rom, target: str, stats: ConvertLibraryStats
    ) -> None:
        planned: list[tuple[RomFile, Operation, str]] = []
        for rom_file in _game_files(rom):
            if file_format(rom_file.file_name) == target:
                stats.already_converted += 1
                continue
            resolved = resolve_operation(
                rom.platform_slug, target, rom_file.file_name, lossless=True
            )
            if resolved is None:
                stats.unsupported += 1
                continue
            if rom.has_simple_single_file and self._name_taken(rom, *resolved):
                stats.failed += 1
                continue
            planned.append((rom_file, *resolved))
        if not planned:
            return
        if not rom.is_identified:
            stats.unmatched += 1
            return

        renames: dict[str, str] = {}
        for rom_file, operation, input_ext in planned:
            src = fs_rom_handler.validate_path(rom_file.full_path)
            try:
                final, saved = await _convert_in_place(src, operation, input_ext)
            except (RomConvertoError, OSError, ValueError) as exc:
                log.warning(f"Could not convert {hl(rom_file.file_name)}: {exc}")
                stats.failed += 1
                continue
            renames[src.name] = final.name
            stats.converted += 1
            stats.bytes_saved += saved
            log.info(f"Converted {hl(src.name)} to {hl(final.name)}")

        if not renames:
            return
        if rom.has_simple_single_file:
            db_rom_handler.update_rom(rom.id, {"fs_name": renames[rom.fs_name]})
        else:
            await asyncio.to_thread(
                _rewrite_playlists,
                fs_rom_handler.validate_path(rom.full_path),
                renames,
            )
        refreshed = db_rom_handler.get_rom(rom.id)
        if refreshed is not None:
            await refresh_rom_files(refreshed)

    @initialize_context()
    async def run(self, platform_id: int | None = None) -> dict[str, int]:
        """Convert every matched ROM on platforms that have a library format."""
        log.info(f"Starting {self.title} task...")
        stats = ConvertLibraryStats()
        if not await rom_converto_service.is_enabled():
            log.warning(f"{self.title} needs rom-converto; set ROM_CONVERTO_ENABLED")
            return asdict(stats)

        formats = cm.get_config().CONVERTO.platform_formats
        rom_ids: list[tuple[int, str]] = []
        for platform in db_platform_handler.get_platforms():
            if platform_id is not None and platform.id != platform_id:
                continue
            target = formats.get(platform.slug)
            if target:
                rom_ids.extend(
                    (rom.id, target)
                    for rom in db_rom_handler.get_roms_scalar(
                        platform_ids=[platform.id]
                    )
                )

        progress = ConversionStats()
        progress.update(total=len(rom_ids))
        for index, (rom_id, target) in enumerate(rom_ids):
            rom = db_rom_handler.get_rom(rom_id)
            if rom is not None:
                await self._convert_rom(rom, target, stats)
            progress.update(processed=index + 1, errors=stats.failed)

        log.info(
            f"{self.title} completed: {stats.converted} converted, "
            f"{stats.failed} failed, {stats.bytes_saved} bytes saved"
        )
        return asdict(stats)


convert_library_task = ConvertLibraryTask()
