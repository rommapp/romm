from typing import TypedDict


class SystemDict(TypedDict):
    VERSION: str
    SHOW_SETUP_WIZARD: bool


class MetadataSourcesDict(TypedDict):
    ANY_SOURCE_ENABLED: bool
    IGDB_API_ENABLED: bool
    SS_API_ENABLED: bool
    MOBY_API_ENABLED: bool
    STEAMGRIDDB_API_ENABLED: bool
    RA_API_ENABLED: bool
    LAUNCHBOX_API_ENABLED: bool
    HASHEOUS_API_ENABLED: bool
    PLAYMATCH_API_ENABLED: bool
    TGDB_API_ENABLED: bool
    FLASHPOINT_API_ENABLED: bool
    HLTB_API_ENABLED: bool


class FilesystemDict(TypedDict):
    FS_PLATFORMS: list[str]


class EmulationDict(TypedDict):
    DISABLE_EMULATOR_JS: bool
    DISABLE_RUFFLE_RS: bool


class FrontendDict(TypedDict):
    UPLOAD_TIMEOUT: int
    DISABLE_USERPASS_LOGIN: bool
    YOUTUBE_BASE_URL: str


class OIDCDict(TypedDict):
    ENABLED: bool
    PROVIDER: str


class TasksDict(TypedDict):
    ENABLE_SCHEDULED_RESCAN: bool
    SCHEDULED_RESCAN_CRON: str
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB: bool
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: str
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA: bool
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON: str
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP: bool
    SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON: str


class HeartbeatResponse(TypedDict):
    SYSTEM: SystemDict
    METADATA_SOURCES: MetadataSourcesDict
    FILESYSTEM: FilesystemDict
    EMULATION: EmulationDict
    FRONTEND: FrontendDict
    OIDC: OIDCDict
    TASKS: TasksDict
