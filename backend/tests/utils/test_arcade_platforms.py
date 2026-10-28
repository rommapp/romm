import pytest

from endpoints.responses.feeds import (
    WEBRCADE_SLUG_TO_TYPE_MAP,
    WEBRCADE_SUPPORTED_PLATFORM_SLUGS,
)
from handler.database.roms_handler import EJS_SUPPORTED_PLATFORMS
from handler.metadata import (
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.metadata.platform_names import resolve_platform_name
from utils.arcade_platforms import (
    ARCADE_PLATFORMS,
    ARCADE_SET_PLATFORMS,
    arcade_fallbacks,
)
from utils.platform_slugs import UniversalPlatformSlug as UPS

BOARD_PLATFORMS = sorted(ARCADE_PLATFORMS - ARCADE_SET_PLATFORMS)
PLAYABLE_SETS = {UPS.ARCADE, UPS.MAME, UPS.FBNEO, UPS.FBA}


def test_fallbacks_keep_a_providers_own_entry():
    platforms = {UPS.ARCADE: "arcade", UPS.NAOMI: "naomi"}

    assert arcade_fallbacks(platforms, [UPS.NAOMI, UPS.MAME]) == {UPS.MAME: "arcade"}


@pytest.mark.parametrize("slug", sorted(ARCADE_PLATFORMS))
def test_every_arcade_platform_is_looked_up_at_every_provider(slug: UPS):
    assert meta_ss_handler.get_platform(slug)["ss_id"]
    assert meta_launchbox_handler.get_platform(slug)["launchbox_id"]
    assert meta_moby_handler.get_platform(slug)["moby_id"]
    assert meta_tgdb_handler.get_platform(slug)["tgdb_id"]
    assert meta_hasheous_handler.get_platform(slug)["hasheous_id"]
    assert meta_hltb_handler.get_platform(slug)["hltb_slug"]


@pytest.mark.parametrize("slug", sorted(ARCADE_PLATFORMS - {UPS.ARCADE}))
def test_an_arcade_platform_is_not_named_arcade(slug: UPS):
    assert resolve_platform_name(slug) != "Arcade"


@pytest.mark.parametrize("slug", sorted(ARCADE_SET_PLATFORMS))
def test_a_set_platform_gets_retroachievements_arcade(slug: UPS):
    assert meta_ra_handler.get_platform(slug)["ra_id"] == 27
    assert meta_hasheous_handler.get_platform(slug)["ra_id"] == 27


@pytest.mark.parametrize("slug", BOARD_PLATFORMS)
def test_a_board_gets_no_retroachievements_console(slug: UPS):
    assert meta_ra_handler.get_platform(slug)["ra_id"] is None
    assert meta_hasheous_handler.get_platform(slug)["ra_id"] is None


def test_only_sets_an_emulatorjs_core_runs_are_playable():
    assert PLAYABLE_SETS <= set(EJS_SUPPORTED_PLATFORMS)
    assert not (ARCADE_PLATFORMS - PLAYABLE_SETS) & set(EJS_SUPPORTED_PLATFORMS)


@pytest.mark.parametrize("slug", sorted(PLAYABLE_SETS))
def test_set_platforms_feed_webrcade_as_arcade(slug: UPS):
    assert slug in WEBRCADE_SUPPORTED_PLATFORM_SLUGS
    assert WEBRCADE_SLUG_TO_TYPE_MAP[slug] == "arcade"


def test_advancemame_is_left_out_of_webrcade():
    assert UPS.MAME_ADVMAME not in WEBRCADE_SUPPORTED_PLATFORM_SLUGS
