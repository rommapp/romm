"""How a scan picks a ROM's LaunchBox match.

Playmatch answers with a LaunchBox ID for nearly every ROM on some platforms
(N64, SNES, Genesis), so an unhandled miss on that ID would leave those
platforms with no LaunchBox metadata at all while a manual match still works.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from handler.metadata.launchbox_handler.types import LaunchboxRom
from handler.metadata.playmatch_handler import PlaymatchRomMatch
from handler.scan_handler import ScanType, resolve_launchbox_rom

MATCH = LaunchboxRom(launchbox_id=266, name="Mario Kart 64")
NO_MATCH = LaunchboxRom(launchbox_id=None)


def _playmatch(launchbox_id: int | None) -> PlaymatchRomMatch:
    return PlaymatchRomMatch(
        igdb_id=None,
        moby_id=None,
        ss_id=None,
        launchbox_id=launchbox_id,
        sgdb_id=None,
        ra_id=None,
        hasheous_id=None,
        tgdb_id=None,
        flashpoint_id=None,
        hltb_id=None,
        gamelist_id=None,
        libretro_id=None,
    )


def _rom(launchbox_id: int | None = None, launchbox_metadata: dict | None = None):
    return SimpleNamespace(
        launchbox_id=launchbox_id,
        launchbox_metadata=launchbox_metadata or {},
    )


@pytest.fixture
def lookups():
    """Patch both LaunchBox lookups, defaulting each to a miss."""
    with (
        patch(
            "handler.scan_handler.meta_launchbox_handler.get_rom_by_id",
            new=AsyncMock(return_value=NO_MATCH),
        ) as by_id,
        patch(
            "handler.scan_handler.meta_launchbox_handler.get_rom",
            new=AsyncMock(return_value=NO_MATCH),
        ) as by_name,
    ):
        yield SimpleNamespace(by_id=by_id, by_name=by_name)


async def test_unresolved_playmatch_id_falls_back_to_file_name(lookups):
    lookups.by_name.return_value = MATCH

    result = await resolve_launchbox_rom(
        rom=_rom(),
        fs_name="Mario Kart 64 (USA).zip",
        platform_slug="n64",
        scan_type=ScanType.COMPLETE,
        playmatch_rom=_playmatch(266),
        remote_enabled=True,
    )

    lookups.by_id.assert_awaited_once()
    lookups.by_name.assert_awaited_once_with(
        "Mario Kart 64 (USA).zip", "n64", remote_enabled=True
    )
    assert result["launchbox_id"] == 266


async def test_resolved_playmatch_id_skips_the_file_name_lookup(lookups):
    lookups.by_id.return_value = MATCH

    result = await resolve_launchbox_rom(
        rom=_rom(),
        fs_name="Mario Kart 64 (USA).zip",
        platform_slug="n64",
        scan_type=ScanType.COMPLETE,
        playmatch_rom=_playmatch(266),
        remote_enabled=True,
    )

    lookups.by_name.assert_not_awaited()
    assert result["launchbox_id"] == 266


async def test_no_playmatch_id_uses_the_file_name_lookup(lookups):
    lookups.by_name.return_value = MATCH

    result = await resolve_launchbox_rom(
        rom=_rom(),
        fs_name="Mario Kart 64 (USA).zip",
        platform_slug="n64",
        scan_type=ScanType.COMPLETE,
        playmatch_rom=_playmatch(None),
        remote_enabled=True,
    )

    lookups.by_id.assert_not_awaited()
    assert result["launchbox_id"] == 266


async def test_stored_id_is_not_replaced_by_a_file_name_guess(lookups):
    """An ID the store can't resolve stays put rather than being re-guessed."""
    result = await resolve_launchbox_rom(
        rom=_rom(launchbox_id=999),
        fs_name="Mario Kart 64 (USA).zip",
        platform_slug="n64",
        scan_type=ScanType.UPDATE,
        playmatch_rom=_playmatch(266),
        remote_enabled=True,
    )

    lookups.by_id.assert_awaited_once()
    lookups.by_name.assert_not_awaited()
    assert result["launchbox_id"] is None


async def test_unmatched_scan_refetches_metadata_for_a_stored_id(lookups):
    lookups.by_id.return_value = MATCH

    result = await resolve_launchbox_rom(
        rom=_rom(launchbox_id=266),
        fs_name="Mario Kart 64 (USA).zip",
        platform_slug="n64",
        scan_type=ScanType.UNMATCHED,
        playmatch_rom=_playmatch(None),
        remote_enabled=True,
    )

    lookups.by_id.assert_awaited_once()
    lookups.by_name.assert_not_awaited()
    assert result["launchbox_id"] == 266


async def test_local_only_never_calls_the_remote_id_lookup(lookups):
    """With the remote store off, only the local filename lookup may run."""
    await resolve_launchbox_rom(
        rom=_rom(launchbox_id=266),
        fs_name="Mario Kart 64 (USA).zip",
        platform_slug="n64",
        scan_type=ScanType.UPDATE,
        playmatch_rom=_playmatch(266),
        remote_enabled=False,
    )

    lookups.by_id.assert_not_awaited()
    lookups.by_name.assert_awaited_once_with(
        "Mario Kart 64 (USA).zip", "n64", remote_enabled=False
    )
