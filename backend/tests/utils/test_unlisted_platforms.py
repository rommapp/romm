import pytest

from adapters.services.igdb import IGDB_PLATFORM_LIST
from handler.metadata import meta_igdb_handler
from handler.metadata.launchbox_handler.platforms import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST
from handler.metadata.platform_names import resolve_platform_name
from handler.metadata.ra_handler import RA_PLATFORM_LIST
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST
from utils.platform_slugs import UniversalPlatformSlug as UPS
from utils.unlisted_platforms import UNLISTED_PLATFORMS, host_fallbacks


@pytest.mark.parametrize("slug", UNLISTED_PLATFORMS)
def test_each_unlisted_platform_is_named_by_hand(slug: UPS):
    assert resolve_platform_name(slug.value) == UNLISTED_PLATFORMS[slug].name


def test_a_port_searches_under_its_host_but_keeps_its_name():
    assert SCREENSAVER_PLATFORM_LIST[UPS.QUAKE]["id"] == (
        SCREENSAVER_PLATFORM_LIST[UPS.DOS]["id"]
    )
    assert SCREENSAVER_PLATFORM_LIST[UPS.QUAKE]["name"] == "Quake"
    assert MOBYGAMES_PLATFORM_LIST[UPS.SONIC3_AIR]["id"] == (
        MOBYGAMES_PLATFORM_LIST[UPS.GENESIS]["id"]
    )
    assert LAUNCHBOX_PLATFORM_LIST[UPS.HALFLIFE]["id"] == (
        LAUNCHBOX_PLATFORM_LIST[UPS.WIN]["id"]
    )

    igdb = meta_igdb_handler.get_platform(UPS.QUAKE.value)
    assert igdb["igdb_id"] == IGDB_PLATFORM_LIST[UPS.DOS]["id"]
    assert igdb["slug"] == UPS.QUAKE.value
    assert igdb.get("name") == "Quake"


def test_a_port_does_not_inherit_its_hosts_other_names():
    assert "alternative_names" in SCREENSAVER_PLATFORM_LIST[UPS.DOS]
    assert "alternative_names" not in SCREENSAVER_PLATFORM_LIST[UPS.QUAKE]


def test_a_providers_own_entry_wins_over_the_host():
    assert SCREENSAVER_PLATFORM_LIST[UPS.LUTRO]["id"] == 206
    assert host_fallbacks(
        {UPS.WIN: {"name": "Windows"}, UPS.CAVESTORY: {"name": "x"}}
    ) == {
        slug: {"name": platform.name}
        for slug, platform in UNLISTED_PLATFORMS.items()
        if platform.host == UPS.WIN and slug != UPS.CAVESTORY
    }


def test_a_port_is_not_matched_by_hash_against_its_host():
    """A port's files are not the original game's, so hash providers skip it."""
    assert UPS.SONIC3_AIR not in RA_PLATFORM_LIST
