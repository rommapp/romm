import asyncio
import ctypes
import dataclasses
import functools
import shutil
from collections import Counter
from collections.abc import Callable, Generator
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
from utils.cue_sheet import AudioTrackRange, audio_track_ranges, parse_cue_sheet
from utils.gdi_sheet import gdi_audio_ranges, parse_gdi_sheet
from utils.m3u import disc_number, listing_playlist

FLAC_BINARY = "flac"
READ_CHUNK_BYTES = 1024 * 1024
# A 74-minute disc encodes in well under a minute; this only catches a hang.
ENCODE_TIMEOUT_SECONDS = 600
# Sheets (.cue, Dreamcast .gdi) point at separate track files; a CHD holds them.
DISC_IMAGE_EXTENSIONS = (".cue", ".gdi", ".chd")

PcmChunks = Generator[bytes, None, None]


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
    raw = path.read_bytes()
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
        ranges = audio_track_ranges(cue_tracks, _file_sizes(located))
    return [
        AudioSource(
            number=track.number,
            big_endian=track.big_endian,
            title=track.title,
            performer=track.performer,
            pcm=functools.partial(
                _bin_pcm, located[track.file_name], track.offset, track.length
            ),
        )
        for track in ranges
    ]


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
    process = await asyncio.create_subprocess_exec(
        *_encode_args(source, album, output),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
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


def _disc_images(rom: Rom) -> list[RomFile]:
    """One image per disc: a sheet and a CHD of the same name in one folder are
    the same disc, and the sheet wins since it can carry CD-Text."""
    images = sorted(
        (
            file
            for file in rom.files
            if file.category in (None, RomFileCategory.GAME)
            and file.file_name.lower().endswith(DISC_IMAGE_EXTENSIONS)
        ),
        key=lambda f: DISC_IMAGE_EXTENSIONS.index(Path(f.file_name).suffix.lower()),
    )
    distinct: dict[tuple[str, str], RomFile] = {}
    for image in images:
        key = (image.file_path, Path(image.file_name).stem.casefold())
        distinct.setdefault(key, image)
    return list(distinct.values())


@dataclass(frozen=True)
class PlannedTrack:
    """An audio track and the soundtrack file it's extracted into."""

    file_name: str
    source: AudioSource


@dataclass(frozen=True)
class CdAudioStatus:
    tracks: int
    extracted: int


def _require_libchdr(images: list[RomFile]) -> ctypes.CDLL | None:
    lib = load_libchdr()
    if lib is None and any(i.file_name.lower().endswith(".chd") for i in images):
        raise CdAudioUnavailableException(
            "Reading CHD images needs libchdr, which is not installed"
        )
    return lib


def _plan_tracks(images: list[RomFile], lib: ctypes.CDLL | None) -> list[PlannedTrack]:
    """Read each disc's audio track layout, without touching its samples.

    Raises:
        CdAudioEncodeException: A disc image couldn't be read.
    """
    # Numbered discs first and in order, then the rest by path.
    images = sorted(
        images,
        key=lambda f: (disc_number(f) is None, disc_number(f) or 0, f.full_path),
    )
    paths = [fs_rom_handler.validate_path(image.full_path) for image in images]
    prefixes = track_prefixes(paths)
    multi_disc = len(images) > 1
    planned: list[PlannedTrack] = []
    for position, (image, path) in enumerate(zip(images, paths, strict=True), 1):
        try:
            if path.suffix.lower() == ".chd":
                assert lib is not None
                sources = _chd_sources(lib, path)
            else:
                sources = _sheet_sources(path)
        except (ChdError, OSError) as exc:
            raise CdAudioEncodeException(f"Could not read {path.name}") from exc
        disc = (disc_number(image) or position) if multi_disc else None
        planned.extend(
            PlannedTrack(
                file_name=track_file_name(prefixes[path], source.number),
                source=dataclasses.replace(source, disc=disc),
            )
            for source in sources
        )
    return planned


async def cd_audio_status(rom: Rom) -> CdAudioStatus:
    """Count a ROM's CD audio tracks and how many are already in its soundtrack.

    Raises:
        CdAudioUnavailableException: libchdr is needed for a CHD but not installed.
        CdAudioEncodeException: A disc image couldn't be read.
    """
    images = _disc_images(rom)
    if not images:
        return CdAudioStatus(tracks=0, extracted=0)
    planned = await asyncio.to_thread(_plan_tracks, images, _require_libchdr(images))
    soundtrack = {
        file.file_name
        for file in rom.files
        if file.category == RomFileCategory.SOUNDTRACK
    }
    return CdAudioStatus(
        tracks=len(planned),
        extracted=sum(track.file_name in soundtrack for track in planned),
    )


async def extract_cd_audio(rom: Rom) -> CdAudioExtraction:
    """Write the audio tracks of a ROM's disc images (.cue, .gdi, .chd) into its
    soundtrack folder.

    Tracks already extracted are left as they are, so the call can be repeated.

    Raises:
        CdAudioUnavailableException: flac, or libchdr for a CHD, isn't installed.
        CdAudioNeedsFolderException: A sheet, or a disc an .m3u lists, sits loose
            in the platform folder.
        CdAudioEncodeException: A track couldn't be encoded.
    """
    if shutil.which(FLAC_BINARY) is None:
        raise CdAudioUnavailableException("The flac encoder is not installed")

    result = CdAudioExtraction()
    images = _disc_images(rom)
    if not images:
        return result

    lib = _require_libchdr(images)

    if rom.has_simple_single_file:
        # A CHD is self-contained, but a lone sheet would leave its tracks behind.
        if not images[0].file_name.lower().endswith(".chd"):
            raise CdAudioNeedsFolderException(
                "Move the disc into a folder of its own to extract its audio"
            )
        disc = fs_rom_handler.validate_path(images[0].full_path)
        playlist = await asyncio.to_thread(listing_playlist, disc)
        if playlist:
            raise CdAudioNeedsFolderException(
                f"{playlist} lists this disc, so moving it would break the "
                "playlist. Move the set into a folder of its own to extract "
                "its audio"
            )
        rom = await promote_single_file_to_folder(rom)
        images = _disc_images(rom)

    folder = CATEGORY_UPLOAD_FOLDERS[RomFileCategory.SOUNDTRACK]
    planned = await asyncio.to_thread(_plan_tracks, images, lib)
    try:
        for track in planned:
            try:
                destination = await prepare_upload_destination(
                    rom, folder, track.file_name
                )
            except UploadConflictException:
                result.skipped.append(track.file_name)
                continue
            staged = staging_path(destination.location)
            await encode_track(track.source, staged, rom.name)
            try:
                move_into_place(destination.location, staged, overwrite=False)
            except UploadConflictException:
                # A concurrent extraction of the same disc got there first.
                result.skipped.append(track.file_name)
                continue
            result.extracted.append(track.file_name)
    finally:
        # Register whatever landed, even when a later track failed.
        if result.extracted:
            await refresh_rom_files(rom)
            log.info(
                f"Extracted {len(result.extracted)} CD audio tracks from "
                f"{hl(rom.fs_name)}"
            )
    return result
