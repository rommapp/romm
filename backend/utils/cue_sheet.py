from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

FRAMES_PER_SECOND = 75

# Bytes per sector for each track mode a raw image can hold.
SECTOR_SIZES = {
    "AUDIO": 2352,
    "CDG": 2448,
    "MODE1/2048": 2048,
    "MODE1/2352": 2352,
    "MODE2/2336": 2336,
    "MODE2/2352": 2352,
    "CDI/2336": 2336,
    "CDI/2352": 2352,
}

# FILE types holding raw sectors; WAVE, MP3 and AIFF tracks are already audio.
RAW_FILE_TYPES = {"BINARY": False, "MOTOROLA": True}

_FILE_REGEX = re.compile(r'^(?:"(?P<quoted>[^"]*)"|(?P<bare>\S+))\s+(?P<type>\S+)$')
_MSF_REGEX = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2})$")


@dataclass
class CueTrack:
    number: int
    mode: str
    file_name: str
    file_type: str
    indexes: dict[int, int] = field(default_factory=dict)
    title: str | None = None
    performer: str | None = None


@dataclass(frozen=True)
class AudioTrackRange:
    """Where one audio track's 44.1 kHz 16-bit stereo PCM sits in its file."""

    number: int
    file_name: str
    offset: int
    length: int
    big_endian: bool
    title: str | None
    performer: str | None


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _msf_to_frames(value: str) -> int | None:
    match = _MSF_REGEX.match(value.strip())
    if not match:
        return None
    minutes, seconds, frames = (int(part) for part in match.groups())
    return (minutes * 60 + seconds) * FRAMES_PER_SECOND + frames


def parse_cue_sheet(text: str) -> list[CueTrack]:
    """Read the tracks of a cue sheet, keeping only each FILE's base name.

    Args:
        text: The sheet's contents.
    Returns:
        The tracks in sheet order; malformed lines are skipped.
    """
    tracks: list[CueTrack] = []
    file_name: str | None = None
    file_type = ""
    for raw_line in text.splitlines():
        keyword, _, rest = raw_line.strip().partition(" ")
        keyword = keyword.upper()
        rest = rest.strip()
        if keyword == "FILE":
            match = _FILE_REGEX.match(rest)
            if not match:
                file_name = None
                continue
            path = match.group("quoted") or match.group("bare")
            # Sheets made on Windows use backslashes; only the name is trusted.
            file_name = re.split(r"[\\/]", path)[-1]
            file_type = match.group("type").upper()
        elif keyword == "TRACK" and file_name:
            number, _, mode = rest.partition(" ")
            if number.isdigit():
                tracks.append(
                    CueTrack(
                        number=int(number),
                        mode=mode.strip().upper(),
                        file_name=file_name,
                        file_type=file_type,
                    )
                )
        elif keyword == "INDEX" and tracks:
            index, _, position = rest.partition(" ")
            frames = _msf_to_frames(position)
            if index.isdigit() and frames is not None:
                tracks[-1].indexes[int(index)] = frames
        elif keyword in ("TITLE", "PERFORMER") and tracks:
            setattr(tracks[-1], keyword.lower(), _unquote(rest) or None)
    return tracks


def audio_track_ranges(
    tracks: list[CueTrack], file_sizes: Mapping[str, int]
) -> list[AudioTrackRange]:
    """Locate the PCM of each audio track stored in a raw image file.

    Args:
        tracks: Tracks from `parse_cue_sheet`.
        file_sizes: Size in bytes of each referenced file present on disk.
    Returns:
        One range per audio track, from INDEX 01 up to where the next track's
        pregap starts, trimmed to whole stereo samples.
    """
    ranges: list[AudioTrackRange] = []
    by_file: dict[str, list[CueTrack]] = {}
    for track in tracks:
        by_file.setdefault(track.file_name, []).append(track)

    for file_name, file_tracks in by_file.items():
        size = file_sizes.get(file_name)
        big_endian = RAW_FILE_TYPES.get(file_tracks[0].file_type)
        if size is None or big_endian is None:
            continue

        # A track's region opens at its first index (the pregap when there is
        # one), and each region is laid out in its own track's sector size.
        region_starts: list[int] = []
        for position, track in enumerate(file_tracks):
            if not track.indexes:
                break
            if position:
                previous = file_tracks[position - 1]
                if previous.mode not in SECTOR_SIZES:
                    break
                sectors = min(track.indexes.values()) - min(previous.indexes.values())
                region_starts.append(
                    region_starts[-1] + sectors * SECTOR_SIZES[previous.mode]
                )
            else:
                region_starts.append(
                    min(track.indexes.values()) * SECTOR_SIZES.get(track.mode, 0)
                )
        # Past a track that can't be measured, the file's size bounds nothing.
        measured_to_end = len(region_starts) == len(file_tracks)

        for position, byte_start in enumerate(region_starts):
            track = file_tracks[position]
            if track.mode != "AUDIO" or 1 not in track.indexes:
                continue
            if position + 1 < len(region_starts):
                end = region_starts[position + 1]
            elif measured_to_end:
                end = size
            else:
                continue
            pregap = track.indexes[1] - min(track.indexes.values())
            offset = byte_start + pregap * SECTOR_SIZES["AUDIO"]
            length = (min(end, size) - offset) // 4 * 4
            if length > 0:
                ranges.append(
                    AudioTrackRange(
                        number=track.number,
                        file_name=file_name,
                        offset=offset,
                        length=length,
                        big_endian=big_endian,
                        title=track.title,
                        performer=track.performer,
                    )
                )
    return ranges
