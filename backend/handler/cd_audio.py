import asyncio
import ctypes
import dataclasses
import functools
import shutil
from collections import Counter
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from anyio import Path as AnyioPath

from handler.filesystem import fs_rom_handler
from handler.rom_conversion import promote_single_file_to_folder
from handler.rom_files import refresh_rom_files
from handler.rom_upload import (
    CATEGORY_UPLOAD_FOLDERS,
    UploadConflictException,
    move_into_place,
    prepare_upload_destination,
    staging_path,
)
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom, RomFile, RomFileCategory
from utils.chd_cdrom import (
    ChdAudioTrack,
    ChdError,
    ChdImage,
    audio_tracks,
    load_libchdr,
)
from utils.cue_sheet import (
    MAX_TRACKS,
    AudioTrackRange,
    audio_track_ranges,
    parse_cue_sheet,
)
from utils.gdi_sheet import gdi_audio_ranges, parse_gdi_sheet
from utils.m3u import disc_number

FLAC_BINARY = "flac"
READ_CHUNK_BYTES = 1024 * 1024
# A 74-minute disc encodes in well under a minute; this only catches a hang.
ENCODE_TIMEOUT_SECONDS = 600
# Sheets (.cue, Dreamcast .gdi) point at separate track files; a CHD holds them.
DISC_IMAGE_EXTENSIONS = (".cue", ".gdi", ".chd")
# A 99-track sheet with full CD-Text is a few tens of KiB.
MAX_SHEET_BYTES = 1024 * 1024

type PcmChunks = Generator[bytes]
# Each disc image's size and modification time, keyed by its path.
type DiscImageState = dict[tuple[str, str], tuple[int, float | None]]


class CdAudioUnavailableException(RuntimeError):
    """A tool the disc needs (flac, or libchdr for CHD) isn't installed."""


class CdAudioEncodeException(RuntimeError):
    """A track couldn't be read from its image or encoded."""


class CdAudioNeedsFolderException(RuntimeError):
    """The disc isn't in a folder of its own, so there is nowhere to write."""


@dataclass
class CdAudioExtraction:
    extracted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AudioSource:
    """One audio track ready to encode, wherever its samples live."""

    number: int
    big_endian: bool
    title: str | None
    performer: str | None
    pcm: Callable[[], PcmChunks]
    # Set only when the ROM holds more than one disc.
    disc: int | None = None


def track_file_name(prefix: str, number: int) -> str:
    return f"{prefix} - Track {number:02d}.flac"


def track_prefixes(images: list[Path]) -> dict[Path, str]:
    """Name each disc's tracks after its image, adding the image's folder when
    another disc of the set shares its name (Dreamcast sets often use disc.gdi)."""
    counts = Counter(image.stem.casefold() for image in images)
    return {
        image: (
            image.stem
            if counts[image.stem.casefold()] == 1
            else f"{image.parent.name} - {image.stem}"
        )
        for image in images
    }


def _read_sheet(path: Path) -> str:
    with path.open("rb") as sheet:
        raw = sheet.read(MAX_SHEET_BYTES + 1)
    if len(raw) > MAX_SHEET_BYTES:
        raise CdAudioEncodeException(f"{path.name} is too large to be a disc sheet")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _locate_files(folder: Path, names: set[str]) -> dict[str, Path]:
    """Match sheet file names to files in the sheet's folder, ignoring case."""
    entries = {entry.name: entry for entry in folder.iterdir() if entry.is_file()}
    by_folded = {name.casefold(): entry for name, entry in entries.items()}
    located: dict[str, Path] = {}
    for name in names:
        entry = entries.get(name) or by_folded.get(name.casefold())
        if entry is not None:
            located[name] = entry
    return located


def _bin_pcm(path: Path, offset: int, length: int) -> PcmChunks:
    with path.open("rb") as image:
        image.seek(offset)
        remaining = length
        while remaining > 0:
            chunk = image.read(min(READ_CHUNK_BYTES, remaining))
            if not chunk:
                return
            remaining -= len(chunk)
            yield chunk


def _chd_pcm(lib: ctypes.CDLL, path: Path, track: ChdAudioTrack) -> PcmChunks:
    # Hunks are small, so they're batched to keep the round trips down.
    pending: list[bytes] = []
    size = 0
    with ChdImage(lib, path) as image:
        for chunk in image.audio_pcm(track):
            pending.append(chunk)
            size += len(chunk)
            if size >= READ_CHUNK_BYTES:
                yield b"".join(pending)
                pending, size = [], 0
    if pending:
        yield b"".join(pending)


def _file_sizes(files: dict[str, Path]) -> dict[str, int]:
    return {name: path.stat().st_size for name, path in files.items()}


def _sheet_sources(sheet_path: Path) -> list[AudioSource]:
    text = _read_sheet(sheet_path)
    ranges: list[AudioTrackRange]
    if sheet_path.suffix.lower() == ".gdi":
        gdi_tracks = parse_gdi_sheet(text)
        located = _locate_files(sheet_path.parent, {t.file_name for t in gdi_tracks})
        ranges = gdi_audio_ranges(gdi_tracks, _file_sizes(located))
    else:
        cue_tracks = parse_cue_sheet(text)
        located = _locate_files(sheet_path.parent, {t.file_name for t in cue_tracks})
        # FILE names differing only in case open one file, so they share its
        # layout rather than each spanning the whole of it.
        cue_tracks = [
            (
                dataclasses.replace(track, file_name=located[track.file_name].name)
                if track.file_name in located
                else track
            )
            for track in cue_tracks
        ]
        located = {path.name: path for path in located.values()}
        ranges = audio_track_ranges(cue_tracks, _file_sizes(located))
    sources: list[AudioSource] = []
    # Lines pointing at the same samples would write the same audio again.
    seen: set[tuple[Path, int]] = set()
    for track in ranges:
        path = located[track.file_name]
        key = (path.resolve(), track.offset)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            AudioSource(
                number=track.number,
                big_endian=track.big_endian,
                title=track.title,
                performer=track.performer,
                pcm=functools.partial(_bin_pcm, path, track.offset, track.length),
            )
        )
    return sources


def _chd_sources(lib: ctypes.CDLL, chd_path: Path) -> list[AudioSource]:
    with ChdImage(lib, chd_path) as image:
        tracks = audio_tracks(image.tracks())
    # CHD stores CD audio big-endian and carries no CD-Text.
    return [
        AudioSource(
            number=track.number,
            big_endian=True,
            title=None,
            performer=None,
            pcm=functools.partial(_chd_pcm, lib, chd_path, track),
        )
        for track in tracks
    ]


def _encode_args(source: AudioSource, album: str | None, output: Path) -> list[str]:
    title = f"Track {source.number:02d}"
    if source.disc:
        title += f" (Disc {source.disc})"
    tags = {
        "TITLE": source.title or title,
        "TRACKNUMBER": str(source.number),
        "DISCNUMBER": str(source.disc) if source.disc else None,
        "ALBUM": album,
        "ARTIST": source.performer,
    }
    return [
        FLAC_BINARY,
        "--silent",
        "--force-raw-format",
        f"--endian={'big' if source.big_endian else 'little'}",
        "--sign=signed",
        "--channels=2",
        "--bps=16",
        "--sample-rate=44100",
        *(f"--tag={key}={value}" for key, value in tags.items() if value),
        "-o",
        str(output),
        "-",
    ]


async def _next_chunk(pcm: PcmChunks) -> bytes | None:
    read = asyncio.ensure_future(asyncio.to_thread(next, pcm, None))
    try:
        return await asyncio.shield(read)
    except asyncio.CancelledError:
        # The thread can't be interrupted, and closing a generator mid-read fails.
        await asyncio.wait([read])
        raise


async def _feed(stdin: asyncio.StreamWriter, pcm: PcmChunks) -> None:
    try:
        while (chunk := await _next_chunk(pcm)) is not None:
            stdin.write(chunk)
            await stdin.drain()
    finally:
        pcm.close()
    stdin.close()
    await stdin.wait_closed()


async def encode_track(source: AudioSource, output: Path, album: str | None) -> None:
    """Encode one track's samples straight from the disc image into a FLAC file.

    Raises:
        CdAudioEncodeException: The image couldn't be read, or flac failed.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *_encode_args(source, album, output),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, ValueError) as exc:
        raise CdAudioEncodeException(
            f"Could not start flac for track {source.number}"
        ) from exc
    assert process.stdin is not None and process.stderr is not None
    try:
        await asyncio.wait_for(
            _feed(process.stdin, source.pcm()), ENCODE_TIMEOUT_SECONDS
        )
        stderr = await asyncio.wait_for(process.stderr.read(), ENCODE_TIMEOUT_SECONDS)
        await process.wait()
    except BaseException as exc:
        # Cancellation included, so no encoder or half-written file outlives it.
        if process.returncode is None:
            process.kill()
        await process.wait()
        await AnyioPath(output).unlink(missing_ok=True)
        if isinstance(exc, Exception):
            raise CdAudioEncodeException(
                f"flac failed on track {source.number}"
            ) from exc
        raise
    if process.returncode != 0:
        await AnyioPath(output).unlink(missing_ok=True)
        raise CdAudioEncodeException(
            stderr.decode(errors="replace").strip()
            or f"flac exited with {process.returncode}"
        )


def encoder_available() -> bool:
    return shutil.which(FLAC_BINARY) is not None


def _is_disc_image(file: RomFile) -> bool:
    return file.category in (
        None,
        RomFileCategory.GAME,
    ) and file.file_name.lower().endswith(DISC_IMAGE_EXTENSIONS)


def disc_image_state(files: Iterable[RomFile]) -> DiscImageState:
    return {
        (file.file_path, file.file_name): (file.file_size_bytes, file.last_modified)
        for file in files
        if _is_disc_image(file)
    }


def disc_images_changed(before: DiscImageState, after: DiscImageState) -> bool:
    """Whether a disc image appeared or changed between two states."""
    return any(before.get(key) != state for key, state in after.items())


def _discs(rom: Rom) -> list[list[RomFile]]:
    """A ROM's disc images, grouped per disc: a sheet and a CHD of the same name
    in one folder are one disc in two formats, sheet first for its CD-Text."""
    discs: dict[tuple[str, str], list[RomFile]] = {}
    for file in rom.files:
        if _is_disc_image(file):
            key = (file.file_path, Path(file.file_name).stem.casefold())
            discs.setdefault(key, []).append(file)
    for images in discs.values():
        images.sort(
            key=lambda f: DISC_IMAGE_EXTENSIONS.index(Path(f.file_name).suffix.lower())
        )
    return list(discs.values())


@dataclass(frozen=True)
class PlannedTrack:
    """An audio track and the soundtrack file it's extracted into."""

    file_name: str
    source: AudioSource


def _disc_sources(images: list[RomFile], lib: ctypes.CDLL | None) -> list[AudioSource]:
    """The audio tracks of the first of a disc's images that has any, so a sheet
    whose track files are gone falls back to the CHD beside it."""
    sources: list[AudioSource] = []
    for image in images:
        path = fs_rom_handler.validate_path(image.full_path)
        try:
            if path.suffix.lower() != ".chd":
                sources = _sheet_sources(path)
            elif lib is None:
                raise CdAudioUnavailableException(
                    "Reading CHD images needs libchdr, which is not installed"
                )
            else:
                sources = _chd_sources(lib, path)
        except (ChdError, OSError) as exc:
            raise CdAudioEncodeException(f"Could not read {path.name}") from exc
        if sources:
            break
    # Track numbers name the output files, so each is taken once, within the
    # range a real disc can hold.
    by_number: dict[int, AudioSource] = {}
    for source in sources:
        if 1 <= source.number <= MAX_TRACKS:
            by_number.setdefault(source.number, source)
    return list(by_number.values())


def _plan_tracks(
    discs: list[list[RomFile]], lib: ctypes.CDLL | None
) -> list[PlannedTrack]:
    """Read each disc's audio track layout, without touching its samples.

    Raises:
        CdAudioUnavailableException: A disc needs libchdr, which isn't installed.
        CdAudioEncodeException: A disc image couldn't be read.
    """
    # Numbered discs first and in order, then the rest by path.
    discs = sorted(
        discs,
        key=lambda d: (
            disc_number(d[0]) is None,
            disc_number(d[0]) or 0,
            d[0].file_path,
            Path(d[0].file_name).stem.casefold(),
        ),
    )
    # Every image of a disc shares its folder and name, so the first names it.
    paths = [fs_rom_handler.validate_path(images[0].full_path) for images in discs]
    prefixes = track_prefixes(paths)
    multi_disc = len(discs) > 1
    planned: list[PlannedTrack] = []
    for position, (images, path) in enumerate(zip(discs, paths, strict=True), 1):
        disc = (disc_number(images[0]) or position) if multi_disc else None
        planned.extend(
            PlannedTrack(
                file_name=track_file_name(prefixes[path], source.number),
                source=dataclasses.replace(source, disc=disc),
            )
            for source in _disc_sources(images, lib)
        )
    return planned


def _lone_sheet(rom: Rom, discs: list[list[RomFile]]) -> bool:
    # A CHD is self-contained, but a lone sheet would leave its tracks behind.
    first = discs[0][0].file_name.lower()
    return rom.has_simple_single_file and not first.endswith(".chd")


async def extract_cd_audio(rom: Rom) -> CdAudioExtraction:
    """Write the audio tracks of a ROM's disc images (.cue, .gdi, .chd) into its
    soundtrack folder.

    Tracks already extracted are left as they are, so the call can be repeated.

    Raises:
        CdAudioUnavailableException: flac, or libchdr for a CHD, isn't installed.
        CdAudioNeedsFolderException: A sheet sits loose in the platform folder.
        RomListedByPlaylistException: A lone CHD an .m3u lists can't be moved
            into a folder.
        CdAudioEncodeException: A track couldn't be encoded.
        UploadRejectedException: A track's file name can't go in the soundtrack
            folder, such as one the scanner excludes.
    """
    if not encoder_available():
        raise CdAudioUnavailableException("The flac encoder is not installed")

    result = CdAudioExtraction()
    discs = _discs(rom)
    if not discs:
        return result

    lib = load_libchdr()
    if _lone_sheet(rom, discs):
        raise CdAudioNeedsFolderException(
            "Move the disc into a folder of its own to extract its audio"
        )
    planned = await asyncio.to_thread(_plan_tracks, discs, lib)
    # Nothing to write, so a lone disc stays where it is.
    if not planned:
        return result

    if rom.has_simple_single_file:
        rom = await promote_single_file_to_folder(rom)
        planned = await asyncio.to_thread(_plan_tracks, _discs(rom), lib)

    try:
        await _write_tracks(rom, planned, result)
    finally:
        # Register whatever landed, even when a later track failed.
        if result.extracted:
            await _register(rom, result)
    return result


async def _write_tracks(
    rom: Rom, planned: list[PlannedTrack], result: CdAudioExtraction
) -> None:
    folder = CATEGORY_UPLOAD_FOLDERS[RomFileCategory.SOUNDTRACK]
    for track in planned:
        try:
            destination = await prepare_upload_destination(rom, folder, track.file_name)
        except UploadConflictException:
            result.skipped.append(track.file_name)
            continue
        staged = staging_path(destination.location)
        await encode_track(track.source, staged, rom.name)
        try:
            await asyncio.to_thread(
                move_into_place, destination.location, staged, overwrite=False
            )
        except UploadConflictException:
            # A concurrent extraction of the same disc got there first.
            result.skipped.append(track.file_name)
            continue
        result.extracted.append(track.file_name)


async def _register(rom: Rom, result: CdAudioExtraction) -> None:
    try:
        await refresh_rom_files(rom)
    except Exception as exc:
        # Kept from replacing the error that stopped the run; the tracks are on
        # disk, so the next scan registers them.
        log.error(f"Could not register the CD audio of ROM {rom.id}", exc_info=exc)
        return
    log.info(
        f"Extracted {len(result.extracted)} CD audio tracks from {hl(rom.fs_name)}"
    )
