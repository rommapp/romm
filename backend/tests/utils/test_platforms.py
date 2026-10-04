from handler.database import db_platform_handler
from handler.filesystem import fs_platform_handler
from models.platform import Platform
from utils.platforms import (
    get_filesystem_platforms,
    get_supported_platforms,
    platform_alternative_names,
)


def test_supported_platform_not_shadowed_by_variant():
    """A variant/alias folder bound to a parent slug must not shadow the parent.

    Regression for the bug where adding an "fbneo" folder as a variant of
    "arcade" renamed the Arcade platform to "FBneo" in the platform picker.
    """
    # Canonical Arcade platform (folder name matches the slug).
    db_platform_handler.add_platform(
        Platform(name="Arcade", slug="arcade", fs_slug="arcade")
    )
    # Variant folder resolved to the same slug during scan.
    db_platform_handler.add_platform(
        Platform(name="FBneo", slug="arcade", fs_slug="fbneo")
    )

    supported = get_supported_platforms()
    arcade = next(p for p in supported if p.slug == "arcade")

    assert arcade.name == "Arcade"
    assert arcade.fs_slug == "arcade"


def test_supported_platform_keeps_tgdb_id_from_tgdb():
    """The TGDB platform ID must survive the metadata merge.

    Regression for the tgdb_id fallback chain missing the TGDB handler
    itself: MobyGames platforms never carry a tgdb_id and the Hasheous
    platform list has no TGDB mappings, so every unmatched platform was
    reported with tgdb_id=None even when TGDB knows the platform.
    """
    supported = get_supported_platforms()
    threedo = next(p for p in supported if p.slug == "3do")

    # TGDB maps the 3DO platform to ID 25.
    assert threedo.tgdb_id == 25


async def test_filesystem_platform_resolves_frontend_folder_name(monkeypatch):
    """A Batocera or ES-DE folder name is listed under the RomM platform it maps to."""

    async def fake_get_platforms() -> list[str]:
        return ["gamecube"]

    monkeypatch.setattr(fs_platform_handler, "get_platforms", fake_get_platforms)

    platforms = await get_filesystem_platforms()

    assert [(p.fs_slug, p.slug) for p in platforms] == [("gamecube", "ngc")]


def test_supported_platform_sharing_ss_id_keeps_its_own_name():
    """A platform sharing a ScreenScraper system ID must not take its sibling's name."""
    supported = {p.slug: p for p in get_supported_platforms()}

    assert supported["c128"].name == "Commodore 128"
    assert supported["videopac-g7400"].name == "Videopac+ G7400"


class TestPlatformAlternativeNames:
    def test_collects_each_provider_name_after_the_alternative_names(self):
        names = platform_alternative_names(
            "genesis",
            "Sega Mega Drive/Genesis",
            [
                {"name": "Sega Mega Drive/Genesis", "alternative_names": ["MD"]},
                {"name": "Megadrive"},
                {"name": "Sega Genesis"},
            ],
        )

        assert names == ["MD", "Megadrive", "Sega Genesis"]

    def test_skips_the_platform_name_and_repeats_ignoring_case_and_spacing(self):
        names = platform_alternative_names(
            "genesis",
            "Sega Mega Drive/Genesis",
            [
                {"name": "Sega Mega Drive / Genesis"},
                {"name": "sega genesis"},
                {"name": "Sega Genesis"},
            ],
        )

        assert names == ["sega genesis"]

    def test_ignores_providers_without_a_name(self):
        assert (
            platform_alternative_names("nes", "NES", [{"slug": "nes"}, {"name": ""}])
            == []
        )

    def test_skips_a_name_that_belongs_to_another_platform(self):
        names = platform_alternative_names(
            "famicom",
            "Family Computer",
            [{"name": "Nintendo Entertainment System"}, {"name": "Famicom"}],
        )

        assert names == ["Famicom"]


def test_supported_platform_carries_other_providers_names():
    genesis = next(p for p in get_supported_platforms() if p.slug == "genesis")

    assert "Megadrive" in genesis.alternative_names
    assert genesis.name not in genesis.alternative_names


def test_supported_platform_reads_a_row_without_alternative_names():
    """Rows that predate the column read NULL and still serialize."""
    platform = db_platform_handler.add_platform(
        Platform(name="Sega Mega Drive/Genesis", slug="genesis", fs_slug="genesis")
    )
    db_platform_handler.update_platform(platform.id, {"alternative_names": None})

    genesis = next(p for p in get_supported_platforms() if p.slug == "genesis")

    assert genesis.alternative_names == []
