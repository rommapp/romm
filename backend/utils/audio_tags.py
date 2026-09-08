from __future__ import annotations

import mimetypes
import os
import re
from typing import Any, TypedDict

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from logger.logger import log
from utils.media_types import IMAGE_EXT_BY_MIME_TYPE

ALLOWED_AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".flac"}
)

# Skip parsing anything larger than this — mutagen mmaps the file and can
# consume substantial memory on pathological inputs (e.g. a mislabeled 4GB WAV).
MAX_AUDIO_PARSE_BYTES = 512 * 1024 * 1024  # 512 MiB


class AudioTags(TypedDict, total=False):
    title: str | None
    artist: str | None
    album: str | None
    year: str | None
    genre: str | None
    track: str | None
    disc: str | None
    duration_seconds: float | None
    has_embedded_cover: bool
    cover_path: str | None
    file_mtime: float
    file_size: int


_YEAR_RE = re.compile(r"\d{4}")
_LEADING_INT_RE = re.compile(r"\s*(\d+)")
_SMALLINT_MAX = 32767


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = _YEAR_RE.search(value)
    return int(match.group()) if match else None


def _parse_leading_int(value: str | None) -> int | None:
    """First integer before any separator: '3/12' -> 3, 'A1' -> None."""
    if not value:
        return None
    match = _LEADING_INT_RE.match(value)
    if not match:
        return None
    parsed = int(match.group(1))
    return parsed if 0 <= parsed <= _SMALLINT_MAX else None


def _truncate(value: str | None, length: int) -> str | None:
    return value[:length] if value is not None else None


def track_meta_columns(tags: AudioTags) -> dict[str, Any]:
    """Map raw AudioTags onto TrackMeta column values (year/track/disc -> int).

    Free-text year/track/disc tags are parsed to ints here so the upload path,
    the scanner, and the migration backfill stay identical. Lengths mirror the
    TrackMeta columns. Only known keys are read, so transient keys such as
    file_mtime/file_size are dropped.
    """
    return {
        "title": _truncate(tags.get("title"), 512),
        "artist": _truncate(tags.get("artist"), 512),
        "album": _truncate(tags.get("album"), 512),
        "genre": _truncate(tags.get("genre"), 255),
        "year": _parse_year(tags.get("year")),
        "track": _parse_leading_int(tags.get("track")),
        "disc": _parse_leading_int(tags.get("disc")),
        "duration_seconds": tags.get("duration_seconds"),
        "has_embedded_cover": bool(tags.get("has_embedded_cover", False)),
        "cover_path": _truncate(tags.get("cover_path"), 1024),
    }


def is_allowed_audio_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_AUDIO_EXTENSIONS


# MIME types for audio formats that the stdlib mimetypes module guesses
# inconsistently (or not at all) across platforms.
AUDIO_MIME_OVERRIDES = {
    ".flac": "audio/flac",
    ".opus": "audio/ogg",
    ".m4a": "audio/mp4",
    ".oga": "audio/ogg",
    ".ogg": "audio/ogg",
}


def guess_audio_media_type(file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower()
    if ext in AUDIO_MIME_OVERRIDES:
        return AUDIO_MIME_OVERRIDES[ext]
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed or "application/octet-stream"


def _first(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else None
    return str(value)


def _id3_text(tags: ID3, key: str) -> str | None:
    frame = tags.get(key)
    if frame is None:
        return None
    text = getattr(frame, "text", None)
    if not text:
        return None
    first = text[0]
    return str(first) if first is not None else None


def _mp4_track_tuple(value: object) -> str | None:
    if not value:
        return None
    first = value[0] if isinstance(value, (list, tuple)) else value
    if isinstance(first, tuple):
        return str(first[0]) if first and first[0] else None
    return str(first)


def _allowed_mime_types(data: bytes) -> str:
    """Return MIME type for embedded cover bytes; only JPEG and PNG are allowed."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise ValueError("embedded cover is not JPEG or PNG")


# NOTE: the per-format tag and embedded-cover handling below (ID3 / MP4 /
# Vorbis comments / FLAC pictures) was largely AI-generated against mutagen's
# API — verify against real files when adding or changing a format.
def _extract_common_tags(audio: mutagen.FileType) -> dict[str, str | None]:
    """Extract common tags across formats from a single non-easy mutagen handle."""
    tags = getattr(audio, "tags", None)
    if tags is None:
        return {}

    if isinstance(tags, ID3):
        return {
            "title": _id3_text(tags, "TIT2"),
            "artist": _id3_text(tags, "TPE1"),
            "album": _id3_text(tags, "TALB"),
            "year": _id3_text(tags, "TDRC") or _id3_text(tags, "TYER"),
            "genre": _id3_text(tags, "TCON"),
            "track": _id3_text(tags, "TRCK"),
            "disc": _id3_text(tags, "TPOS"),
        }

    if isinstance(audio, MP4):
        return {
            "title": _first(tags.get("\xa9nam")),
            "artist": _first(tags.get("\xa9ART")),
            "album": _first(tags.get("\xa9alb")),
            "year": _first(tags.get("\xa9day")),
            "genre": _first(tags.get("\xa9gen")),
            "track": _mp4_track_tuple(tags.get("trkn")),
            "disc": _mp4_track_tuple(tags.get("disk")),
        }

    # Vorbis comments (FLAC, OggVorbis, OggOpus, …)
    return {
        "title": _first(tags.get("title")),
        "artist": _first(tags.get("artist")),
        "album": _first(tags.get("album")),
        "year": _first(tags.get("date")),
        "genre": _first(tags.get("genre")),
        "track": _first(tags.get("tracknumber")),
        "disc": _first(tags.get("discnumber")),
    }


def _has_embedded_cover(audio: mutagen.FileType) -> bool:
    if isinstance(audio, FLAC):
        return bool(audio.pictures)

    tags = getattr(audio, "tags", None)
    if tags is None:
        return False
    if isinstance(audio, (OggVorbis, OggOpus)):
        return bool(tags.get("metadata_block_picture"))
    if isinstance(audio, MP4):
        return bool(tags.get("covr"))
    if isinstance(tags, ID3):
        return any(isinstance(f, APIC) for f in tags.values())
    return False


def _open_mutagen(full_path: str) -> mutagen.FileType | None:
    """Open an audio file via mutagen with a size cap. Returns None on failure."""
    try:
        stat = os.stat(full_path)
    except OSError as exc:
        log.warning(f"[audio_tags] stat failed for {full_path}: {exc}")
        return None

    if stat.st_size > MAX_AUDIO_PARSE_BYTES:
        log.warning(
            f"[audio_tags] skipping oversized audio {full_path}: "
            f"{stat.st_size} bytes > {MAX_AUDIO_PARSE_BYTES}"
        )
        return None

    try:
        return mutagen.File(full_path)
    except Exception as exc:
        log.warning(f"[audio_tags] parse failed for {full_path}: {exc}")
        return None


def extract_audio_meta(full_path: str) -> AudioTags | None:
    """Read tags + duration + embedded-cover presence from an audio file.

    Returns None if the file cannot be parsed. Never raises — on any failure
    we log and fall back to None so the upload/scan path keeps moving.

    Opens the file once with mutagen (non-easy) and derives tags, duration,
    and cover presence from the same handle.
    """
    try:
        stat = os.stat(full_path)
    except OSError as exc:
        log.warning(f"[audio_tags] stat failed for {full_path}: {exc}")
        return None

    audio = _open_mutagen(full_path)
    if audio is None:
        return None

    meta: AudioTags = {
        "file_mtime": stat.st_mtime,
        "file_size": stat.st_size,
    }

    common = _extract_common_tags(audio)
    for key in ("title", "artist", "album", "year", "genre", "track", "disc"):
        meta[key] = common.get(key)  # type: ignore[literal-required]

    info = getattr(audio, "info", None)
    duration = getattr(info, "length", None) if info is not None else None
    meta["duration_seconds"] = float(duration) if duration else None

    meta["has_embedded_cover"] = _has_embedded_cover(audio)

    return meta


def _extract_picture_from_id3(tags: ID3) -> tuple[bytes, str] | None:
    for frame in tags.values():
        if isinstance(frame, APIC):
            return frame.data, _allowed_mime_types(frame.data)
    return None


def _extract_picture_from_flac(audio: FLAC) -> tuple[bytes, str] | None:
    if audio.pictures:
        pic = audio.pictures[0]
        return pic.data, _allowed_mime_types(pic.data)
    return None


def _extract_picture_from_ogg(audio: OggVorbis | OggOpus) -> tuple[bytes, str] | None:
    import base64

    pics = audio.get("metadata_block_picture") or []
    for encoded in pics:
        try:
            pic = Picture(base64.b64decode(encoded))
        except Exception as exc:
            log.debug(f"[audio_tags] ogg picture decode failed: {exc}")
            continue
        return pic.data, _allowed_mime_types(pic.data)
    return None


def _extract_picture_from_mp4(audio: MP4) -> tuple[bytes, str] | None:
    covers = audio.tags.get("covr") if audio.tags else None
    if not covers:
        return None
    cover = covers[0]
    data = bytes(cover)
    return data, _allowed_mime_types(data)


def _ext_for_mime(mime: str) -> str:
    return IMAGE_EXT_BY_MIME_TYPE.get(mime.lower().split(";")[0].strip(), "bin")


def soundtrack_cover_dir(platform_id: int, rom_id: int) -> str:
    """Relative directory (under RESOURCES_BASE_PATH) where soundtrack covers
    for a given ROM are persisted."""
    return f"roms/{platform_id}/{rom_id}/soundtracks"


def persist_embedded_cover(
    audio_full_path: str,
    platform_id: int,
    rom_id: int,
    file_id: int,
) -> str | None:
    """Extract the embedded cover from `audio_full_path` and write it under
    RESOURCES_BASE_PATH. Returns the relative path (suitable for storing in
    track_meta.cover_path), or None if no cover or write failed."""
    from config import RESOURCES_BASE_PATH

    try:
        cover = extract_embedded_cover(audio_full_path)
    except Exception as exc:
        log.error(f"[audio_tags] cover extract failed for {audio_full_path}: {exc}")
        return None
    if cover is None:
        return None

    data, mime = cover
    rel_dir = soundtrack_cover_dir(platform_id, rom_id)
    rel_path = f"{rel_dir}/{file_id}.{_ext_for_mime(mime)}"
    abs_dir = os.path.join(RESOURCES_BASE_PATH, rel_dir)
    abs_path = os.path.join(RESOURCES_BASE_PATH, rel_path)

    try:
        os.makedirs(abs_dir, exist_ok=True)
        with open(abs_path, "wb") as fh:
            fh.write(data)
    except OSError as exc:
        log.warning(f"[audio_tags] cover write failed for {abs_path}: {exc}")
        return None

    return rel_path


def remove_persisted_cover(cover_path: str | None) -> bool:
    """Delete a persisted soundtrack cover (relative path under
    RESOURCES_BASE_PATH). Silently ignores missing files.

    Returns whether the file is gone, so a caller that is about to drop the
    only reference to it can keep that reference and retry later instead.
    """
    if not cover_path:
        return True
    from config import RESOURCES_BASE_PATH

    abs_path = os.path.join(RESOURCES_BASE_PATH, cover_path)
    try:
        os.unlink(abs_path)
    except FileNotFoundError:
        return True
    except OSError as exc:
        log.warning(f"[audio_tags] cover delete failed for {abs_path}: {exc}")
        return False

    return True


def extract_embedded_cover(full_path: str) -> tuple[bytes, str] | None:
    """Return (image_bytes, mime_type) for the first embedded picture, or None
    if the file has no embedded cover.

    Raises if a cover is present but cannot be read (e.g. an unsupported
    image format) so callers can tell that failure apart from "no cover".
    """
    audio = _open_mutagen(full_path)
    if audio is None:
        return None

    if isinstance(audio, FLAC):
        return _extract_picture_from_flac(audio)
    if isinstance(audio, (OggVorbis, OggOpus)):
        return _extract_picture_from_ogg(audio)
    if isinstance(audio, MP4):
        return _extract_picture_from_mp4(audio)

    tags = getattr(audio, "tags", None)
    if isinstance(tags, ID3):
        return _extract_picture_from_id3(tags)

    return None
