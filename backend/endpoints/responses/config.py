from typing import TypedDict


class ConfigResponse(TypedDict):
    EXCLUDED_PLATFORMS: list[str]
    EXCLUDED_SINGLE_EXT: list[str]
    EXCLUDED_SINGLE_FILES: list[str]
    EXCLUDED_MULTI_FILES: list[str]
    EXCLUDED_MULTI_PARTS_EXT: list[str]
    EXCLUDED_MULTI_PARTS_FILES: list[str]
    PLATFORMS_BINDING: dict[str, str]
    PLATFORMS_VERSIONS: dict[str, str]
    ROMS_FOLDER_NAME: str
    FIRMWARE_FOLDER_NAME: str
    HIGH_PRIO_STRUCTURE_PATH: str
