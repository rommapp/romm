from typing import TypedDict


class SystemDict(TypedDict):
    VERSION: str
    SHOW_SETUP_WIZARD: bool


class WatcherDict(TypedDict):
    ENABLED: bool
    TITLE: str
    MESSAGE: str


class TaskDict(WatcherDict):
    CRON: str


class SchedulerDict(TypedDict):
    RESCAN: TaskDict
    SWITCH_TITLEDB: TaskDict


class MetadataSourcesDict(TypedDict):
    ANY_SOURCE_ENABLED: bool
    IGDB_API_ENABLED: bool
    MOBY_API_ENABLED: bool
    STEAMGRIDDB_ENABLED: bool


class FilesystemDict(TypedDict):
    FS_PLATFORMS: list[str]


class EmulationDict(TypedDict):
    DISABLE_EMULATOR_JS: bool
    DISABLE_RUFFLE_RS: bool


class FrontendDict(TypedDict):
    UPLOAD_TIMEOUT: int


class OIDCDict(TypedDict):
    ENABLED: bool
    PROVIDER: str


class HeartbeatResponse(TypedDict):
    SYSTEM: SystemDict
    WATCHER: WatcherDict
    SCHEDULER: SchedulerDict
    METADATA_SOURCES: MetadataSourcesDict
    FILESYSTEM: FilesystemDict
    EMULATION: EmulationDict
    FRONTEND: FrontendDict
    OIDC: OIDCDict
