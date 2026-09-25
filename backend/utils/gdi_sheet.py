from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from utils.cue_sheet import AudioTrackRange

AUDIO_TRACK_TYPE = 0
AUDIO_SECTOR_BYTES = 2352

# "<track> <lba> <type> <sector size> <file> <offset>", the file quoted when it
# has spaces.
_LINE_REGEX = re.compile(
    r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(?:"(?P<quoted>[^"]+)"|(?P<bare>\S+))'
    r"\s+-?\d+\s*$"
)


@dataclass(frozen=True)
class GdiTrack:
    number: int
    lba: int
    type: int
    sector_size: int
    file_name: str


def parse_gdi_sheet(text: str) -> list[GdiTrack]:
    """Read the tracks of a Dreamcast .gdi sheet, keeping only each file's name.

    Args:
        text: The sheet's contents.
    Returns:
        The tracks in sheet order; the count line and malformed lines are skipped.
    """
    tracks: list[GdiTrack] = []
    for line in text.splitlines():
        match = _LINE_REGEX.match(line)
        if not match:
            continue
        number, lba, kind, sector_size = (int(match.group(i)) for i in range(1, 5))
        path = match.group("quoted") or match.group("bare")
        tracks.append(
            GdiTrack(
                number=number,
                lba=lba,
                type=kind,
                sector_size=sector_size,
                file_name=re.split(r"[\\/]", path)[-1],
            )
        )
    return tracks


def gdi_audio_ranges(
    tracks: list[GdiTrack], file_sizes: Mapping[str, int]
) -> list[AudioTrackRange]:
    """Each audio track fills its own file with little-endian PCM.

    Args:
        tracks: Tracks from `parse_gdi_sheet`.
        file_sizes: Size in bytes of each referenced file present on disk.
    Returns:
        One range per audio track whose file is present, trimmed to whole samples.
    """
    ranges: list[AudioTrackRange] = []
    for track in tracks:
        size = file_sizes.get(track.file_name)
        if (
            track.type != AUDIO_TRACK_TYPE
            or track.sector_size != AUDIO_SECTOR_BYTES
            or not size
        ):
            continue
        ranges.append(
            AudioTrackRange(
                number=track.number,
                file_name=track.file_name,
                offset=0,
                length=size // 4 * 4,
                big_endian=False,
                title=None,
                performer=None,
            )
        )
    return ranges
