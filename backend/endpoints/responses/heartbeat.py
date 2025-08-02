from typing import TypedDict


class SystemDict(TypedDict):
    VERSION: str
    SHOW_SETUP_WIZARD: bool


class MetadataSourcesDict(TypedDict):
    ANY_SOURCE_ENABLED: bool
    IGDB_API_ENABLED: bool
    MOBY_API_ENABLED: bool
    SS_API_ENABLED: bool
    STEAMGRIDDB_API_ENABLED: bool
    RA_API_ENABLED: bool
    LAUNCHBOX_API_ENABLED: bool
    PLAYMATCH_API_ENABLED: bool
    HASHEOUS_API_ENABLED: bool
    TGDB_API_ENABLED: bool


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


class HeartbeatResponse(TypedDict):
    SYSTEM: SystemDict
    METADATA_SOURCES: MetadataSourcesDict
    FILESYSTEM: FilesystemDict
    EMULATION: EmulationDict
    FRONTEND: FrontendDict
    OIDC: OIDCDict
