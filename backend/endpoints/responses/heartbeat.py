from typing_extensions import TypedDict


class ConfigDict(TypedDict):
    EXCLUDED_PLATFORMS: list[str]
    EXCLUDED_SINGLE_EXT: list[str]
    EXCLUDED_SINGLE_FILES: list[str]
    EXCLUDED_MULTI_FILES: list[str]
    EXCLUDED_MULTI_PARTS_EXT: list[str]
    EXCLUDED_MULTI_PARTS_FILES: list[str]
    PLATFORMS_BINDING: dict[str, str]
    ROMS_FOLDER_NAME: str
    SAVES_FOLDER_NAME: str
    STATES_FOLDER_NAME: str
    SCREENSHOTS_FOLDER_NAME: str
    HIGH_PRIO_STRUCTURE_PATH: str


class WatcherDict(TypedDict):
    ENABLED: bool
    TITLE: str
    MESSAGE: str


class TaskDict(WatcherDict):
    CRON: str


class SchedulerDict(TypedDict):
    RESCAN: TaskDict
    SWITCH_TITLEDB: TaskDict
    MAME_XML: TaskDict


class HeartbeatReturn(TypedDict):
    VERSION: str
    NEW_VERSION: str
    ROMM_AUTH_ENABLED: bool
    WATCHER: WatcherDict
    SCHEDULER: SchedulerDict
    CONFIG: ConfigDict
