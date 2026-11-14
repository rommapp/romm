from pathlib import Path

import pytest
import yaml

from config.config_manager import Config
from utils.platform_aliases import (
    PLATFORM_FS_ALIASES,
    PLATFORM_SLUG_FOLDERS,
    resolve_builtin_platform_slug,
    resolve_fs_folder,
    resolve_fs_slug,
    resolve_platform_slug,
    unknown_binding_warning,
    unknown_binding_warnings,
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


def test_resolves_zc_folders_to_zelda_classic():
    """zc210 (Batocera/libretro 2.10) and zc250 (2.50) both map to Zelda Classic."""
    assert resolve_platform_slug("zc210", _config()) == UPS.ZELDA_CLASSIC.value
    assert resolve_platform_slug("zc250", _config()) == UPS.ZELDA_CLASSIC.value
    # Two folder names map here, so no single reverse folder is canonical.
    assert resolve_fs_slug(UPS.ZELDA_CLASSIC.value, _config()) is None


def test_resolves_easyrpg_to_rpg_maker():
    """Batocera, RetroBat and ES-DE all name the RPG Maker folder after the engine."""
    assert resolve_platform_slug("easyrpg", _config()) == UPS.RPG_MAKER.value
    assert resolve_fs_slug(UPS.RPG_MAKER.value, _config()) == "easyrpg"


@pytest.mark.parametrize("folder", ["sgb", "sgb-msu1"])
def test_super_game_boy_folders_stay_unidentified(folder: str):
    """ES-DE and Batocera use sgb for the Super Game Boy, which has no RomM slug."""
    assert resolve_builtin_platform_slug(folder) is None
    assert resolve_platform_slug(folder, _config()) == folder


@pytest.mark.parametrize(
    ("folder", "slug"),
    [
        ("mame", UPS.MAME),
        ("fbneo", UPS.FBNEO),
        ("naomi", UPS.NAOMI),
        ("lindbergh", UPS.LINDBERGH),
        ("laserdisc", UPS.DAPHNE),
        ("cps2", UPS.ARCADE),
        ("system16", UPS.ARCADE),
        ("model1", UPS.ARCADE),
        ("namco22", UPS.ARCADE),
        ("system-32", UPS.ARCADE),
        ("typex", UPS.TYPE_X),
        ("teknoparrot", UPS.TEKNOPARROT),
    ],
)
def test_arcade_folders_resolve_by_emulator(folder: str, slug: UPS):
    """Emulator families and boards with their own emulator keep a slug; MAME-only boards are Arcade."""
    assert resolve_platform_slug(folder, _config()) == slug.value


def test_a_binding_to_an_alias_resolves_to_its_platform():
    config = _config(bindings={"capcom": "cps2"}, versions={"sega": "Mastersystem"})

    assert resolve_platform_slug("capcom", config) == UPS.ARCADE.value
    assert resolve_platform_slug("sega", config) == UPS.SMS.value
    assert resolve_fs_slug(UPS.SMS.value, config) == "sega"


def test_binding_and_version_win_over_alias():
    bound = _config(bindings={"gamecube": "arcade"})
    assert resolve_platform_slug("gamecube", bound) == "arcade"

    versioned = _config(versions={"gamecube": "wii"})
    assert resolve_platform_slug("gamecube", versioned) == "wii"

    both = _config(bindings={"gamecube": "arcade"}, versions={"gamecube": "wii"})
    assert resolve_platform_slug("gamecube", both) == "arcade"


def test_warns_about_a_binding_to_an_unknown_name():
    config = _config(bindings={"snes-test": "snse"})

    warning = unknown_binding_warning("SNES-Test", config)

    assert warning is not None
    assert "system.platforms.snes-test is snse" in warning
    assert warning.endswith("Did you mean snes, singe?")


def test_warns_about_a_version_to_an_unknown_name():
    warning = unknown_binding_warning("cube", _config(versions={"cube": "gamcube"}))

    assert warning is not None
    assert "system.versions.cube is gamcube" in warning
    assert "gamecube" in warning


def test_leaves_out_the_suggestion_when_nothing_is_close():
    warning = unknown_binding_warning("mine", _config(bindings={"mine": "qqqqqq"}))

    assert warning is not None
    assert "Did you mean" not in warning


@pytest.mark.parametrize(
    ("bindings", "versions", "folder"),
    [
        ({"nintendo-snes": "snes"}, {}, "nintendo-snes"),
        ({"easyrpg-2000": "easyrpg"}, {}, "easyrpg-2000"),
        ({}, {"sega": "Mastersystem"}, "sega"),
        ({"a1200": "amiga-a-1200"}, {}, "a1200"),
        ({}, {}, "my-homebrew"),
        # The binding wins over the version, so only it is checked.
        ({"gamecube": "arcade"}, {"gamecube": "gamcube"}, "gamecube"),
    ],
)
def test_no_warning_for_known_names_or_unbound_folders(
    bindings: dict[str, str], versions: dict[str, str], folder: str
):
    assert unknown_binding_warning(folder, _config(bindings, versions)) is None


def test_lists_a_warning_for_each_unknown_binding():
    config = _config(
        bindings={"snes-test": "snse", "nintendo-snes": "snes"},
        versions={"cube": "gamcube"},
    )

    warnings = unknown_binding_warnings(config)

    assert len(warnings) == 2
    assert "system.versions.cube" in warnings[0]
    assert "system.platforms.snes-test" in warnings[1]


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


def test_resolves_a_config_key_to_the_folder_on_disk():
    """Config keys are lowercased; paths need the folder's own casing."""
    assert resolve_fs_folder("nintendo 64", ["Nintendo 64", "psx"]) == "Nintendo 64"


def test_resolves_a_folder_that_is_not_on_disk_to_nothing():
    assert resolve_fs_folder("nintendo 64", ["psx"]) is None


def test_two_folders_differing_only_by_case_each_resolve_to_themselves():
    """A case-sensitive filesystem allows both; neither may claim the other."""
    folders = ["PSX", "psx"]

    assert resolve_fs_folder("psx", folders) == "psx"
    assert resolve_fs_folder("PSX", folders) == "PSX"


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


@pytest.mark.parametrize(
    ("folder", "slug"),
    [("gamecube", "ngc"), ("MegaDrive", "genesis"), ("N64", "n64"), ("mystery", None)],
)
def test_resolves_builtin_slug_without_config(folder: str, slug: str | None):
    assert resolve_builtin_platform_slug(folder) == slug
