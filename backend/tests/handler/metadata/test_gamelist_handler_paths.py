"""gamelist.xml paths the main suite leaves out: the platform file lookup, the
cache, every stored media path, and the entries and failures a parse skips."""

from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import Element  # trunk-ignore(bandit/B405)

import pytest

from config.config_manager import MetadataMediaType
from handler.filesystem import fs_platform_handler
from handler.metadata import gamelist_handler
from handler.metadata.gamelist_handler import (
    GamelistHandler,
    GamelistMetadata,
    _is_directory_entry,
    get_preferred_media_types,
    populate_rom_specific_paths,
)
from models.platform import Platform
from models.rom import Rom


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fs_platform_handler, "base_path", tmp_path)
    return tmp_path


def _gamelist(library: Path, platform: Platform, games: str) -> Path:
    platform_dir = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)
    path = library / platform_dir / "gamelist.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<?xml version="1.0"?>\n<gameList>{games}</gameList>', encoding="utf-8"
    )
    return path


def _metadata() -> GamelistMetadata:
    return GamelistMetadata(
        box2d_url=None,
        box2d_back_url=None,
        box3d_url=None,
        fanart_url=None,
        image_url=None,
        manual_url=None,
        marquee_url=None,
        miximage_url=None,
        miximage_v2_url=None,
        physical_url=None,
        screenshot_url=None,
        thumbnail_url=None,
        title_screen_url=None,
        video_url=None,
        rating=None,
        first_release_date=None,
        sort_name=None,
        companies=None,
        publishers=None,
        developers=None,
        franchises=None,
        genres=None,
        player_count=None,
        md5_hash=None,
        box2d_back_path=None,
        box3d_path=None,
        fanart_path=None,
        miximage_path=None,
        miximage_v2_path=None,
        physical_path=None,
        marquee_path=None,
        title_screen_path=None,
        video_path=None,
    )


def test_every_preferred_media_type_gets_its_stored_path():
    metadata = _metadata()
    metadata["box2d_back_url"] = "file:///media/box2d_back.png"
    metadata["box3d_url"] = "file:///media/box3d.png"
    metadata["fanart_url"] = "file:///media/fanart.png"
    metadata["marquee_url"] = "file:///media/marquee.png"
    metadata["miximage_url"] = "file:///media/miximage.png"
    metadata["miximage_v2_url"] = "file:///media/miximage_v2.png"
    metadata["physical_url"] = "file:///media/physical.png"
    metadata["title_screen_url"] = "file:///media/title_screen.png"
    metadata["video_url"] = "file:///media/video.mp4"
    rom = Rom(id=7, platform_id=3)

    with patch(
        "handler.metadata.gamelist_handler.get_preferred_media_types",
        return_value=list(MetadataMediaType),
    ):
        paths = populate_rom_specific_paths(metadata, rom)

    assert paths == {
        "box2d_back_path": "roms/3/7/box2d_back/box2d_back.png",
        "box3d_path": "roms/3/7/box3d/box3d.png",
        "fanart_path": "roms/3/7/fanart/fanart.png",
        "marquee_path": "roms/3/7/marquee/marquee.png",
        "miximage_path": "roms/3/7/miximage/miximage.png",
        "miximage_v2_path": "roms/3/7/miximage_v2/miximage_v2.png",
        "physical_path": "roms/3/7/physical/physical.png",
        "title_screen_path": "roms/3/7/title_screen/title_screen.png",
        "video_path": "roms/3/7/video/video.mp4",
    }


def test_preferred_media_types_come_from_the_config():
    assert all(isinstance(m, MetadataMediaType) for m in get_preferred_media_types())


def test_a_path_outside_the_library_is_not_a_directory(library: Path):
    assert (
        _is_directory_entry(
            Element("game"),
            "platform",
            "../../outside",
            fs_platform_handler.validate_path,
        )
        is False
    )


class TestHandler:
    async def test_populate_cache_reads_the_platform_gamelist(
        self, library: Path, platform: Platform
    ):
        _gamelist(
            library,
            platform,
            "<game><path>./zelda.zip</path><name>Zelda</name></game>",
        )
        handler = GamelistHandler()

        await handler.populate_cache(platform)

        assert handler._gamelist_cache[platform.id]["zelda.zip"].get("name") == (
            "Zelda"
        )
        assert await handler.heartbeat() is True
        handler.clear_cache()
        assert handler._gamelist_cache == {}

    async def test_a_platform_without_a_gamelist_has_no_match(
        self, library: Path, platform: Platform
    ):
        handler = GamelistHandler()

        await handler.populate_cache(platform)
        rom = await handler.get_rom("zelda.zip", platform, Rom(fs_path=""))

        assert handler._gamelist_cache == {}
        assert rom == {"gamelist_id": None}

    async def test_a_matched_rom_gets_its_manual_and_stored_paths(
        self, library: Path, platform: Platform
    ):
        gamelist = _gamelist(
            library,
            platform,
            "<game><path>./zelda.zip</path><name>Zelda</name>"
            "<manual>./manuals/zelda.pdf</manual>"
            "<fanart>./fanart/zelda.png</fanart></game>",
        )
        for media in ("manuals/zelda.pdf", "fanart/zelda.png"):
            (gamelist.parent / media).parent.mkdir(exist_ok=True)
            (gamelist.parent / media).write_bytes(b"")
        handler = GamelistHandler()
        rom = Rom(id=7, platform_id=platform.id, fs_path="")

        with patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[MetadataMediaType.MANUAL, MetadataMediaType.FANART],
        ):
            matched = await handler.get_rom("zelda.zip", platform, rom)

        assert matched.get("url_manual", "").endswith("zelda.pdf")
        metadata = matched.get("gamelist_metadata")
        assert metadata is not None
        assert metadata["fanart_path"] == f"roms/{platform.id}/7/fanart/fanart.png"

    async def test_entries_without_a_path_are_skipped(
        self, library: Path, platform: Platform
    ):
        gamelist = _gamelist(
            library,
            platform,
            "<game><name>No Path</name></game>"
            "<game><path/></game>"
            "<game><path>./zelda.zip</path><name>Zelda</name></game>",
        )

        roms = GamelistHandler()._parse_gamelist_xml(gamelist, platform)

        assert {key: r.get("name") for key, r in roms.items()} == {"zelda.zip": "Zelda"}

    async def test_an_unreadable_library_yields_nothing(
        self, library: Path, platform: Platform
    ):
        gamelist = _gamelist(library, platform, "<game><path>./zelda.zip</path></game>")

        with patch.object(
            gamelist_handler,
            "build_media_file_index",
            side_effect=OSError("media folder vanished"),
        ):
            assert GamelistHandler()._parse_gamelist_xml(gamelist, platform) == {}
