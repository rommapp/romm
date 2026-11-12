import pytest

from adapters.services.igdb import IGDB_PLATFORM_LIST
from adapters.services.rahasher import PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID
from handler.metadata.hasheous_handler import HASHEOUS_PLATFORM_LIST
from handler.metadata.hltb_handler import HLTB_PLATFORM_LIST
from handler.metadata.launchbox_handler.platforms import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST
from handler.metadata.platform_names import resolve_platform_name
from handler.metadata.ra_handler import RA_PLATFORM_LIST
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST
from handler.metadata.tgdb_handler import TGDB_PLATFORM_LIST
from utils.platform_slugs import DUPLICATE_PLATFORM_SLUGS
from utils.platform_slugs import UniversalPlatformSlug as UPS
from utils.platform_slugs import fill_duplicate_slugs


def test_fills_either_slug_from_the_other():
    platforms = {UPS.VC_4000: 1, UPS.PIPPIN: 2}

    fill_duplicate_slugs(platforms)

    assert platforms[UPS.INTERTON_VC_4000] == 1
    assert platforms[UPS.APPLE_PIPPIN] == 2
    assert UPS.VIS not in platforms
    assert UPS.TANDY_VIS not in platforms


def test_keeps_both_entries_when_both_are_listed():
    platforms = {UPS.VC_4000: 1, UPS.INTERTON_VC_4000: 2}

    fill_duplicate_slugs(platforms)

    assert platforms == {UPS.VC_4000: 1, UPS.INTERTON_VC_4000: 2}


@pytest.mark.parametrize(
    "platforms",
    [
        IGDB_PLATFORM_LIST,
        SCREENSAVER_PLATFORM_LIST,
        LAUNCHBOX_PLATFORM_LIST,
        RA_PLATFORM_LIST,
        PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID,
        TGDB_PLATFORM_LIST,
        MOBYGAMES_PLATFORM_LIST,
        HASHEOUS_PLATFORM_LIST,
    ],
    ids=["igdb", "ss", "launchbox", "ra", "rahasher", "tgdb", "moby", "hasheous"],
)
def test_provider_lists_cover_both_slugs_or_neither(platforms: dict[UPS, object]):
    for slug, duplicate in DUPLICATE_PLATFORM_SLUGS:
        assert (slug in platforms) == (duplicate in platforms)


def test_abc_800_is_its_own_platform_apart_from_the_abc_80():
    assert UPS.ABC_800.value == "abc-800"
    assert UPS.ABC_800.value != UPS.ABC_80.value
    assert HASHEOUS_PLATFORM_LIST[UPS.ABC_800]["id"] == 278114
    assert resolve_platform_name(UPS.ABC_800.value) == "Luxor ABC 800"
    assert resolve_platform_name(UPS.ABC_80.value) == "ABC 80"


def test_playstation_mobile_is_named_and_mapped_where_providers_list_it():
    assert UPS.PLAYSTATION_MOBILE.value == "playstation-mobile"
    assert HASHEOUS_PLATFORM_LIST[UPS.PLAYSTATION_MOBILE]["id"] == 314213
    assert HLTB_PLATFORM_LIST[UPS.PLAYSTATION_MOBILE]["name"] == "PlayStation Mobile"
    assert resolve_platform_name(UPS.PLAYSTATION_MOBILE.value) == (
        "Sony PlayStation Mobile"
    )
