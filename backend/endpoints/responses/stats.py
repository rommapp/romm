from typing import TypedDict


class MetadataCoverageItem(TypedDict):
    source: str
    matched: int


class RegionBreakdownItem(TypedDict):
    region: str
    count: int


class StatsReturn(TypedDict, total=False):
    PLATFORMS: int
    ROMS: int
    SAVES: int
    STATES: int
    SCREENSHOTS: int
    TOTAL_FILESIZE_BYTES: int
    METADATA_COVERAGE: dict[int, list[MetadataCoverageItem]]
    REGION_BREAKDOWN: dict[int, list[RegionBreakdownItem]]
