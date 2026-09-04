from pathlib import Path

import pytest
import yaml

from config.config_manager import Config
from utils.platform_aliases import (
    PLATFORM_FS_ALIASES,
    PLATFORM_SLUG_FOLDERS,
    resolve_fs_slug,
    resolve_platform_slug,
)
from utils.platform_slugs import UniversalPlatformSlug as UPS

EXAMPLE_CONFIGS = sorted((Path(__file__).parents[3] / "examples").glob("config.*.yml"))


def _config(
    bindings: dict[str, str] | None = None,
    versions: dict[str, str] | None = None,
) -> Config:
    return Config(
        PLATFORMS_BINDING=bindings or {},
        PLATFORMS_VERSIONS=versions or {},
    )


def test_alias_keys_are_not_slugs():
    """An alias for a folder name that already is a slug could never be reached."""
    assert not [k for k in PLATFORM_FS_ALIASES if k in UPS]


def test_alias_keys_are_lowercase():
    assert all(k == k.lower() for k in PLATFORM_FS_ALIASES)


def test_resolves_frontend_folder_names():
    config = _config()
    assert resolve_platform_slug("gamecube", config) == "ngc"
    assert resolve_platform_slug("megadrive", config) == "genesis"
    assert resolve_platform_slug("n3ds", config) == "3ds"
    assert resolve_platform_slug("GameCube", config) == "ngc"


def test_folder_without_alias_passes_through():
    config = _config()
    # atari800 is a Batocera folder name that is also a RomM slug, so it can
    # only be remapped through a config binding.
    assert resolve_platform_slug("atari800", config) == "atari800"
    assert resolve_platform_slug("my-custom-folder", config) == "my-custom-folder"


def test_resolves_easyrpg_to_rpg_maker():
    """Batocera, RetroBat and ES-DE all name the RPG Maker folder after the engine."""
    assert resolve_platform_slug("easyrpg", _config()) == UPS.RPG_MAKER.value
    assert resolve_fs_slug(UPS.RPG_MAKER.value, _config()) == "easyrpg"


def test_binding_and_version_win_over_alias():
    bound = _config(bindings={"gamecube": "arcade"})
    assert resolve_platform_slug("gamecube", bound) == "arcade"

    versioned = _config(versions={"gamecube": "wii"})
    assert resolve_platform_slug("gamecube", versioned) == "wii"

    both = _config(bindings={"gamecube": "arcade"}, versions={"gamecube": "wii"})
    assert resolve_platform_slug("gamecube", both) == "arcade"


def test_resolution_is_case_insensitive():
    config = _config(bindings={"gamecube": "arcade"})
    assert resolve_platform_slug("GameCube", config) == "arcade"
    assert resolve_platform_slug("SNES", _config()) == "snes"


def test_resolves_slug_back_to_folder_name():
    assert resolve_fs_slug("dc", _config()) == "dreamcast"
    assert resolve_fs_slug("wii", _config(bindings={"wiiware": "wii"})) == "wiiware"


def test_slug_reached_by_several_folders_has_no_reverse():
    """amiga500, amiga600 and amiga1200 all resolve to amiga, so none is canonical."""
    assert resolve_fs_slug("amiga", _config()) is None
    assert resolve_fs_slug("ngc", _config()) is None
    assert resolve_fs_slug("my-custom-slug", _config()) is None


def test_reverse_map_agrees_with_alias_table():
    for slug, fs_slug in PLATFORM_SLUG_FOLDERS.items():
        assert PLATFORM_FS_ALIASES[fs_slug].value == slug


@pytest.mark.parametrize("config_file", EXAMPLE_CONFIGS, ids=lambda p: p.name)
def test_example_configs_list_only_needed_overrides(config_file: Path):
    """Every example entry must be one the alias table cannot resolve on its own."""
    raw = yaml.safe_load(config_file.read_text()) or {}
    platforms = (raw.get("system") or {}).get("platforms") or {}
    empty = _config()

    redundant = {
        fs_slug: slug
        for fs_slug, slug in platforms.items()
        if resolve_platform_slug(fs_slug, empty) == slug
    }
    assert not redundant
