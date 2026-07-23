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

    assert loader.config.EXCLUDED_PLATFORMS == sorted({*DEFAULT_EXCLUDED_DIRS, "romm"})
    assert loader.config.EXCLUDED_SINGLE_EXT == sorted(
        {
            *(e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS),
            "xml",
        }
    )
    assert loader.config.EXCLUDED_SINGLE_FILES == sorted(
        {*DEFAULT_EXCLUDED_FILES, "info.txt"}
    )
    assert loader.config.EXCLUDED_MULTI_FILES == sorted(
        {
            *DEFAULT_EXCLUDED_DIRS,
            "my_multi_file_game",
            "DLC",
        }
    )
    assert loader.config.EXCLUDED_MULTI_PARTS_EXT == sorted(
        {
            *(e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS),
            "txt",
        }
    )
    assert loader.config.EXCLUDED_MULTI_PARTS_FILES == sorted(
        {
            *DEFAULT_EXCLUDED_FILES,
            "data.xml",
        }
    )
    assert loader.config.PLATFORMS_BINDING == {"gc": "ngc"}
    assert loader.config.PLATFORMS_VERSIONS == {"naomi": "arcade"}
    assert loader.config.ROMS_FOLDER_NAME == "ROMS"
    assert loader.config.FIRMWARE_FOLDER_NAME == "BIOS"
    assert loader.config.SKIP_HASH_CALCULATION
    assert loader.config.EJS_DEBUG
    assert loader.config.EJS_DISABLE_AUTO_UNLOAD
    assert loader.config.EJS_DISABLE_BATCH_BOOTUP
    assert loader.config.EJS_CACHE_LIMIT == 1000
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
    assert loader.config.SCAN_ARTWORK_PRIORITY_OVERRIDES == {
        "url_cover": ["ss", "tgdb"],
        "url_screenshots": ["igdb"],
    }
    assert loader.config.SCAN_REGION_PRIORITY == ["jp", "eu", "wor"]
    assert loader.config.SCAN_REGION_MODE == "prefer_config"
    assert loader.config.SCAN_LANGUAGE_PRIORITY == ["jp", "es"]
    assert loader.config.GAMELIST_MEDIA_THUMBNAIL == "box3d"
    assert loader.config.GAMELIST_MEDIA_IMAGE == "title_screen"


def test_scan_priority_sources_match_metadata_source_enum():
    """VALID_SCAN_PRIORITY_SOURCES duplicates MetadataSource to avoid a circular
    import; guard against the two drifting apart."""
    from config.config_manager import VALID_SCAN_PRIORITY_SOURCES
    from handler.scan_handler import MetadataSource

    assert VALID_SCAN_PRIORITY_SOURCES == {source.value for source in MetadataSource}


def test_empty_config_loader():
    loader = ConfigManager(
        os.path.join(
            Path(__file__).resolve().parent, "fixtures", "config/empty_config.yml"
        )
    )

    assert loader.config.EXCLUDED_PLATFORMS == sorted(DEFAULT_EXCLUDED_DIRS)
    assert loader.config.EXCLUDED_SINGLE_EXT == sorted(
        {e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS}
    )
    assert loader.config.EXCLUDED_SINGLE_FILES == sorted(DEFAULT_EXCLUDED_FILES)
    assert loader.config.EXCLUDED_MULTI_FILES == sorted(DEFAULT_EXCLUDED_DIRS)
    assert loader.config.EXCLUDED_MULTI_PARTS_EXT == sorted(
        {e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS}
    )
    assert loader.config.EXCLUDED_MULTI_PARTS_FILES == sorted(DEFAULT_EXCLUDED_FILES)
    assert loader.config.PLATFORMS_BINDING == {}
    assert loader.config.PLATFORMS_VERSIONS == {}
    assert loader.config.ROMS_FOLDER_NAME == "roms"
    assert loader.config.FIRMWARE_FOLDER_NAME == "bios"
    assert not loader.config.SKIP_HASH_CALCULATION
    assert not loader.config.EJS_DEBUG
    assert loader.config.EJS_CACHE_LIMIT is None
    assert not loader.config.EJS_DISABLE_AUTO_UNLOAD
    assert not loader.config.EJS_DISABLE_BATCH_BOOTUP
    assert not loader.config.EJS_NETPLAY_ENABLED
    assert loader.config.EJS_NETPLAY_ICE_SERVERS == []
    assert loader.config.EJS_SETTINGS == {}
    assert loader.config.EJS_CONTROLS == {}
    assert loader.config.SCAN_ARTWORK_PRIORITY_OVERRIDES == {}
    assert loader.config.SCAN_REGION_MODE == "prefer_rom_tags"
    assert loader.config.GAMELIST_MEDIA_THUMBNAIL == "box2d"
    assert loader.config.GAMELIST_MEDIA_IMAGE == "screenshot"


def test_missing_config_file_is_created(tmp_path):
    config_file = tmp_path / "config" / "config.yml"

    loader = ConfigManager(str(config_file))

    assert config_file.parent.exists()
    assert config_file.exists()
    assert config_file.read_text() == ""
    assert loader.config.CONFIG_FILE_MOUNTED
    assert loader.config.CONFIG_FILE_WRITABLE


def test_forward_compat_unknown_values_are_tolerated():
    """A newer release may ship sample configs that reference media types
    this version doesn't yet recognize. The loader should drop unknowns and
    fall back to defaults rather than exiting."""
    loader = ConfigManager(
        os.path.join(
            Path(__file__).resolve().parent,
            "fixtures",
            "config/forward_compat_config.yml",
        )
    )

    # Unknown entries in scan.media are filtered out; known ones survive.
    assert loader.config.SCAN_MEDIA == ["box2d", "screenshot"]
    # Unknown thumbnail/image values fall back to their defaults.
    assert loader.config.GAMELIST_MEDIA_THUMBNAIL == "box2d"
    assert loader.config.GAMELIST_MEDIA_IMAGE == "screenshot"
    # Unknown region_mode values fall back to the default.
    assert loader.config.SCAN_REGION_MODE == "prefer_rom_tags"


def test_malformed_yaml_falls_back_to_defaults():
    """A YAML parse error should log critically and leave the app on
    defaults, not crash."""
    loader = ConfigManager(
        os.path.join(
            Path(__file__).resolve().parent,
            "fixtures",
            "config/malformed_config.yml",
        )
    )

    assert loader.config.ROMS_FOLDER_NAME == "roms"
    assert loader.config.FIRMWARE_FOLDER_NAME == "bios"
    assert loader.config.SCAN_MEDIA == ["box2d", "screenshot", "manual"]
    # The parse error is surfaced so the UI can warn the user their whole
    # config (not just the broken part) was discarded.
    assert loader.config.CONFIG_FILE_PARSE_ERROR is not None


def test_valid_config_has_no_parse_error():
    """A syntactically valid config should not report a parse error."""
    loader = ConfigManager(
        os.path.join(Path(__file__).resolve().parent, "fixtures", "config/config.yml")
    )

    assert loader.config.CONFIG_FILE_PARSE_ERROR is None


def test_mixed_gamelist_syntax_surfaces_parse_error(tmp_path):
    """Regression for #3708: mixing the old (`scan.export`) and new
    (`scan.gamelist.export`) syntax produces invalid YAML. The whole config is
    discarded and defaults are used, so the parse error must be surfaced rather
    than silently swallowed."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "scan:\n"
        "  gamelist:\n"
        "    export: true\n"
        "  - gamelist_xml: true\n"
        "  media:\n"
        "    - box2d\n"
        "    - video\n"
        "    - manual\n"
    )

    loader = ConfigManager(str(config_file))

    assert loader.config.CONFIG_FILE_PARSE_ERROR is not None
    # The user's scan.media list is lost, falling back to defaults.
    assert loader.config.SCAN_MEDIA == ["box2d", "screenshot", "manual"]


def test_parse_error_is_cleared_when_config_is_missing(tmp_path):
    """A stale parse error from a malformed config must not persist once the
    file is gone. The loader is a singleton, so a later reload that skips YAML
    parsing (e.g. the file was deleted) has to clear the flag."""
    config_file = tmp_path / "config.yml"
    config_file.write_text("scan:\n  - broken: true\n  media: [box2d]\n")

    loader = ConfigManager(str(config_file))
    assert loader.config.CONFIG_FILE_PARSE_ERROR is not None

    # get_config's FileNotFoundError branch must clear the stale error.
    config_file.unlink()
    loader.get_config()
    assert loader.config.CONFIG_FILE_PARSE_ERROR is None


def test_parse_error_is_cleared_when_config_is_recreated(tmp_path):
    """Reloading via a missing file goes through _create_missing_config_file,
    which must also clear a stale parse error from a prior malformed load."""
    broken_file = tmp_path / "config.yml"
    broken_file.write_text("scan:\n  - broken: true\n  media: [box2d]\n")

    ConfigManager(str(broken_file))

    # Reusing the singleton with a missing path exercises the __init__
    # FileNotFoundError -> _create_missing_config_file recreate path.
    broken_file.unlink()
    loader = ConfigManager(str(broken_file))

    assert loader.config.CONFIG_FILE_PARSE_ERROR is None


def test_config_updates_serialize_gamelist_media_as_plain_strings(tmp_path):
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "scan:\n"
        "  gamelist:\n"
        "    media:\n"
        "      thumbnail: box2d\n"
        "      image: screenshot\n"
    )
    loader = ConfigManager(str(config_file))
    loader.add_platform_binding("atarist", "atari-st")

    config_text = config_file.read_text()
    assert "!!python/object" not in config_text
    assert "thumbnail: box2d" in config_text
    assert "image: screenshot" in config_text

    reloaded = ConfigManager(str(config_file))
    assert reloaded.config.PLATFORMS_BINDING == {"atarist": "atari-st"}


def test_update_scan_settings_round_trip(tmp_path):
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "scan:\n  priority:\n    region_mode: prefer_config\n  media:\n    - box2d\n"
    )
    loader = ConfigManager(str(config_file))

    loader.update_scan_settings(
        metadata_priority=["ss", "igdb"],
        artwork_priority=["igdb", "ss"],
        artwork_overrides={"cover": ["ss"], "screenshot": None, "manual": None},
        region_priority=["jp", "us"],
        language_priority=["ja", "en"],
        media=["box2d", "screenshot", "manual"],
        gamelist_export=True,
        gamelist_thumbnail="box3d",
        gamelist_image="title_screen",
        pegasus_export=True,
    )

    config_text = config_file.read_text()
    assert "!!python/object" not in config_text

    reloaded = ConfigManager(str(config_file))
    assert reloaded.config.SCAN_METADATA_PRIORITY == ["ss", "igdb"]
    assert reloaded.config.SCAN_ARTWORK_PRIORITY == ["igdb", "ss"]
    # Only the "cover" override was provided; the others fall back to artwork.
    assert reloaded.config.SCAN_ARTWORK_PRIORITY_OVERRIDES == {"url_cover": ["ss"]}
    assert reloaded.config.SCAN_REGION_PRIORITY == ["jp", "us"]
    # region_mode is not runtime-editable but must survive the rewrite.
    assert reloaded.config.SCAN_REGION_MODE == "prefer_config"
    assert reloaded.config.SCAN_LANGUAGE_PRIORITY == ["ja", "en"]
    assert reloaded.config.SCAN_MEDIA == ["box2d", "screenshot", "manual"]
    assert reloaded.config.GAMELIST_AUTO_EXPORT_ON_SCAN is True
    assert reloaded.config.GAMELIST_MEDIA_THUMBNAIL == "box3d"
    assert reloaded.config.GAMELIST_MEDIA_IMAGE == "title_screen"
    assert reloaded.config.PEGASUS_AUTO_EXPORT_ON_SCAN is True


def test_config_update_preserves_streaming_section(tmp_path):
    """A runtime write (e.g. saving scan settings) must not drop the
    streaming section, which isn't otherwise re-serialized."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "streaming:\n"
        "  enabled: true\n"
        "  containers:\n"
        "    - platform: ps2\n"
        "      host: https://192.168.1.51:3001\n"
        "      broker_host: http://192.168.1.51:8000\n"
        "      label: PCSX2\n"
    )
    loader = ConfigManager(str(config_file))
    assert loader.config.STREAMING_ENABLED

    loader.add_platform_binding("gc", "ngc")

    reloaded = ConfigManager(str(config_file))
    assert reloaded.config.STREAMING_ENABLED
    assert reloaded.config.STREAMING_CONTAINERS == [
        {
            "platform": "ps2",
            "host": "https://192.168.1.51:3001",
            "broker_host": "http://192.168.1.51:8000",
            "label": "PCSX2",
        }
    ]
