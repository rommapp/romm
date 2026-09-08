import logging
import os
from pathlib import Path

import pytest

from config.config_manager import (
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FILES,
    DEFAULT_EXCLUDED_MULTI_FILE_DIRS,
    DEFAULT_EXCLUDED_PLATFORM_DIRS,
    ConfigManager,
    parse_firmware_template,
    parse_platform_templates,
    parse_structure_template,
)


def test_config_loader():
    loader = ConfigManager(
        os.path.join(Path(__file__).resolve().parent, "fixtures", "config/config.yml")
    )

    assert loader.config.EXCLUDED_PLATFORMS == sorted(
        {*DEFAULT_EXCLUDED_PLATFORM_DIRS, "romm"}
    )
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
            *DEFAULT_EXCLUDED_MULTI_FILE_DIRS,
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
    assert loader.config.SKIP_HASH_CALCULATION
    assert loader.config.EJS_DEBUG
    assert loader.config.EJS_DISABLE_AUTO_UNLOAD
    assert loader.config.EJS_DISABLE_BATCH_BOOTUP
    assert loader.config.EJS_ENABLE_AUTO_SAVE_SYNC
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
    assert loader.config.STRUCTURE_TEMPLATES == {
        "default": "ROMS/{platform}/{game}",
        "firmware": "BIOS/{platform}",
        "psx": "ROMS/{platform}/{category}/{game}",
        "nes": ["ROMS/{platform}/{game}", "ROMS/{platform}/{category}/{game}"],
    }
    assert loader.config.default_structure.platform_dir == ("ROMS",)
    assert loader.config.platforms_dir == "ROMS"
    assert loader.config.firmware_structure.platform_path("psx") == "BIOS/psx"

    # The accessor parses templates on demand.
    psx = loader.config.platform_structure("psx")
    assert len(psx) == 1
    assert psx[0].platform_path("psx") == "ROMS/psx"
    assert len(psx[0].levels) == 1 and psx[0].levels[0].literal is None
    # The list form yields one structure per template (union on discovery).
    nes = loader.config.platform_structure("nes")
    assert len(nes) == 2
    assert nes[0].levels == ()
    assert len(nes[1].levels) == 1 and nes[1].levels[0].literal is None
    # A platform without an override falls back to the library-wide layout.
    assert loader.config.platform_structure("snes") == (
        loader.config.default_structure,
    )


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

    assert loader.config.EXCLUDED_PLATFORMS == sorted(DEFAULT_EXCLUDED_PLATFORM_DIRS)
    assert loader.config.EXCLUDED_SINGLE_EXT == sorted(
        {e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS}
    )
    assert "ini" not in loader.config.EXCLUDED_SINGLE_EXT
    assert loader.config.EXCLUDED_SINGLE_FILES == sorted(DEFAULT_EXCLUDED_FILES)
    assert loader.config.EXCLUDED_MULTI_FILES == sorted(
        DEFAULT_EXCLUDED_MULTI_FILE_DIRS
    )
    assert loader.config.EXCLUDED_MULTI_PARTS_EXT == sorted(
        {e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS}
    )
    assert "ini" not in loader.config.EXCLUDED_MULTI_PARTS_EXT
    assert loader.config.EXCLUDED_MULTI_PARTS_FILES == sorted(DEFAULT_EXCLUDED_FILES)
    assert loader.config.PLATFORMS_BINDING == {}
    assert loader.config.PLATFORMS_VERSIONS == {}
    assert loader.config.platforms_dir == "roms"
    assert loader.config.firmware_structure.platform_path("nes") == "bios/nes"
    assert not loader.config.SKIP_HASH_CALCULATION
    assert not loader.config.EJS_DEBUG
    assert loader.config.EJS_CACHE_LIMIT is None
    assert not loader.config.EJS_DISABLE_AUTO_UNLOAD
    assert not loader.config.EJS_DISABLE_BATCH_BOOTUP
    assert not loader.config.EJS_ENABLE_AUTO_SAVE_SYNC
    assert not loader.config.EJS_NETPLAY_ENABLED
    assert loader.config.EJS_NETPLAY_ICE_SERVERS == []
    assert loader.config.EJS_SETTINGS == {}
    assert loader.config.EJS_CONTROLS == {}
    assert loader.config.SCAN_ARTWORK_PRIORITY_OVERRIDES == {}
    assert loader.config.SCAN_REGION_MODE == "prefer_rom_tags"
    assert loader.config.GAMELIST_MEDIA_THUMBNAIL == "box2d"
    assert loader.config.GAMELIST_MEDIA_IMAGE == "screenshot"
    assert loader.config.STRUCTURE_TEMPLATES == {}


@pytest.mark.parametrize(
    ("template", "platform_dir", "levels"),
    [
        ("{platform}/{game}", (), ()),
        ("roms/{platform}/{game}", ("roms",), ()),
        ("roms/{platform}/{category}/{game}", ("roms",), (None,)),
        ("roms/{platform}/Hacks/{game}", ("roms",), ("Hacks",)),
        (
            "games/all/{platform}/{region}/{system}/{game}",
            ("games", "all"),
            (None, None),
        ),
    ],
)
def test_parse_structure_template_valid(template, platform_dir, levels):
    structure = parse_structure_template(template)
    assert structure.platform_dir == platform_dir
    assert tuple(level.literal for level in structure.levels) == levels


def test_parse_structure_template_accepts_the_platform_folder_by_name():
    """A per-platform override may name the folder outright instead of using the
    macro, which is how the key already reads."""
    structure = parse_structure_template("roms/ps3/{category}/{game}", fs_slug="ps3")
    assert structure.platform_dir == ("roms",)
    assert structure.platform_path("ps3") == "roms/ps3"


@pytest.mark.parametrize(
    "template",
    [
        "",
        "justliteral",
        "roms/{platform}",  # no terminal
        "roms/{platform}/{category}",  # no terminal
        "roms/{game}",  # no platform folder
        "{game}/roms/{platform}",  # terminal not last
        "roms/{platform}/{game}/extra",  # terminal not last
        "roms/{platform}/{platform}/{game}",  # platform folder twice
        "{category}/{platform}/{game}",  # wildcard above the platform folder
        "{library}/roms/{platform}/{game}",  # macro RomM resolves itself
        "roms/{platform}/{}/{game}",  # empty macro
        "roms/{platform}/{gameFile}",  # the terminal is spelled {game}
    ],
)
def test_parse_structure_template_invalid(template):
    with pytest.raises(ValueError):
        parse_structure_template(template)


@pytest.mark.parametrize(
    ("template", "platform_dir", "subdir"),
    [
        ("bios/{platform}", ("bios",), ()),
        ("{platform}/bios", (), ("bios",)),
        ("{platform}/firmware/bios", (), ("firmware", "bios")),
    ],
)
def test_parse_firmware_template_valid(template, platform_dir, subdir):
    template_parsed = parse_firmware_template(template)
    assert template_parsed.platform_dir == platform_dir
    assert template_parsed.subdir == subdir


@pytest.mark.parametrize(
    "template",
    [
        "",
        "bios",  # no platform folder
        "bios/{platform}/{game}",  # firmware is a folder, not a set of games
        "bios/{platform}/{region}",  # no wildcard levels
    ],
)
def test_parse_firmware_template_invalid(template):
    with pytest.raises(ValueError):
        parse_firmware_template(template)


def test_structure_templates_are_keyed_case_insensitively(monkeypatch, tmp_path):
    """`system.platforms` lowercases its folder names, so `filesystem.structure`
    has to as well or the same key works in one block and not the other."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "filesystem:\n  structure:\n"
        "    'Atari - 2600': 'roms/{platform}/Hacks/{game}'\n"
    )
    config = ConfigManager(str(config_file)).get_config()

    for key in ("Atari - 2600", "atari - 2600"):
        structure = config.platform_structure(key)
        assert len(structure) == 1
        assert structure[0].levels[0].literal == "Hacks"


def test_parse_platform_templates_string_and_list():
    # A bare string yields a single structure.
    single = parse_platform_templates("roms/{platform}/{game}")
    assert len(single) == 1 and single[0].levels == ()

    # A list yields one structure per template, preserving order.
    multi = parse_platform_templates(
        ["roms/{platform}/{game}", "roms/{platform}/{category}/{game}"]
    )
    assert len(multi) == 2
    assert multi[0].levels == ()
    assert len(multi[1].levels) == 1 and multi[1].levels[0].literal is None


def test_parse_platform_templates_propagates_invalid():
    with pytest.raises(ValueError):
        parse_platform_templates(["roms/{platform}/{game}", "nope"])


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


def test_non_string_region_mode_falls_back_to_default(tmp_path):
    """A list/mapping region_mode is unhashable and must not crash the
    membership check against the valid-modes set."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "scan:\n  priority:\n    region_mode:\n      - prefer_config\n"
    )
    loader = ConfigManager(str(config_file))

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

    assert loader.config.platforms_dir == "roms"
    assert loader.config.firmware_structure.platform_path("nes") == "bios/nes"
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


def test_legacy_streaming_container_logs_deprecation_warning(caplog, tmp_path):
    """A container without `protocol: webstation` is the deprecated
    per-emulator broker shape and must warn, not fail, so it keeps working
    for one more release while pointing operators at the migration guide."""
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
    # The "romm" logger has propagate=False, so caplog's handler must be
    # added directly to it rather than relying on root-logger propagation.
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="romm"):
            loader = ConfigManager(str(config_file))
    finally:
        romm_logger.removeHandler(caplog.handler)

    assert loader.config.STREAMING_CONTAINERS
    assert "deprecated" in caplog.text
    assert "emulator-streaming-migration" in caplog.text


def test_webstation_streaming_container_does_not_warn(caplog, tmp_path):
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "streaming:\n"
        "  enabled: true\n"
        "  containers:\n"
        "    - host: https://192.168.1.56:3010\n"
        "      protocol: webstation\n"
        "      subfolder: /streaming\n"
        "      label: Emulation station\n"
        "      platforms:\n"
        "        ps2: pcsx2\n"
    )
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="romm"):
            ConfigManager(str(config_file))
    finally:
        romm_logger.removeHandler(caplog.handler)

    assert "deprecated" not in caplog.text


def test_config_update_preserves_nested_container_platforms(tmp_path):
    """A container's `platforms` map is the only nested mapping inside the
    containers list, so it is the shape a runtime rewrite could flatten."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        "streaming:\n"
        "  enabled: true\n"
        "  containers:\n"
        "    - host: https://192.168.1.51:3001\n"
        "      broker_host: http://192.168.1.51:8000\n"
        "      label: WEBSTATION\n"
        "      platforms:\n"
        "        ps2: pcsx2\n"
        "        ngc: dolphin\n"
    )
    loader = ConfigManager(str(config_file))
    loader.add_platform_binding("gc", "ngc")

    reloaded = ConfigManager(str(config_file))
    assert reloaded.config.STREAMING_CONTAINERS == [
        {
            "host": "https://192.168.1.51:3001",
            "broker_host": "http://192.168.1.51:8000",
            "label": "WEBSTATION",
            "platforms": {"ps2": "pcsx2", "ngc": "dolphin"},
        }
    ]


def _write_config(tmp_path: Path, system_block: str) -> ConfigManager:
    config_file = tmp_path / "config.yml"
    config_file.write_text(f"system:\n{system_block}")
    return ConfigManager(str(config_file))


def test_platform_folder_names_are_lowercased(tmp_path):
    loader = _write_config(
        tmp_path,
        '  platforms:\n    GameCube: "ngc"\n  versions:\n    NAOMI: "arcade"\n',
    )

    assert loader.config.PLATFORMS_BINDING == {"gamecube": "ngc"}
    assert loader.config.PLATFORMS_VERSIONS == {"naomi": "arcade"}


def test_null_platforms_block_means_empty(tmp_path):
    loader = _write_config(tmp_path, "  platforms:\n  versions:\n")

    assert loader.config.PLATFORMS_BINDING == {}
    assert loader.config.PLATFORMS_VERSIONS == {}


@pytest.mark.parametrize("value", ['""', "5", "~"])
def test_platform_binding_must_be_a_non_empty_string(tmp_path, value):
    with pytest.raises(SystemExit) as excinfo:
        _write_config(tmp_path, f"  platforms:\n    gamecube: {value}\n")

    assert excinfo.value.code == 3


def test_platform_binding_lookup_ignores_case(tmp_path):
    loader = _write_config(tmp_path, '  platforms:\n    GameCube: "ngc"\n')

    loader.remove_platform_binding("GAMECUBE")
    assert loader.config.PLATFORMS_BINDING == {}


@pytest.fixture
def critical(mocker):
    """The last message the config manager logged before exiting."""
    spy = mocker.patch("config.config_manager.log.critical")
    return lambda: str(spy.call_args[0][0])


def _write_filesystem_config(tmp_path: Path, block: str) -> ConfigManager:
    config_file = tmp_path / "config.yml"
    config_file.write_text(f"filesystem:\n{block}")
    return ConfigManager(str(config_file))


@pytest.mark.parametrize(
    ("key", "folder", "expected"),
    [
        ("roms_folder", "retro_games", 'default: "retro_games/{platform}/{game}"'),
        ("firmware_folder", "fw", 'firmware: "fw/{platform}"'),
    ],
)
def test_retired_folder_keys_exit_with_the_replacement(
    tmp_path, key, folder, expected, critical
):
    """Ignoring them would silently relocate the library, so refuse to start and
    name the template that reproduces the layout."""
    with pytest.raises(SystemExit) as excinfo:
        _write_filesystem_config(tmp_path, f"  {key}: {folder}\n")

    assert excinfo.value.code == 3
    assert expected in critical()


def test_an_override_may_not_move_the_platform_folder(tmp_path, critical):
    """A platform outside the folder platforms are enumerated in would never be
    discovered."""
    with pytest.raises(SystemExit) as excinfo:
        _write_filesystem_config(
            tmp_path,
            "  structure:\n"
            '    default: "roms/{platform}/{game}"\n'
            '    ps3: "disc-games/{platform}/{game}"\n',
        )

    assert excinfo.value.code == 3
    assert "disc-games" in critical()


@pytest.mark.parametrize("key", ["default", "firmware"])
def test_a_reserved_structure_key_takes_a_single_template(tmp_path, key):
    """Only a platform can union several layouts; the library has just one."""
    with pytest.raises(SystemExit) as excinfo:
        _write_filesystem_config(
            tmp_path,
            f'  structure:\n    {key}:\n      - "roms/{{platform}}/{{game}}"\n',
        )

    assert excinfo.value.code == 3


def test_an_invalid_firmware_template_is_rejected(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        _write_filesystem_config(
            tmp_path, '  structure:\n    firmware: "bios/{platform}/{game}"\n'
        )

    assert excinfo.value.code == 3


def test_the_retired_library_layout_check_names_the_template(
    tmp_path, mocker, critical
):
    """A `{platform}/roms` library used to be auto-detected; now it has to say so
    rather than scan as empty and mark every rom missing."""
    library = tmp_path / "library"
    (library / "n64" / "roms").mkdir(parents=True)
    mocker.patch("config.config_manager.LIBRARY_BASE_PATH", str(library))

    loader = _write_filesystem_config(tmp_path, "  skip_hash_calculation: false\n")
    with pytest.raises(SystemExit) as excinfo:
        loader.check_library_layout()

    assert excinfo.value.code == 3
    assert 'default: "{platform}/roms/{game}"' in critical()


def test_the_retired_library_layout_check_passes_once_declared(tmp_path, mocker):
    library = tmp_path / "library"
    (library / "n64" / "roms").mkdir(parents=True)
    mocker.patch("config.config_manager.LIBRARY_BASE_PATH", str(library))

    loader = _write_filesystem_config(
        tmp_path, '  structure:\n    default: "{platform}/roms/{game}"\n'
    )
    loader.check_library_layout()


def test_a_platform_named_like_a_layout_key_uses_the_default(tmp_path):
    """`structure.firmware` is a firmware folder, not a template for a platform
    whose folder happens to be called `firmware`."""
    loader = _write_filesystem_config(
        tmp_path, '  structure:\n    firmware: "bios/{platform}"\n'
    )

    config = loader.get_config()
    assert config.platform_structure("firmware") == (config.default_structure,)
