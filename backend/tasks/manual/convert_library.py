"""Convert each matched ROM to its platform's library format, in place."""

import asyncio
import contextlib
import os
import re
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from sqlalchemy.exc import SQLAlchemyError

from adapters.services.rom_converto import (
    Operation,
    RomConvertoError,
    file_format,
    resolve_operation,
    rom_converto_service,
)
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.rom_conversion import STAGE_PREFIX
from handler.rom_files import refresh_rom_files
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom, RomFile, RomFileCategory
from tasks.registry import CONVERT_LIBRARY_SPEC
from tasks.scheduled.convert_images_to_webp import ConversionStats
from tasks.tasks import Task
from utils.context import initialize_context
from utils.filesystem import LINK_FALLBACK_ERRNOS

_CUE_FILE_LINE: Final = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))', re.IGNORECASE)
_CUE_EXT: Final = ".cue"
_PLAYLIST_EXT: Final = ".m3u"
_CONVERT_STAGE_PREFIX: Final = f"{STAGE_PREFIX}convert_"


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
    for line in cue.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = _CUE_FILE_LINE.match(line)
        if match is None:
            continue
        name = match.group(1) or match.group(2)
        # A track outside the cue's folder isn't this rom's to delete.
        if Path(name).name != name:
            raise ValueError(f"{cue.name} references a track outside its folder")
        tracks.append(cue.with_name(name))
    return tracks


def _shared_tracks(cue: Path, tracks: list[Path]) -> set[Path]:
    """The tracks of `cue` that another cue beside it also references."""
    others: set[Path] = set()
    for other in cue.parent.iterdir():
        if other == cue or other.suffix.lower() != _CUE_EXT or not other.is_file():
            continue
        with contextlib.suppress(OSError, ValueError):
            others.update(_cue_tracks(other))
    return set(tracks) & others


def _renamed_entry(line: str, renames: dict[str, str]) -> str:
    entry = line.strip()
    return renames.get(os.path.normpath(entry), line) if entry else line


def _rewritten_playlists(folder: Path, renames: dict[str, str]) -> dict[Path, str]:
    """The playlists in `folder` that name a renamed file, with their new text."""
    rewrites: dict[Path, str] = {}
    for playlist in folder.iterdir():
        if playlist.suffix.lower() != _PLAYLIST_EXT or not playlist.is_file():
            continue
        lines = playlist.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        rewritten = [_renamed_entry(line, renames) for line in lines]
        if rewritten != lines:
            rewrites[playlist] = "\n".join(rewritten) + "\n"
    return rewrites


async def _rewrite_playlists(folder: Path, renames: dict[str, str]) -> None:
    """Point each playlist entry for a converted file at its new name."""
    rewrites = await asyncio.to_thread(_rewritten_playlists, folder, renames)
    for playlist, text in rewrites.items():
        async with fs_rom_handler._atomic_write(playlist) as staged:
            await asyncio.to_thread(staged.write_text, text)


def _sources(src: Path, final: Path, input_ext: str) -> list[Path]:
    """The files a conversion of `src` replaces, refusing one that would overwrite."""
    if final.exists():
        raise FileExistsError(f"{final.name} already exists")
    if input_ext != _CUE_EXT:
        return [src]
    tracks = _cue_tracks(src)
    if shared := _shared_tracks(src, tracks):
        raise ValueError(
            f"{src.name} shares {sorted(p.name for p in shared)} with another cue"
        )
    return [src, *tracks]


def _drop_stale_stages(folder: Path) -> None:
    """Remove stage dirs a killed conversion left, none recent enough to be live."""
    cutoff = time.time() - CONVERT_LIBRARY_SPEC.timeout
    for stage in folder.glob(f"{_CONVERT_STAGE_PREFIX}*"):
        with contextlib.suppress(OSError):
            if stage.is_dir() and stage.stat().st_mtime < cutoff:
                shutil.rmtree(stage, ignore_errors=True)


def _publish(stage_dir: Path, final: Path) -> None:
    """Move the staged output to `final`, never replacing a file that appeared there."""
    staged = stage_dir / final.name
    try:
        os.link(staged, final)
    except OSError as exc:
        if exc.errno not in LINK_FALLBACK_ERRNOS:
            raise
        if final.exists():
            raise FileExistsError(f"{final.name} already exists") from None
        os.replace(staged, final)


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


async def _convert_beside(
    src: Path, final: Path, operation: Operation, stage_parent: Path
) -> None:
    """Convert `src` to `final` beside it, staging in `stage_parent` and leaving `src` in place."""
    stage_dir = Path(
        await asyncio.to_thread(
            tempfile.mkdtemp, prefix=_CONVERT_STAGE_PREFIX, dir=stage_parent
        )
    )
    try:
        await rom_converto_service.convert(
            operation, src=src, out=stage_dir / final.name
        )
        await asyncio.to_thread(_publish, stage_dir, final)
    finally:
        await asyncio.to_thread(shutil.rmtree, stage_dir, True)


def _names_taken(rom: Rom, names: list[str]) -> list[str]:
    """The `names` another rom row beside `rom` already holds."""
    if not names:
        return []
    owned = db_rom_handler.get_roms_by_fs_name(rom.platform_id, names)
    return sorted(n for n in names if f"{rom.fs_path}/{n}" in owned)


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
        super().__init__(CONVERT_LIBRARY_SPEC)

    async def _convert_rom(
        self, rom: Rom, target: str, stats: ConvertLibraryStats
    ) -> None:
        single_file = rom.has_simple_single_file
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
            name = resolved[0].output_name(Path(rom.fs_name), resolved[1])
            if single_file and _names_taken(rom, [name]):
                log.warning(
                    f"Not converting {hl(rom.fs_name)}: a rom named {name} exists"
                )
                stats.failed += 1
                continue
            planned.append((rom_file, *resolved))
        if not planned:
            return
        if not rom.is_identified:
            stats.unmatched += 1
            return

        # A rom folder lists dot-prefixed subfolders as its files, so stage beside it.
        stage_parent = fs_rom_handler.validate_path(rom.fs_path)
        await asyncio.to_thread(_drop_stale_stages, stage_parent)
        # Originals go only once the rom and its playlists point at the new files.
        published: list[tuple[Path, Path, list[Path]]] = []
        for rom_file, operation, input_ext in planned:
            src = fs_rom_handler.validate_path(rom_file.full_path)
            final = src.with_name(operation.output_name(src, input_ext))
            try:
                sources = await asyncio.to_thread(_sources, src, final, input_ext)
                if single_file and (
                    taken := _names_taken(rom, [t.name for t in sources[1:]])
                ):
                    raise ValueError(f"{taken} belong to other roms")
                await _convert_beside(src, final, operation, stage_parent)
            except (RomConvertoError, OSError, ValueError) as exc:
                log.warning(f"Could not convert {hl(rom_file.file_name)}: {exc}")
                stats.failed += 1
                continue
            published.append((src, final, sources))

        if not published:
            return
        renames = {src.name: final.name for src, final, _ in published}
        try:
            if single_file:
                db_rom_handler.update_rom(rom.id, {"fs_name": renames[rom.fs_name]})
            else:
                await _rewrite_playlists(
                    fs_rom_handler.validate_path(rom.full_path), renames
                )
        except (OSError, SQLAlchemyError) as exc:
            log.warning(f"Kept the originals of {hl(rom.fs_name)}: {exc}")
            stats.failed += len(published)
            if single_file:
                for _, final, _ in published:
                    final.unlink(missing_ok=True)
            return

        for src, final, sources in published:
            stats.bytes_saved += await asyncio.to_thread(
                _replace_sources, sources, final
            )
            stats.converted += 1
            log.info(f"Converted {hl(src.name)} to {hl(final.name)}")
        refreshed = db_rom_handler.get_rom(rom.id)
        if refreshed is not None:
            await refresh_rom_files(refreshed)

    @initialize_context()
    async def run(self, platform_id: int | None = None) -> dict[str, int]:
        """Convert every matched ROM on platforms that have a library format."""
        log.info(f"Starting {self.spec.title} task...")
        stats = ConvertLibraryStats()
        if not await rom_converto_service.is_enabled():
            log.warning(
                f"{self.spec.title} needs rom-converto; set ROM_CONVERTO_ENABLED"
            )
            return asdict(stats)

        formats = cm.get_config().CONVERTO.platform_formats
        rom_ids: list[tuple[int, str]] = []
        for platform in db_platform_handler.get_platforms():
            if platform_id is not None and platform.id != platform_id:
                continue
            target = formats.get(platform.slug)
            if target:
                rom_ids.extend(
                    (rom_id, target)
                    for rom_id in db_rom_handler.get_rom_ids(platform_ids=[platform.id])
                )

        progress = ConversionStats()
        progress.update(total=len(rom_ids))
        for index, (rom_id, target) in enumerate(rom_ids):
            rom = db_rom_handler.get_rom(rom_id)
            if rom is not None:
                try:
                    await self._convert_rom(rom, target, stats)
                except Exception as exc:
                    # One rom's failure must not stop the rest of the library.
                    log.exception(f"Could not convert {hl(rom.fs_name)}: {exc}")
                    stats.failed += 1
            progress.update(processed=index + 1, errors=stats.failed)

        log.info(
            f"{self.spec.title} completed: {stats.converted} converted, "
            f"{stats.failed} failed, {stats.bytes_saved} bytes saved"
        )
        return asdict(stats)


convert_library_task = ConvertLibraryTask()
