import copy

from config.config_manager import Config
from config.config_manager import config_manager as cm
from utils.platform_aliases import PLATFORM_FS_ALIASES, resolve_platform_slug
from utils.platform_slugs import UniversalPlatformSlug as UPS


def _config(
    bindings: dict[str, str] | None = None,
    versions: dict[str, str] | None = None,
) -> Config:
    config = copy.copy(cm.get_config())
    config.PLATFORMS_BINDING = bindings or {}
    config.PLATFORMS_VERSIONS = versions or {}
    return config


def test_alias_keys_are_not_slugs():
    """An alias for a folder name that already is a slug could never be reached."""
    slugs = {slug.value for slug in UPS}
    assert not {k for k in PLATFORM_FS_ALIASES if k in slugs}


def test_alias_keys_are_lowercase():
    assert all(k == k.lower() for k in PLATFORM_FS_ALIASES)


def test_resolves_frontend_folder_names():
    config = _config()
    assert resolve_platform_slug("gamecube", config) == "ngc"
    assert resolve_platform_slug("megadrive", config) == "genesis"
    assert resolve_platform_slug("n3ds", config) == "3ds"
    assert resolve_platform_slug("GameCube", config) == "ngc"


def test_valid_slug_wins_over_alias():
    """atari800 is both a Batocera folder and a RomM slug; the slug wins."""
    assert resolve_platform_slug("atari800", _config()) == "atari800"


def test_unknown_folder_passes_through():
    assert resolve_platform_slug("my-custom-folder", _config()) == "my-custom-folder"


def test_binding_and_version_win_over_alias():
    bound = _config(bindings={"gamecube": "arcade"})
    assert resolve_platform_slug("gamecube", bound) == "arcade"

    versioned = _config(versions={"gamecube": "wii"})
    assert resolve_platform_slug("gamecube", versioned) == "wii"

    both = _config(bindings={"gamecube": "arcade"}, versions={"gamecube": "wii"})
    assert resolve_platform_slug("gamecube", both) == "arcade"
