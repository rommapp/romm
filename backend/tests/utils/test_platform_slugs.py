import pytest

from adapters.services.igdb import IGDB_PLATFORM_LIST
from adapters.services.rahasher import PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID
from handler.metadata.hasheous_handler import HASHEOUS_PLATFORM_LIST
from handler.metadata.launchbox_handler.platforms import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST
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
