from typing import TypedDict

from config.config_manager import EjsControls, NetplayICEServer


class ConfigResponse(TypedDict):
    CONFIG_FILE_MOUNTED: bool
    CONFIG_FILE_WRITABLE: bool
    EXCLUDED_PLATFORMS: list[str]
    EXCLUDED_SINGLE_EXT: list[str]
    EXCLUDED_SINGLE_FILES: list[str]
    EXCLUDED_MULTI_FILES: list[str]
    EXCLUDED_MULTI_PARTS_EXT: list[str]
    EXCLUDED_MULTI_PARTS_FILES: list[str]
    PLATFORMS_BINDING: dict[str, str]
    PLATFORMS_VERSIONS: dict[str, str]
    SKIP_HASH_CALCULATION: bool
    EJS_DEBUG: bool
    EJS_CACHE_LIMIT: int | None
    EJS_KEYBOARD_LOCK: bool
    EJS_DISABLE_AUTO_UNLOAD: bool
    EJS_DISABLE_BATCH_BOOTUP: bool
    EJS_NETPLAY_ENABLED: bool
    EJS_NETPLAY_ICE_SERVERS: list[NetplayICEServer]
    EJS_SETTINGS: dict[str, dict[str, str]]
    EJS_CONTROLS: dict[str, EjsControls]
    SCAN_METADATA_PRIORITY: list[str]
    SCAN_ARTWORK_PRIORITY: list[str]
    SCAN_REGION_PRIORITY: list[str]
    SCAN_LANGUAGE_PRIORITY: list[str]
    SCAN_MEDIA: list[str]
