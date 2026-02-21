import os
from pathlib import Path

from config.config_manager import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FILES,
    ConfigManager,
)


def test_config_loader():
    loader = ConfigManager(
        os.path.join(Path(__file__).resolve().parent, "fixtures", "config/config.yml")
    )

    assert loader.config.EXCLUDED_PLATFORMS == ["romm"]
    assert loader.config.EXCLUDED_SINGLE_EXT == ["xml"]
    assert loader.config.EXCLUDED_SINGLE_FILES == ["info.txt"]
    assert loader.config.EXCLUDED_MULTI_FILES == ["my_multi_file_game", "DLC"]
    assert loader.config.EXCLUDED_MULTI_PARTS_EXT == ["txt"]
    assert loader.config.EXCLUDED_MULTI_PARTS_FILES == ["data.xml"]
    assert loader.config.PLATFORMS_BINDING == {"gc": "ngc"}
    assert loader.config.PLATFORMS_VERSIONS == {"naomi": "arcade"}
    assert loader.config.ROMS_FOLDER_NAME == "ROMS"
    assert loader.config.FIRMWARE_FOLDER_NAME == "BIOS"
    assert loader.config.SKIP_HASH_CALCULATION
    assert loader.config.EJS_DEBUG
    assert loader.config.EJS_DISABLE_AUTO_UNLOAD
    assert loader.config.EJS_DISABLE_BATCH_BOOTUP
    assert loader.config.EJS_CACHE_LIMIT == 1000
    assert loader.config.EJS_KEYBOARD_LOCK
    assert loader.config.EJS_NETPLAY_ENABLED
    assert loader.config.EJS_NETPLAY_ICE_SERVERS == [
        {"urls": "stun:stun.relay.metered.ca:80"},
        {
            "urls": "turn:global.relay.metered.ca:80",
            "username": "user",
            "credential": "password",
        },
    ]
    assert loader.config.EJS_SETTINGS == {
        "parallel_n64": {"vsync": "disabled"},
        "snes9x": {"snes9x_region": "ntsc"},
    }
    assert loader.config.EJS_CONTROLS == {
        "snes9x": {
            "_0": {0: {"value": "x", "value2": "BUTTON_2"}},
            "_1": {},
            "_2": {},
            "_3": {},
        },
    }
    assert loader.config.SCAN_METADATA_PRIORITY == ["ss", "launchbox"]
    assert loader.config.SCAN_ARTWORK_PRIORITY == ["igdb", "ss"]
    assert loader.config.SCAN_REGION_PRIORITY == ["jp", "eu", "wor"]
    assert loader.config.SCAN_LANGUAGE_PRIORITY == ["jp", "es"]


def test_empty_config_loader():
    loader = ConfigManager(
        os.path.join(
            Path(__file__).resolve().parent, "fixtures", "config/empty_config.yml"
        )
    )

    assert loader.config.EXCLUDED_PLATFORMS == DEFAULT_EXCLUDED_DIRS
    assert loader.config.EXCLUDED_SINGLE_EXT == [
        e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS
    ]
    assert loader.config.EXCLUDED_SINGLE_FILES == DEFAULT_EXCLUDED_FILES
    assert loader.config.EXCLUDED_MULTI_FILES == DEFAULT_EXCLUDED_DIRS
    assert loader.config.EXCLUDED_MULTI_PARTS_EXT == [
        e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS
    ]
    assert loader.config.EXCLUDED_MULTI_PARTS_FILES == DEFAULT_EXCLUDED_FILES
    assert loader.config.PLATFORMS_BINDING == {}
    assert loader.config.PLATFORMS_VERSIONS == {}
    assert loader.config.ROMS_FOLDER_NAME == "roms"
    assert loader.config.FIRMWARE_FOLDER_NAME == "bios"
    assert not loader.config.SKIP_HASH_CALCULATION
    assert not loader.config.EJS_DEBUG
    assert loader.config.EJS_CACHE_LIMIT is None
    assert not loader.config.EJS_KEYBOARD_LOCK
    assert not loader.config.EJS_DISABLE_AUTO_UNLOAD
    assert not loader.config.EJS_DISABLE_BATCH_BOOTUP
    assert not loader.config.EJS_NETPLAY_ENABLED
    assert loader.config.EJS_NETPLAY_ICE_SERVERS == []
    assert loader.config.EJS_SETTINGS == {}
    assert loader.config.EJS_CONTROLS == {}
