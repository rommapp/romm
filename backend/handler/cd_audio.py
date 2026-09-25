import asyncio
import ctypes
import functools
import shutil
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
from utils.cue_sheet import audio_track_ranges, parse_cue_sheet

FLAC_BINARY = "flac"
READ_CHUNK_BYTES = 1024 * 1024
# A 74-minute disc encodes in well under a minute; this only catches a hang.
ENCODE_TIMEOUT_SECONDS = 600
DISC_IMAGE_EXTENSIONS = (".cue", ".chd")

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


def track_file_name(image_stem: str, number: int) -> str:
    """Name the track after its image, so each disc of a set keeps its own."""
    return f"{image_stem} - Track {number:02d}.flac"


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


def _sheet_sources(sheet_path: Path) -> list[AudioSource]:
    tracks = parse_cue_sheet(_read_sheet(sheet_path))
    located = _locate_files(sheet_path.parent, {track.file_name for track in tracks})
    sizes = {name: path.stat().st_size for name, path in located.items()}
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
        for track in audio_track_ranges(tracks, sizes)
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
    tags = {
        "TITLE": source.title or f"Track {source.number:02d}",
        "TRACKNUMBER": str(source.number),
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


async def _feed(stdin: asyncio.StreamWriter, pcm: PcmChunks) -> None:
    try:
        while (chunk := await asyncio.to_thread(next, pcm, None)) is not None:
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
    return [
        file
        for file in rom.files
        if file.category in (None, RomFileCategory.GAME)
        and file.file_name.lower().endswith(DISC_IMAGE_EXTENSIONS)
    ]


async def extract_cd_audio(rom: Rom) -> CdAudioExtraction:
    """Write the audio tracks of a ROM's cue sheets and CHD images into its
    soundtrack folder.

    Tracks already extracted are left as they are, so the call can be repeated.

    Raises:
        CdAudioUnavailableException: flac, or libchdr for a CHD, isn't installed.
        CdAudioNeedsFolderException: A cue sheet sits loose in the platform folder.
        CdAudioEncodeException: A track couldn't be encoded.
    """
    if shutil.which(FLAC_BINARY) is None:
        raise CdAudioUnavailableException("The flac encoder is not installed")

    result = CdAudioExtraction()
    images = _disc_images(rom)
    if not images:
        return result

    lib = load_libchdr()
    if lib is None and any(i.file_name.lower().endswith(".chd") for i in images):
        raise CdAudioUnavailableException(
            "Reading CHD images needs libchdr, which is not installed"
        )

    if rom.has_simple_single_file:
        # A CHD is self-contained, but a lone sheet would leave its tracks behind.
        if images[0].file_name.lower().endswith(".cue"):
            raise CdAudioNeedsFolderException(
                "Move the disc into a folder of its own to extract its audio"
            )
        rom = await promote_single_file_to_folder(rom)
        images = _disc_images(rom)

    folder = CATEGORY_UPLOAD_FOLDERS[RomFileCategory.SOUNDTRACK]
    try:
        for image in images:
            path = fs_rom_handler.validate_path(image.full_path)
            try:
                if path.suffix.lower() == ".chd":
                    assert lib is not None
                    sources = await asyncio.to_thread(_chd_sources, lib, path)
                else:
                    sources = await asyncio.to_thread(_sheet_sources, path)
            except (ChdError, OSError) as exc:
                raise CdAudioEncodeException(f"Could not read {path.name}") from exc
            for source in sources:
                name = track_file_name(path.stem, source.number)
                try:
                    destination = await prepare_upload_destination(rom, folder, name)
                except UploadConflictException:
                    result.skipped.append(name)
                    continue
                staged = staging_path(destination.location)
                await encode_track(source, staged, rom.name)
                move_into_place(destination.location, staged, overwrite=False)
                result.extracted.append(name)
    finally:
        # Register whatever landed, even when a later track failed.
        if result.extracted:
            await refresh_rom_files(rom)
            log.info(
                f"Extracted {len(result.extracted)} CD audio tracks from "
                f"{hl(rom.fs_name)}"
            )
    return result
