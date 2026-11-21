"""Convert each matched ROM to its platform's library format, in place."""

import asyncio
import contextlib
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from sqlalchemy.exc import SQLAlchemyError

from adapters.services.rom_converto import (
    CUE_EXT,
    Operation,
    RomConvertoError,
    RomConvertoUnsafeSourceError,
    cue_tracks,
    file_format,
    resolve_operation,
    rom_converto_service,
)
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler, db_snapshot_handler
from handler.filesystem import fs_rom_handler
from handler.rom_files import refresh_rom_files
from handler.snapshots.file_key import FileKey
from handler.snapshots.legacy import sync_file
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom, RomFile, RomFileCategory
from tasks.registry import CONVERT_LIBRARY_SPEC
from tasks.scheduled.convert_images_to_webp import ConversionStats
from tasks.tasks import Task
from utils.context import initialize_context
from utils.filesystem import LINK_FALLBACK_ERRNOS, TEMP_FILE_PREFIX

_PLAYLIST_EXT: Final = ".m3u"
_CONVERT_STAGE_PREFIX: Final = f"{TEMP_FILE_PREFIX}convert_"


@dataclass
class ConvertLibraryStats:
    converted: int = 0
    already_converted: int = 0
    # Converted files no longer hash-match a DAT, so only matched roms convert.
    unmatched: int = 0
    unsupported: int = 0
    failed: int = 0
    bytes_saved: int = 0


def _shared_tracks(cue: Path, tracks: list[Path]) -> set[Path]:
    """The tracks of `cue` that another cue beside it also references."""
    others: set[Path] = set()
    for other in cue.parent.iterdir():
        if other == cue or other.suffix.lower() != CUE_EXT or not other.is_file():
            continue
        with contextlib.suppress(OSError, RomConvertoUnsafeSourceError):
            others.update(cue_tracks(other))
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


async def _rewrite_playlists(
    folder: Path, renames: dict[str, str], originals: dict[Path, bytes]
) -> None:
    """Point each playlist entry for a converted file at its new name, keeping
    each playlist's bytes in `originals` before rewriting it."""
    rewrites = await asyncio.to_thread(_rewritten_playlists, folder, renames)
    for playlist, text in rewrites.items():
        original = await asyncio.to_thread(playlist.read_bytes)
        async with fs_rom_handler._atomic_write(playlist) as staged:
            await asyncio.to_thread(staged.write_text, text)
        originals[playlist] = original


def _sources(src: Path, final: Path, input_ext: str) -> list[Path]:
    """The files a conversion of `src` replaces, refusing one that would overwrite."""
    if final.exists():
        raise FileExistsError(f"{final.name} already exists")
    if input_ext != CUE_EXT:
        return [src]
    tracks = cue_tracks(src)
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


@dataclass(frozen=True)
class _Replacements:
    channels: dict[FileKey, tuple[FileKey, ...]]
    hashes: dict[str, str]
    file_ids: dict[int, int]


def _replacements(
    before: list[RomFile], after: list[RomFile], replaced: dict[Path, Path]
) -> _Replacements:
    """Pair each replaced file with its replacement, from the file rows a
    refresh made while both were on disk.

    Raises:
        FileNotFoundError: The refresh did not list every output.
    """
    validate = fs_rom_handler.cached_path_validator()
    by_path = {validate(f.full_path): f for f in after}
    outputs = set(replaced.values())
    if unlisted := sorted(p.name for p in outputs if p not in by_path):
        raise FileNotFoundError(f"the file refresh did not list {unlisted}")
    pairs = [
        (old, by_path[replaced[path]])
        for old in before
        if (path := validate(old.full_path)) in replaced
    ]
    channels: dict[FileKey, tuple[FileKey, ...]] = {
        old_key: (new_key,)
        for old, new in pairs
        if (old_key := FileKey.of_file(old)) != (new_key := FileKey.of_file(new))
    }
    # Clients look up a ROM's channels by its sync file. It is followed only to
    # a file this run wrote, since a disc that failed to convert is another disc.
    gone = {path for path, final in replaced.items() if path != final}
    old_sync = sync_file(before)
    new_sync = sync_file(f for f in after if validate(f.full_path) not in gone)
    if old_sync and new_sync and validate(new_sync.full_path) in outputs:
        old_key, new_key = FileKey.of_file(old_sync), FileKey.of_file(new_sync)
        if old_key in channels and new_key not in channels[old_key]:
            channels[old_key] = (new_key, *channels[old_key])
    return _Replacements(
        channels=channels,
        hashes={
            old.sha1_hash: new.sha1_hash
            for old, new in pairs
            if old.sha1_hash and new.sha1_hash and old.sha1_hash != new.sha1_hash
        },
        # A single-file ROM's old row is already gone, and a state without a
        # disc resumes on the start disc, its only one.
        file_ids={old.id: new.id for old, new in pairs if old.id != new.id},
    )


async def _move_to_outputs(rom: Rom, replaced: dict[Path, Path]) -> int:
    """Refresh the ROM's files while the originals are still on disk, then move
    its channels, snapshots and states onto the outputs.

    Returns:
        The number of channels moved.
    """
    refreshed = db_rom_handler.get_rom(rom.id)
    if refreshed is None:
        raise LookupError(f"rom {rom.id} is gone")
    # The ROM-level hashes wait for the refresh after the originals go.
    await refresh_rom_files(refreshed, rom_hashes=False)
    after = db_rom_handler.rom_files_for_rom_id(rom.id)
    moves = _replacements(rom.files, after, replaced)
    return db_snapshot_handler.move_to_replacements(
        rom.id, moves.channels, moves.hashes, moves.file_ids
    )


async def _restore(
    rom: Rom,
    published: list[tuple[Path, Path, list[Path]]],
    playlists: dict[Path, bytes],
    renamed: bool,
) -> None:
    """Put the ROM back on its originals, none of which were deleted yet, each
    step tried even when an earlier one fails."""
    if renamed:
        try:
            db_rom_handler.update_rom(rom.id, {"fs_name": rom.fs_name})
        except SQLAlchemyError as exc:
            log.warning(f"Could not point {hl(rom.fs_name)} back: {exc}")
    for playlist, data in playlists.items():
        try:
            async with fs_rom_handler._atomic_write(playlist) as staged:
                await asyncio.to_thread(staged.write_bytes, data)
        except OSError as exc:
            log.warning(f"Could not restore {playlist}: {exc}")
    for _, final, _ in published:
        try:
            final.unlink(missing_ok=True)
        except OSError as exc:
            log.warning(f"Could not remove {final}: {exc}")
    try:
        if refreshed := db_rom_handler.get_rom(rom.id):
            await refresh_rom_files(refreshed)
    except Exception as exc:
        log.warning(f"Could not refresh the files of {hl(rom.fs_name)}: {exc}")


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
        replaced = {path: final for _, final, sources in published for path in sources}
        playlists: dict[Path, bytes] = {}
        try:
            if single_file:
                db_rom_handler.update_rom(rom.id, {"fs_name": renames[rom.fs_name]})
            else:
                await _rewrite_playlists(
                    fs_rom_handler.validate_path(rom.full_path), renames, playlists
                )
                replaced.update((p, p) for p in playlists)
            moved = await _move_to_outputs(rom, replaced)
        except Exception as exc:
            log.warning(f"Kept the originals of {hl(rom.fs_name)}: {exc}")
            stats.failed += len(published)
            await _restore(rom, published, playlists, single_file)
            return

        for src, final, sources in published:
            stats.bytes_saved += await asyncio.to_thread(
                _replace_sources, sources, final
            )
            stats.converted += 1
            log.info(f"Converted {hl(src.name)} to {hl(final.name)}")
        if moved:
            log.info(f"Moved {moved} save channels of {hl(rom.fs_name)}")
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
                    log.exception(f"Could not convert {hl(rom.fs_name)}: {exc}")
                    stats.failed += 1
            progress.update(processed=index + 1, errors=stats.failed)

        log.info(
            f"{self.spec.title} completed: {stats.converted} converted, "
            f"{stats.failed} failed, {stats.bytes_saved} bytes saved"
        )
        return asdict(stats)


convert_library_task = ConvertLibraryTask()
