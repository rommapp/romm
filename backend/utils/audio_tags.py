from __future__ import annotations

import os
from typing import TypedDict

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis

from logger.logger import log

ALLOWED_AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".flac"}
)

# Skip parsing anything larger than this — mutagen mmaps the file and can
# consume substantial memory on pathological inputs (e.g. a mislabeled 4GB WAV).
MAX_AUDIO_PARSE_BYTES = 512 * 1024 * 1024  # 512 MiB


class AudioMeta(TypedDict, total=False):
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


def is_allowed_audio_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_AUDIO_EXTENSIONS


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
    if isinstance(audio, OggVorbis):
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


def extract_audio_meta(full_path: str) -> AudioMeta | None:
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

    meta: AudioMeta = {
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
            return frame.data, frame.mime or "image/jpeg"
    return None


def _extract_picture_from_flac(audio: FLAC) -> tuple[bytes, str] | None:
    if audio.pictures:
        pic = audio.pictures[0]
        return pic.data, pic.mime or "image/jpeg"
    return None


def _extract_picture_from_ogg(audio: OggVorbis) -> tuple[bytes, str] | None:
    import base64

    pics = audio.get("metadata_block_picture") or []
    for encoded in pics:
        try:
            pic = Picture(base64.b64decode(encoded))
        except Exception as exc:
            log.debug(f"[audio_tags] ogg picture decode failed: {exc}")
            continue
        return pic.data, pic.mime or "image/jpeg"
    return None


def _extract_picture_from_mp4(audio: MP4) -> tuple[bytes, str] | None:
    covers = audio.tags.get("covr") if audio.tags else None
    if not covers:
        return None
    cover = covers[0]
    fmt = getattr(cover, "imageformat", None)
    mime = "image/png" if fmt == MP4.Cover.FORMAT_PNG else "image/jpeg"
    return bytes(cover), mime


_COVER_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _ext_for_mime(mime: str) -> str:
    return _COVER_EXT_BY_MIME.get(mime.lower().split(";")[0].strip(), "bin")


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
    audio_meta.cover_path), or None if no cover or write failed."""
    from config import RESOURCES_BASE_PATH

    cover = extract_embedded_cover(audio_full_path)
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


def remove_persisted_cover(cover_path: str | None) -> None:
    """Delete a persisted soundtrack cover (relative path under
    RESOURCES_BASE_PATH). Silently ignores missing files."""
    if not cover_path:
        return
    from config import RESOURCES_BASE_PATH

    abs_path = os.path.join(RESOURCES_BASE_PATH, cover_path)
    try:
        os.unlink(abs_path)
    except FileNotFoundError:
        return
    except OSError as exc:
        log.warning(f"[audio_tags] cover delete failed for {abs_path}: {exc}")


def extract_embedded_cover(full_path: str) -> tuple[bytes, str] | None:
    """Return (image_bytes, mime_type) for the first embedded picture, or None."""
    audio = _open_mutagen(full_path)
    if audio is None:
        return None

    if isinstance(audio, FLAC):
        return _extract_picture_from_flac(audio)
    if isinstance(audio, OggVorbis):
        return _extract_picture_from_ogg(audio)
    if isinstance(audio, MP4):
        return _extract_picture_from_mp4(audio)

    tags = getattr(audio, "tags", None)
    if isinstance(tags, ID3):
        return _extract_picture_from_id3(tags)

    return None
