from typing import TypedDict

from .base import UTCDatetime


class DownloadLogEntry(TypedDict):
    """One served download. Admin-only: carries user identity and client info."""

    id: int
    user_id: int | None
    username: str
    rom_id: int | None
    rom_name: str
    platform_id: int | None
    platform_name: str
    source: str
    kind: str
    file_count: int
    size_bytes: int
    client_ip: str | None
    user_agent: str | None
    downloaded_at: UTCDatetime


class DownloadLogPage(TypedDict):
    items: list[DownloadLogEntry]
    total: int
    limit: int
    offset: int


class TopDownloadedRom(TypedDict):
    rom_id: int
    rom_name: str
    platform_id: int
    platform_name: str
    platform_slug: str
    path_cover_small: str | None
    download_count: int
    last_downloaded_at: UTCDatetime | None
    file_size_bytes: int


class PlatformDownloadStat(TypedDict):
    platform_id: int
    platform_name: str
    platform_slug: str
    download_count: int
    size_bytes: int


class DownloadSourceStat(TypedDict):
    source: str
    count: int


class DownloadTimelinePoint(TypedDict):
    date: str
    count: int
    size_bytes: int


class DownloadStatsSummary(TypedDict):
    total_downloads: int
    total_bytes: int
    downloads_in_window: int
    bytes_in_window: int
    unique_roms_downloaded: int
    unique_users: int
    roms_total: int
    never_downloaded_count: int
    never_downloaded_bytes: int


class DownloadStatsOverview(TypedDict):
    summary: DownloadStatsSummary
    top_roms: list[TopDownloadedRom]
    by_platform: list[PlatformDownloadStat]
    by_source: list[DownloadSourceStat]
    timeline: list[DownloadTimelinePoint]
