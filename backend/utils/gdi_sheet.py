import re
from collections.abc import Mapping
from dataclasses import dataclass

from utils.cue_sheet import (
    AUDIO_SECTOR_BYTES,
    SHEET_FILE_PATTERN,
    AudioTrackRange,
    sheet_file_name,
)

AUDIO_TRACK_TYPE = 0

# "<track> <lba> <type> <sector size> <file> <offset>". Numbers are ASCII and
# bounded so int() always takes them.
_LINE_REGEX = re.compile(
    rf"^\s*(\d{{1,3}})\s+\d{{1,9}}\s+(\d{{1,3}})\s+(\d{{1,5}})\s+"
    rf"{SHEET_FILE_PATTERN}\s+-?\d+\s*$",
    re.ASCII,
)


@dataclass(frozen=True)
class GdiTrack:
    number: int
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
        number, kind, sector_size = (int(match.group(i)) for i in range(1, 4))
        tracks.append(
            GdiTrack(
                number=number,
                type=kind,
                sector_size=sector_size,
                file_name=sheet_file_name(match),
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
