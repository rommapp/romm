from __future__ import annotations

import ctypes
import ctypes.util
import functools
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# A CD frame in a CHD: one raw sector followed by its subcode.
SECTOR_BYTES = 2352
FRAME_BYTES = SECTOR_BYTES + 96
# Each track's frames are padded up to a multiple of this.
TRACK_PADDING = 4

_OPEN_READ = 1
_METADATA_BUFFER_BYTES = 512


def _tag(name: str) -> int:
    return int.from_bytes(name.encode("ascii"), "big")


# Current and legacy CD track metadata. GD-ROM ('CHGD') pads tracks
# differently and isn't read.
TRACK_METADATA_TAGS = (_tag("CHT2"), _tag("CHTR"))


@dataclass(frozen=True)
class ChdTrack:
    number: int
    type: str
    frames: int
    pregap: int
    pregap_stored: bool


@dataclass(frozen=True)
class ChdAudioTrack:
    """An audio track's playable frames, big-endian 44.1 kHz 16-bit stereo."""

    number: int
    first_frame: int
    frame_count: int


def parse_track_metadata(text: str) -> ChdTrack | None:
    """Read one CHT2/CHTR track entry, or None when it's malformed."""
    fields = dict(
        token.split(":", 1) for token in text.strip("\0 ").split() if ":" in token
    )
    try:
        pregap = int(fields.get("PREGAP", "0"))
        return ChdTrack(
            number=int(fields["TRACK"]),
            type=fields["TYPE"].upper(),
            frames=int(fields["FRAMES"]),
            pregap=pregap,
            # A 'V' pregap type means the pregap's frames are in the image.
            pregap_stored=fields.get("PGTYPE", "").upper().startswith("V"),
        )
    except KeyError, ValueError:
        return None


def audio_tracks(tracks: list[ChdTrack]) -> list[ChdAudioTrack]:
    """Locate each audio track's frames, skipping any pregap stored ahead of it."""
    located: list[ChdAudioTrack] = []
    frame = 0
    for track in sorted(tracks, key=lambda t: t.number):
        if track.type == "AUDIO":
            skip = track.pregap if track.pregap_stored else 0
            if track.frames > skip:
                located.append(
                    ChdAudioTrack(
                        number=track.number,
                        first_frame=frame + skip,
                        frame_count=track.frames - skip,
                    )
                )
        frame += -(-track.frames // TRACK_PADDING) * TRACK_PADDING
    return located


class _Header(ctypes.Structure):
    # The leading fields of libchdr's chd_header, which is all this reads.
    _fields_ = [
        ("length", ctypes.c_uint32),
        ("version", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("compression", ctypes.c_uint32 * 4),
        ("hunkbytes", ctypes.c_uint32),
        ("totalhunks", ctypes.c_uint32),
    ]


class ChdError(RuntimeError):
    """libchdr refused the file."""


@functools.cache
def load_libchdr() -> ctypes.CDLL | None:
    """libchdr, or None when it isn't installed."""
    # find_library can't see musl's library paths, so the soname goes first.
    for name in ("libchdr.so.0", ctypes.util.find_library("chdr")):
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        lib.chd_open.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.chd_close.argtypes = [ctypes.c_void_p]
        lib.chd_get_header.argtypes = [ctypes.c_void_p]
        lib.chd_get_header.restype = ctypes.POINTER(_Header)
        lib.chd_get_metadata.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint8),
        ]
        lib.chd_read.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        return lib
    return None


class ChdImage:
    """A CD image opened read-only through libchdr."""

    def __init__(self, lib: ctypes.CDLL, path: Path):
        self._lib = lib
        self._handle = ctypes.c_void_p()
        error = lib.chd_open(str(path).encode(), _OPEN_READ, None, self._handle)
        if error:
            raise ChdError(f"libchdr could not open {path.name} (error {error})")
        header = lib.chd_get_header(self._handle).contents
        self.hunk_bytes: int = header.hunkbytes
        self.total_hunks: int = header.totalhunks

    def __enter__(self) -> ChdImage:
        return self

    def __exit__(self, *_: object) -> None:
        if self._handle:
            self._lib.chd_close(self._handle)
            self._handle = ctypes.c_void_p()

    def tracks(self) -> list[ChdTrack]:
        buffer = ctypes.create_string_buffer(_METADATA_BUFFER_BYTES)
        length = ctypes.c_uint32()
        for tag in TRACK_METADATA_TAGS:
            found: list[ChdTrack] = []
            index = 0
            while not self._lib.chd_get_metadata(
                self._handle, tag, index, buffer, len(buffer), length, None, None
            ):
                track = parse_track_metadata(buffer.value.decode("ascii", "replace"))
                if track:
                    found.append(track)
                index += 1
            if found:
                return found
        return []

    def audio_pcm(self, track: ChdAudioTrack) -> Iterator[bytes]:
        """Yield a track's samples a hunk at a time, dropping the subcode."""
        if self.hunk_bytes % FRAME_BYTES:
            raise ChdError("Image isn't laid out in CD frames")
        frames_per_hunk = self.hunk_bytes // FRAME_BYTES
        hunk = ctypes.create_string_buffer(self.hunk_bytes)
        frame = track.first_frame
        end = track.first_frame + track.frame_count
        while frame < end:
            number, offset = divmod(frame, frames_per_hunk)
            if number >= self.total_hunks:
                return
            if self._lib.chd_read(self._handle, number, hunk):
                raise ChdError(f"libchdr could not read hunk {number}")
            count = min(frames_per_hunk - offset, end - frame)
            raw = hunk.raw
            yield b"".join(
                raw[
                    (offset + i) * FRAME_BYTES : (offset + i) * FRAME_BYTES
                    + SECTOR_BYTES
                ]
                for i in range(count)
            )
            frame += count
