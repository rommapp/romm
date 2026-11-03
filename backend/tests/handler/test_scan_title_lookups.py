"""How a scan looks up a file named by all of a game's titles.

No-Intro and Redump join them with " ~ ", and a provider searching the whole
name often finds nothing where either title alone finds the game.
"""

from unittest.mock import AsyncMock, call, patch

from tests.factories import make_platform
from tests.handler.scan_stubs import add_rom, run_scan

from handler.metadata.hltb_handler import HLTBRom
from handler.metadata.igdb_handler import IGDBRom
from handler.scan.lookups import lookup_by_file_name
from handler.scan.sources import MetadataSource, ScanType

FS_NAME = "Sonic Wings 2 ~ Aero Fighters 2 (World) (En,Ja).chd"
FIRST_TITLE = "Sonic Wings 2 (World) (En,Ja).chd"
SECOND_TITLE = "Aero Fighters 2 (World) (En,Ja).chd"
MATCH = HLTBRom(hltb_id=4821, name="Aero Fighters 2")
NO_MATCH = HLTBRom(hltb_id=None)


async def test_a_match_on_the_full_name_stands():
    lookup = AsyncMock(return_value=MATCH)

    result = await lookup_by_file_name(MetadataSource.HLTB, FS_NAME, lookup)

    lookup.assert_awaited_once_with(FS_NAME)
    assert result == MATCH


async def test_each_title_is_looked_up_until_one_matches():
    lookup = AsyncMock(side_effect=[NO_MATCH, MATCH])

    result = await lookup_by_file_name(MetadataSource.HLTB, FS_NAME, lookup)

    assert lookup.await_args_list == [call(FS_NAME), call(FIRST_TITLE)]
    assert result == MATCH


async def test_a_miss_on_every_title_stays_a_miss():
    lookup = AsyncMock(return_value=NO_MATCH)

    result = await lookup_by_file_name(MetadataSource.HLTB, FS_NAME, lookup)

    assert lookup.await_args_list == [
        call(FS_NAME),
        call(FIRST_TITLE),
        call(SECOND_TITLE),
    ]
    assert result == NO_MATCH


async def test_a_single_title_is_looked_up_once():
    lookup = AsyncMock(return_value=NO_MATCH)

    await lookup_by_file_name(MetadataSource.HLTB, SECOND_TITLE, lookup)

    lookup.assert_awaited_once_with(SECOND_TITLE)


async def test_a_scan_matches_igdb_by_the_second_title():
    platform = make_platform("neo-geo-cd", id=1, igdb_id=136)
    rom = add_rom(platform, FS_NAME, "Sonic Wings 2 ~ Aero Fighters 2")
    lookup = AsyncMock(
        side_effect=[
            IGDBRom(igdb_id=None),
            IGDBRom(igdb_id=None),
            IGDBRom(igdb_id=6773, name="Aero Fighters 2"),
        ]
    )

    with patch("handler.scan.lookups.meta_igdb_handler.get_rom", new=lookup):
        result = await run_scan(
            platform,
            rom,
            scan_type=ScanType.COMPLETE,
            metadata_sources=[MetadataSource.IGDB],
        )

    assert [lookup_call.args[1:] for lookup_call in lookup.await_args_list] == [
        (FS_NAME, 136),
        (FIRST_TITLE, 136),
        (SECOND_TITLE, 136),
    ]
    assert result.igdb_id == 6773
    assert result.name == "Aero Fighters 2"
