import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from anyio import Path as AnyioPath

from handler.filesystem import fs_rom_handler
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
from models.rom import Rom, RomFileCategory
from utils.cue_sheet import AudioTrackRange, audio_track_ranges, parse_cue_sheet

FLAC_BINARY = "flac"
READ_CHUNK_BYTES = 1024 * 1024
# A 74-minute disc encodes in well under a minute; this only catches a hang.
ENCODE_TIMEOUT_SECONDS = 600


class CdAudioUnavailableException(RuntimeError):
    """The flac encoder isn't installed."""


class CdAudioEncodeException(RuntimeError):
    """flac failed on a track."""


class CdAudioNeedsFolderException(RuntimeError):
    """The disc isn't in a folder of its own, so there is nowhere to write."""


@dataclass
class CdAudioExtraction:
    extracted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def track_file_name(cue_stem: str, track: AudioTrackRange) -> str:
    """Name the track after its sheet, so each disc of a set keeps its own."""
    return f"{cue_stem} - Track {track.number:02d}.flac"


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


def _file_sizes(files: dict[str, Path]) -> dict[str, int]:
    return {name: path.stat().st_size for name, path in files.items()}


def _encode_args(track: AudioTrackRange, album: str | None, output: Path) -> list[str]:
    tags = {
        "TITLE": track.title or f"Track {track.number:02d}",
        "TRACKNUMBER": str(track.number),
        "ALBUM": album,
        "ARTIST": track.performer,
    }
    return [
        FLAC_BINARY,
        "--silent",
        "--force-raw-format",
        f"--endian={'big' if track.big_endian else 'little'}",
        "--sign=signed",
        "--channels=2",
        "--bps=16",
        "--sample-rate=44100",
        *(f"--tag={key}={value}" for key, value in tags.items() if value),
        "-o",
        str(output),
        "-",
    ]


async def _feed(stdin: asyncio.StreamWriter, source: Path, track: AudioTrackRange):
    with source.open("rb") as image:
        image.seek(track.offset)
        remaining = track.length
        while remaining > 0:
            chunk = await asyncio.to_thread(
                image.read, min(READ_CHUNK_BYTES, remaining)
            )
            if not chunk:
                break
            stdin.write(chunk)
            await stdin.drain()
            remaining -= len(chunk)
    stdin.close()
    await stdin.wait_closed()


async def encode_track(
    source: Path, track: AudioTrackRange, output: Path, album: str | None
) -> None:
    """Encode one track's PCM straight from the disc image into a FLAC file.

    Raises:
        CdAudioEncodeException: flac exited with an error or timed out.
    """
    process = await asyncio.create_subprocess_exec(
        *_encode_args(track, album, output),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None and process.stderr is not None
    try:
        await asyncio.wait_for(
            _feed(process.stdin, source, track), ENCODE_TIMEOUT_SECONDS
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
                f"flac failed on track {track.number}"
            ) from exc
        raise
    if process.returncode != 0:
        await AnyioPath(output).unlink(missing_ok=True)
        raise CdAudioEncodeException(
            stderr.decode(errors="replace").strip()
            or f"flac exited with {process.returncode}"
        )


async def extract_cd_audio(rom: Rom) -> CdAudioExtraction:
    """Write the audio tracks of a ROM's cue sheets into its soundtrack folder.

    Tracks already extracted are left as they are, so the call can be repeated.

    Raises:
        CdAudioUnavailableException: flac isn't installed.
        CdAudioNeedsFolderException: The sheet sits loose in the platform folder.
        CdAudioEncodeException: A track couldn't be encoded.
    """
    if shutil.which(FLAC_BINARY) is None:
        raise CdAudioUnavailableException("The flac encoder is not installed")
    # Promoting a lone sheet into a folder would leave its tracks behind.
    if rom.has_simple_single_file:
        raise CdAudioNeedsFolderException(
            "Move the disc into a folder of its own to extract its audio"
        )

    folder = CATEGORY_UPLOAD_FOLDERS[RomFileCategory.SOUNDTRACK]
    result = CdAudioExtraction()
    sheets = [
        file
        for file in rom.files
        if file.category in (None, RomFileCategory.GAME)
        and file.file_name.lower().endswith(".cue")
    ]
    try:
        for sheet in sheets:
            await _extract_sheet(rom, sheet.full_path, folder, result)
    finally:
        # Register whatever landed, even when a later track failed.
        if result.extracted:
            await refresh_rom_files(rom)
            log.info(
                f"Extracted {len(result.extracted)} CD audio tracks from "
                f"{hl(rom.fs_name)}"
            )
    return result


async def _extract_sheet(
    rom: Rom, sheet_rel_path: str, folder: str, result: CdAudioExtraction
) -> None:
    sheet_path = fs_rom_handler.validate_path(sheet_rel_path)
    tracks = parse_cue_sheet(await asyncio.to_thread(_read_sheet, sheet_path))
    located = await asyncio.to_thread(
        _locate_files, sheet_path.parent, {track.file_name for track in tracks}
    )
    sizes = await asyncio.to_thread(_file_sizes, located)
    for track in audio_track_ranges(tracks, sizes):
        name = track_file_name(sheet_path.stem, track)
        try:
            destination = await prepare_upload_destination(rom, folder, name)
        except UploadConflictException:
            result.skipped.append(name)
            continue
        staged = staging_path(destination.location)
        await encode_track(located[track.file_name], track, staged, rom.name)
        move_into_place(destination.location, staged, overwrite=False)
        result.extracted.append(name)
