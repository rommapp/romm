"""How a scan picks a ROM's Steam match."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from handler.metadata.steam_handler import SteamRom
from handler.scan_handler import ScanType, resolve_steam_rom

MATCH = SteamRom(steam_id=1091500, name="Cyberpunk 2077")
NO_MATCH = SteamRom(steam_id=None)


def _rom(steam_id: int | None = None, steam_metadata: dict | None = None):
    return SimpleNamespace(
        steam_id=steam_id,
        steam_metadata=steam_metadata or {},
    )


@pytest.fixture
def lookups():
    """Patch both Steam lookups, defaulting each to a miss."""
    with (
        patch(
            "handler.scan_handler.meta_steam_handler.get_rom_by_id",
            new=AsyncMock(return_value=NO_MATCH),
        ) as by_id,
        patch(
            "handler.scan_handler.meta_steam_handler.get_rom",
            new=AsyncMock(return_value=NO_MATCH),
        ) as by_name,
    ):
        yield SimpleNamespace(by_id=by_id, by_name=by_name)


async def test_rom_with_no_id_is_matched_by_file_name(lookups):
    lookups.by_name.return_value = MATCH

    result = await resolve_steam_rom(
        rom=_rom(),
        fs_name="Cyberpunk 2077.lnk",
        platform_slug="win",
        scan_type=ScanType.COMPLETE,
    )

    lookups.by_id.assert_not_awaited()
    lookups.by_name.assert_awaited_once_with("Cyberpunk 2077.lnk", "win")
    assert result["steam_id"] == 1091500


async def test_update_scan_refetches_the_stored_id(lookups):
    lookups.by_id.return_value = MATCH

    result = await resolve_steam_rom(
        rom=_rom(steam_id=1091500, steam_metadata={"genres": ["RPG"]}),
        fs_name="Cyberpunk 2077.lnk",
        platform_slug="win",
        scan_type=ScanType.UPDATE,
    )

    lookups.by_id.assert_awaited_once_with(1091500)
    lookups.by_name.assert_not_awaited()
    assert result["steam_id"] == 1091500


async def test_stored_id_is_not_replaced_by_a_file_name_guess(lookups):
    """An app ID the storefront can't resolve stays put rather than being re-guessed."""
    result = await resolve_steam_rom(
        rom=_rom(steam_id=999999),
        fs_name="Cyberpunk 2077.lnk",
        platform_slug="win",
        scan_type=ScanType.UPDATE,
    )

    lookups.by_name.assert_not_awaited()
    assert result["steam_id"] is None


async def test_unmatched_scan_refetches_metadata_for_a_stored_id(lookups):
    lookups.by_id.return_value = MATCH

    result = await resolve_steam_rom(
        rom=_rom(steam_id=1091500),
        fs_name="Cyberpunk 2077.lnk",
        platform_slug="win",
        scan_type=ScanType.UNMATCHED,
    )

    lookups.by_id.assert_awaited_once_with(1091500)
    lookups.by_name.assert_not_awaited()
    assert result["steam_id"] == 1091500


async def test_unmatched_scan_searches_when_the_stored_id_already_has_metadata(lookups):
    lookups.by_name.return_value = MATCH

    await resolve_steam_rom(
        rom=_rom(steam_id=1091500, steam_metadata={"genres": ["RPG"]}),
        fs_name="Cyberpunk 2077.lnk",
        platform_slug="win",
        scan_type=ScanType.UNMATCHED,
    )

    lookups.by_id.assert_not_awaited()
    lookups.by_name.assert_awaited_once()
