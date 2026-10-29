"""A refresh scan refetches a rom's stored match rather than matching it anew."""

from unittest.mock import AsyncMock, patch

from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.metadata import (
    meta_demozoo_handler,
    meta_igdb_handler,
    meta_moby_handler,
    meta_playmatch_handler,
)
from handler.metadata.demozoo_handler import DemozooRom
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.moby_handler import MobyGamesRom
from handler.metadata.playmatch_handler import PlaymatchRomMatch
from handler.scan_handler import MetadataSource, ScanType


def _playmatch_answer(igdb_id: int) -> PlaymatchRomMatch:
    return PlaymatchRomMatch(
        igdb_id=igdb_id,
        moby_id=None,
        ss_id=None,
        launchbox_id=None,
        sgdb_id=None,
        ra_id=None,
        hasheous_id=None,
        tgdb_id=None,
        flashpoint_id=None,
        hltb_id=None,
        libretro_id=None,
        gamelist_id=None,
    )


async def test_an_update_keeps_the_stored_igdb_id_over_playmatch():
    platform = add_n64_platform(igdb_id=4)
    rom = add_rom(platform, "Paper Mario (USA).z64", "Paper Mario", igdb_id=1)
    by_id = AsyncMock(return_value=IGDBRom(igdb_id=None))

    with (
        patch.object(meta_playmatch_handler, "is_enabled", return_value=True),
        patch.object(
            meta_playmatch_handler,
            "lookup_rom",
            new=AsyncMock(return_value=_playmatch_answer(igdb_id=99)),
        ),
        patch.object(meta_igdb_handler, "get_rom_by_id", new=by_id),
    ):
        await run_scan(
            platform,
            rom,
            scan_type=ScanType.UPDATE,
            metadata_sources=[MetadataSource.PLAYMATCH, MetadataSource.IGDB],
        )

    by_id.assert_awaited_once_with(rom, 1)


async def test_an_unmatched_scan_refetches_an_id_without_metadata():
    platform = add_n64_platform(moby_id=9)
    rom = add_rom(platform, "Paper Mario (USA).z64", "Paper Mario", moby_id=123)
    by_id = AsyncMock(return_value=MobyGamesRom(moby_id=None))
    by_name = AsyncMock(return_value=MobyGamesRom(moby_id=None))

    with (
        patch.object(meta_moby_handler, "get_rom_by_id", new=by_id),
        patch.object(meta_moby_handler, "get_rom", new=by_name),
    ):
        await run_scan(
            platform,
            rom,
            scan_type=ScanType.UNMATCHED,
            metadata_sources=[MetadataSource.MOBY],
        )

    by_id.assert_awaited_once_with(123)
    by_name.assert_not_awaited()


async def test_an_update_refetches_the_stored_demozoo_id():
    platform = add_n64_platform()
    rom = add_rom(platform, "Desert Dream.adf", "Desert Dream", demozoo_id=1234)
    by_id = AsyncMock(return_value=DemozooRom(demozoo_id=None))
    by_name = AsyncMock(return_value=DemozooRom(demozoo_id=None))

    with (
        patch.object(meta_demozoo_handler, "get_rom_by_id", new=by_id),
        patch.object(meta_demozoo_handler, "get_rom", new=by_name),
    ):
        await run_scan(
            platform,
            rom,
            scan_type=ScanType.UPDATE,
            metadata_sources=[MetadataSource.DEMOZOO],
        )

    by_id.assert_awaited_once_with(1234)
    by_name.assert_not_awaited()
