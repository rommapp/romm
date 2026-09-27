import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.concurrency_stubs import InFlight

from handler.scan_handler import MetadataSource, download_rom_resources


def _rom() -> Any:
    return SimpleNamespace(
        id=7,
        url_cover="http://x/cover.png",
        url_manual="http://x/manual.pdf",
        url_screenshots=["http://x/ss.jpg"],
        ss_metadata={"fanart_path": "roms/1/7/fanart/fanart.png"},
        gamelist_metadata={"video_path": "roms/1/7/video/video.mp4"},
        launchbox_metadata=None,
        ra_metadata={
            "achievements": [
                {
                    "badge_url": "http://x/1.png",
                    "badge_path": "roms/1/7/badges/1.png",
                    "badge_url_lock": "http://x/1_lock.png",
                    "badge_path_lock": "roms/1/7/badges/1_lock.png",
                }
            ]
        },
    )


@pytest.fixture
def resources() -> Iterator[SimpleNamespace]:
    """Stub every download, so each test overrides only the ones it checks."""
    downloads = {
        "get_cover": AsyncMock(return_value=(None, None)),
        "get_manual": AsyncMock(return_value=None),
        "get_rom_screenshots": AsyncMock(return_value=[]),
        "store_metadata_media": AsyncMock(return_value=False),
        "store_ra_badge": AsyncMock(return_value=None),
    }
    with (
        patch("handler.scan_handler.get_preferred_media_types", return_value=[]),
        patch("handler.scan_handler.db_rom_handler.update_rom") as update_rom,
        patch.multiple("handler.scan_handler.fs_resource_handler", **downloads),
    ):
        yield SimpleNamespace(update_rom=update_rom, **downloads)


async def _download(rom: Any, metadata_sources: list[str]) -> None:
    await download_rom_resources(
        added_rom=rom,
        previous_url_cover=None,
        previous_url_manual=None,
        previous_url_screenshots=None,
        metadata_sources=metadata_sources,
    )


@pytest.mark.asyncio
async def test_downloads_every_file_of_a_rom_together(resources: SimpleNamespace):
    tracker = InFlight()
    resources.get_cover.side_effect = tracker.returning(("small.png", "big.png"))
    resources.get_manual.side_effect = tracker.returning("manual.pdf")
    resources.get_rom_screenshots.side_effect = tracker.returning(["0.jpg"])
    resources.store_metadata_media.side_effect = tracker.returning(False)
    resources.store_ra_badge.side_effect = tracker.returning(None)

    await _download(
        _rom(), [MetadataSource.SS, MetadataSource.GAMELIST, MetadataSource.RA]
    )

    # Cover, manual, screenshots, one provider dict at a time and two badges.
    assert tracker.peak == 6
    resources.update_rom.assert_called_once_with(
        7,
        {
            "path_cover_s": "small.png",
            "path_cover_l": "big.png",
            "path_screenshots": ["0.jpg"],
            "path_manual": "manual.pdf",
        },
    )


@pytest.mark.asyncio
async def test_provider_media_dicts_take_turns_in_priority_order(
    resources: SimpleNamespace,
):
    rom = _rom()
    rom.launchbox_metadata = {"video_path": "roms/1/7/video/video.mp4"}
    tracker = InFlight()
    order: list[dict[str, Any]] = []

    async def store_metadata_media(metadata: dict[str, Any], *_args: Any) -> bool:
        await tracker.hold()
        order.append(metadata)
        return False

    resources.store_metadata_media.side_effect = store_metadata_media

    await _download(
        rom, [MetadataSource.SS, MetadataSource.GAMELIST, MetadataSource.LAUNCHBOX]
    )

    assert tracker.peak == 1
    assert order == [rom.ss_metadata, rom.gamelist_metadata, rom.launchbox_metadata]


@pytest.mark.asyncio
async def test_writes_back_only_the_provider_media_that_changed(
    resources: SimpleNamespace,
):
    rom = _rom()
    resources.store_metadata_media.side_effect = (
        lambda metadata, *_args: metadata is rom.gamelist_metadata
    )

    await _download(rom, [MetadataSource.SS, MetadataSource.GAMELIST])

    written = resources.update_rom.call_args.args[1]
    assert written["gamelist_metadata"] is rom.gamelist_metadata
    assert "ss_metadata" not in written


@pytest.mark.asyncio
async def test_a_failed_download_leaves_none_running(resources: SimpleNamespace):
    finished = MagicMock()

    async def manual(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(0.01)
        finished()

    resources.get_cover.side_effect = ValueError("bad cover url")
    resources.get_manual.side_effect = manual

    with pytest.raises(ValueError):
        await _download(_rom(), [MetadataSource.SS])

    finished.assert_called_once()
    resources.update_rom.assert_not_called()


@pytest.mark.asyncio
async def test_a_failed_provider_download_still_saves_the_paths_that_landed(
    resources: SimpleNamespace,
):
    resources.get_cover.return_value = ("small.png", "big.png")
    resources.store_ra_badge.side_effect = OSError("disk full")

    with pytest.raises(OSError):
        await _download(_rom(), [MetadataSource.RA])

    written = resources.update_rom.call_args.args[1]
    assert written["path_cover_l"] == "big.png"
