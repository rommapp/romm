"""Song listings for console sound files, read with game-music-emu (libgme)."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

from logger.logger import log
from utils.audio_tags import AudioTags

# Mirrors DEFAULT_FADE_MSECS in docker/gme/romm_gme.cpp, so listed durations
# match what the player renders.
DEFAULT_FADE_MS = 8000

# Formats whose headers don't record a song count (libgme reports 256 slots),
# so only a sidecar .m3u lists their songs.
UNCOUNTED_EXTENSIONS = frozenset({".hes", ".kss"})

MAX_SONGS = 256

# gme_open_data's sample rate for reading track info without an emulator.
_INFO_ONLY = -1


@dataclass(frozen=True)
class Song:
    """One song of a sound file: the index libgme plays it by, and its tags."""

    index: int
    tags: AudioTags


class _GmeInfo(ctypes.Structure):
    # Only the leading fields of gme_info_t; libgme owns the allocation.
    _fields_ = [
        ("length", ctypes.c_int),
        ("intro_length", ctypes.c_int),
        ("loop_length", ctypes.c_int),
        ("play_length", ctypes.c_int),
        # A reserved -1 before libgme 0.6.4.
        ("fade_length", ctypes.c_int),
        *[(f"i{n}", ctypes.c_int) for n in range(5, 16)],
        ("system", ctypes.c_char_p),
        ("game", ctypes.c_char_p),
        ("song", ctypes.c_char_p),
        ("author", ctypes.c_char_p),
        ("copyright", ctypes.c_char_p),
    ]


@cache
def _libgme() -> ctypes.CDLL | None:
    for name in ("libgme.so.0", "libgme.so", ctypes.util.find_library("gme")):
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        lib.gme_open_data.argtypes = [
            ctypes.c_void_p,
            ctypes.c_long,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_int,
        ]
        lib.gme_open_data.restype = ctypes.c_char_p
        lib.gme_load_m3u_data.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
        ]
        lib.gme_load_m3u_data.restype = ctypes.c_char_p
        lib.gme_track_count.argtypes = [ctypes.c_void_p]
        lib.gme_track_count.restype = ctypes.c_int
        lib.gme_track_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.POINTER(_GmeInfo)),
            ctypes.c_int,
        ]
        lib.gme_track_info.restype = ctypes.c_char_p
        lib.gme_free_info.argtypes = [ctypes.POINTER(_GmeInfo)]
        lib.gme_free_info.restype = None
        lib.gme_delete.argtypes = [ctypes.c_void_p]
        lib.gme_delete.restype = None
        return lib
    log.warning("libgme not found; chiptune files are listed as single tracks")
    return None


def _text(value: bytes | None) -> str | None:
    if not value:
        return None
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError:
        # Older rips store Latin-1 in their headers.
        text = value.decode("latin-1")
    return text.strip() or None


def find_sidecar_m3u(file_name: str, candidates: Iterable[str]) -> str | None:
    """The .m3u among `candidates` named like `file_name`, ignoring case."""
    stem = os.path.splitext(file_name)[0].lower()
    for candidate in sorted(candidates):
        base, ext = os.path.splitext(candidate)
        if ext.lower() == ".m3u" and base.lower() == stem:
            return candidate
    return None


def sidecar_m3u_path(file_path: str) -> str | None:
    """The .m3u beside a sound file with the same name, if there is one."""
    directory, name = os.path.split(file_path)
    try:
        entries = os.listdir(directory or ".")
    except OSError:
        return None
    match = find_sidecar_m3u(name, entries)
    return os.path.join(directory, match) if match else None


def _song_tags(info: _GmeInfo, index: int) -> AudioTags:
    fade = info.fade_length if info.fade_length > 0 else DEFAULT_FADE_MS
    return {
        "title": _text(info.song),
        "artist": _text(info.author),
        "album": _text(info.game),
        # Copyright fields read like "1990 Konami"; the year is parsed from it.
        "year": _text(info.copyright),
        "track": str(index + 1),
        "duration_seconds": (info.play_length + fade) / 1000,
    }


def read_songs(file_path: str, m3u_path: str | None = None) -> list[Song] | None:
    """List the songs in a console sound file.

    Args:
        file_path: the sound file.
        m3u_path: a playlist naming and timing its songs, loaded after the file.

    Returns:
        The songs in playback order, skipping playlist entries libgme rejects,
        or None when libgme is missing or can't read the file.
    """
    lib = _libgme()
    if lib is None:
        return None
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        m3u = None
        if m3u_path:
            with open(m3u_path, "rb") as f:
                m3u = f.read()
    except OSError as exc:
        log.warning(f"Could not read {file_path} for its song list: {exc}")
        return None

    emu = ctypes.c_void_p()
    if lib.gme_open_data(data, len(data), ctypes.byref(emu), _INFO_ONLY):
        return None
    try:
        has_playlist = m3u is not None and not lib.gme_load_m3u_data(emu, m3u, len(m3u))
        count = lib.gme_track_count(emu)
        ext = os.path.splitext(file_path)[1].lower()
        if not has_playlist and ext in UNCOUNTED_EXTENSIONS:
            count = 1
        songs: list[Song] = []
        for index in range(min(max(count, 1), MAX_SONGS)):
            info = ctypes.POINTER(_GmeInfo)()
            if lib.gme_track_info(emu, ctypes.byref(info), index):
                continue
            try:
                songs.append(Song(index, _song_tags(info.contents, index)))
            finally:
                lib.gme_free_info(info)
        if len(songs) == 1:
            # A track number only means something among a file's other songs.
            songs[0].tags["track"] = None
        return songs or None
    finally:
        lib.gme_delete(emu)
