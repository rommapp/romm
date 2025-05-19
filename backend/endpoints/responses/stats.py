from typing import TypedDict


class StatsReturn(TypedDict):
    PLATFORMS_COUNT: int
    PLATFORMS: list
    ROMS: int
    SAVES: int
    STATES: int
    SCREENSHOTS: int
    TOTAL_FILESIZE: int
