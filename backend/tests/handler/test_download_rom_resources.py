import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from handler.scan_handler import MetadataSource, download_rom_resources


class _InFlight:
    """Counts overlapping calls, holding each one long enough to overlap."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    def returning(self, value: Any):
        async def call(*_args, **_kwargs):
            self.current += 1
            self.peak = max(self.peak, self.current)
            try:
                await asyncio.sleep(0.01)
            finally:
                self.current -= 1
            return value

        return call


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


@pytest.mark.asyncio
async def test_downloads_every_file_of_a_rom_together():
    tracker = _InFlight()
    rom = _rom()

    with (
        patch("handler.scan_handler.get_preferred_media_types", return_value=[]),
        patch("handler.scan_handler.db_rom_handler.update_rom") as update_rom,
        patch.multiple(
            "handler.scan_handler.fs_resource_handler",
            get_cover=tracker.returning(("small.png", "big.png")),
            get_manual=tracker.returning("manual.pdf"),
            get_rom_screenshots=tracker.returning(["0.jpg"]),
            store_metadata_media=tracker.returning(False),
            store_ra_badge=tracker.returning(None),
        ),
    ):
        await download_rom_resources(
            added_rom=rom,
            previous_url_cover=None,
            previous_url_manual=None,
            previous_url_screenshots=None,
            metadata_sources=[
                MetadataSource.SS,
                MetadataSource.GAMELIST,
                MetadataSource.RA,
            ],
        )

    # Cover, manual, screenshots, two provider dicts and two badges.
    assert tracker.peak == 7
    update_rom.assert_called_once_with(
        7,
        {
            "path_cover_s": "small.png",
            "path_cover_l": "big.png",
            "path_screenshots": ["0.jpg"],
            "path_manual": "manual.pdf",
        },
    )


@pytest.mark.asyncio
async def test_writes_back_only_the_provider_media_that_changed():
    rom = _rom()

    async def store_metadata_media(metadata, *_args):
        return metadata is rom.gamelist_metadata

    with (
        patch("handler.scan_handler.get_preferred_media_types", return_value=[]),
        patch("handler.scan_handler.db_rom_handler.update_rom") as update_rom,
        patch.multiple(
            "handler.scan_handler.fs_resource_handler",
            get_cover=_InFlight().returning((None, None)),
            get_manual=_InFlight().returning(None),
            get_rom_screenshots=_InFlight().returning([]),
            store_metadata_media=store_metadata_media,
            store_ra_badge=_InFlight().returning(None),
        ),
    ):
        await download_rom_resources(
            added_rom=rom,
            previous_url_cover=None,
            previous_url_manual=None,
            previous_url_screenshots=None,
            metadata_sources=[MetadataSource.SS, MetadataSource.GAMELIST],
        )

    written = update_rom.call_args.args[1]
    assert written["gamelist_metadata"] is rom.gamelist_metadata
    assert "ss_metadata" not in written
