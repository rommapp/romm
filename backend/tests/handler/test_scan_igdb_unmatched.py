"""Which platforms an unmatched scan retries IGDB on."""

from unittest.mock import AsyncMock, patch

import pytest
from tests.factories import make_platform
from tests.handler.scan_stubs import add_rom, run_scan

from adapters.services.igdb import IGDB_PLATFORM_LIST
from handler.metadata.igdb_handler import IGDBRom
from handler.scan_handler import MetadataSource, ScanType
from utils.platform_slugs import UniversalPlatformSlug as UPS

ARCADE_IGDB_ID = IGDB_PLATFORM_LIST[UPS.ARCADE]["id"]


async def _unmatched_scan(slug: str, igdb_id: int) -> AsyncMock:
    platform = make_platform(slug, id=1, igdb_id=igdb_id)
    rom = add_rom(platform, "mvsc2.zip", "mvsc2")
    lookup = AsyncMock(return_value=IGDBRom(igdb_id=None))

    with patch("handler.scan_handler.meta_igdb_handler.get_rom", new=lookup):
        await run_scan(
            platform,
            rom,
            scan_type=ScanType.UNMATCHED,
            metadata_sources=[MetadataSource.IGDB],
        )
    return lookup


@pytest.mark.parametrize("slug", [UPS.ARCADE, UPS.MAME, UPS.NAOMI, UPS.MODEL2])
async def test_an_arcade_platform_is_retried_under_arcade(slug: UPS):
    lookup = await _unmatched_scan(slug, ARCADE_IGDB_ID)

    lookup.assert_awaited_once()


async def test_a_platform_igdb_does_not_list_is_skipped():
    lookup = await _unmatched_scan(UPS.TAITO_X_55, ARCADE_IGDB_ID)

    lookup.assert_not_awaited()
