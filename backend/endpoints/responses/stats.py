from typing import TypedDict


class StatsReturn(TypedDict):
    PLATFORMS: int
    ROMS: int
    SAVES: int
    STATES: int
    SCREENSHOTS: int
    TOTAL_FILESIZE_BYTES: int
