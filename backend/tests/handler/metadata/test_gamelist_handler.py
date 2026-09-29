from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest
from defusedxml import ElementTree as ET

from config.config_manager import MetadataMediaType
from handler.filesystem import fs_platform_handler
from handler.metadata.gamelist_handler import (
    ESDE_MEDIA_MAP,
    GamelistHandler,
    GamelistMetadataMedia,
    build_media_file_index,
    extract_media_from_gamelist_rom,
    extract_metadata_from_gamelist_rom,
    populate_rom_specific_paths,
)
from models.platform import Platform
from models.rom import Rom

MOCK_METADATA = {
    "box2d_url": None,
    "image_url": None,
    "manual_url": None,
    "screenshot_url": None,
    "sort_name": None,
    "title_screen_url": None,
}

MOCK_MEDIA = {
    "box2d_url": None,
    "image_url": None,
    "manual_url": None,
    "screenshot_url": None,
    "title_screen_url": None,
}


def test_parse_gamelist_xml_includes_folder_entries(tmp_path: Path, platform: Platform):
    gamelist_path = tmp_path / "gamelist.xml"
    gamelist_path.write_text(
        """<?xml version="1.0"?>
<gameList>
  <folder>
    <path>./Subfolder</path>
    <name>Folder Entry</name>
    <desc>Folder summary</desc>
    <lang>en, fr</lang>
    <region>us, eu</region>
  </folder>
</gameList>""",
        encoding="utf-8",
    )
    handler = GamelistHandler()

    with (
        patch(
            "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
            return_value=MOCK_METADATA,
        ),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
    ):
        roms_data = handler._parse_gamelist_xml(gamelist_path, platform)

    assert "Subfolder" in roms_data
    folder_entry = roms_data["Subfolder"]
    assert folder_entry.get("name") == "Folder Entry"
    assert folder_entry.get("summary") == "Folder summary"
    assert folder_entry.get("languages") == ["English", "French"]
    assert folder_entry.get("regions") == ["USA", "Europe"]


def test_parse_gamelist_xml_keeps_game_entries(tmp_path: Path, platform: Platform):
    gamelist_path = tmp_path / "gamelist.xml"
    gamelist_path.write_text(
        """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./test-rom.zip</path>
    <name>Game Entry</name>
  </game>
</gameList>""",
        encoding="utf-8",
    )
    handler = GamelistHandler()

    with (
        patch(
            "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
            return_value=MOCK_METADATA,
        ),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
    ):
        roms_data = handler._parse_gamelist_xml(gamelist_path, platform)

    assert "test-rom.zip" in roms_data
    assert roms_data["test-rom.zip"].get("name") == "Game Entry"


def test_parse_gamelist_xml_keys_entries_by_path(tmp_path: Path, platform: Platform):
    """Nested entries keep their own metadata, and a bare file name is a fallback
    key only while it points at a single entry."""
    gamelist_path = tmp_path / "gamelist.xml"
    gamelist_path.write_text(
        """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./USA/shared.zip</path>
    <name>USA Release</name>
  </game>
  <game>
    <path>./Japan/shared.zip</path>
    <name>Japan Release</name>
  </game>
  <game>
    <path>./Disks/Set A/alone.zip</path>
    <name>Only One</name>
  </game>
</gameList>""",
        encoding="utf-8",
    )
    handler = GamelistHandler()

    with (
        patch(
            "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
            return_value=MOCK_METADATA,
        ),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
    ):
        roms_data = handler._parse_gamelist_xml(gamelist_path, platform)

    assert roms_data["USA/shared.zip"].get("name") == "USA Release"
    assert roms_data["Japan/shared.zip"].get("name") == "Japan Release"
    assert "shared.zip" not in roms_data
    assert roms_data["alone.zip"].get("name") == "Only One"


@pytest.mark.asyncio
async def test_get_rom_matches_the_folder_the_rom_sits_in(
    tmp_path: Path, platform: Platform
):
    gamelist_path = tmp_path / "gamelist.xml"
    gamelist_path.write_text(
        """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./USA/shared.zip</path>
    <name>USA Release</name>
  </game>
  <game>
    <path>./Japan/shared.zip</path>
    <name>Japan Release</name>
  </game>
</gameList>""",
        encoding="utf-8",
    )
    handler = GamelistHandler()
    platform_fs_path = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)

    matched: dict[str, str | None] = {}
    with (
        patch(
            "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
            return_value=MOCK_METADATA,
        ),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
        patch.object(handler, "_find_gamelist_file", return_value=gamelist_path),
    ):
        for folder in ("USA", "Japan"):
            rom = Rom(
                platform_id=platform.id,
                fs_name="shared.zip",
                fs_path=f"{platform_fs_path}/{folder}",
            )
            result = await handler.get_rom("shared.zip", platform, rom)
            matched[folder] = result.get("name")

    assert matched == {"USA": "USA Release", "Japan": "Japan Release"}


def test_parse_gamelist_xml_limited_to_file_names_skips_other_entries(
    tmp_path: Path, platform: Platform
):
    gamelist_path = _write_gamelist(
        tmp_path,
        platform,
        "<game><path>./USA/shared.zip</path><name>USA</name></game>"
        "<game><path>./Japan/shared.zip</path><name>Japan</name></game>"
        "<game><path>./Other.zip</path><name>Other</name></game>",
    )
    handler = GamelistHandler()

    with (
        patch(
            "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
            return_value=MOCK_METADATA,
        ) as extract,
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
    ):
        roms_data = handler._parse_gamelist_xml(
            gamelist_path, platform, fs_names=frozenset({"shared.zip"})
        )

    assert extract.call_count == 2
    assert set(roms_data) == {"USA/shared.zip", "Japan/shared.zip"}


@pytest.mark.asyncio
async def test_get_rom_outside_a_limited_cache_widens_it_to_that_rom(
    tmp_path: Path, platform: Platform
):
    gamelist_path = _write_gamelist(
        tmp_path,
        platform,
        "<game><path>./One.zip</path><name>One</name></game>"
        "<game><path>./Two.zip</path><name>Two</name></game>"
        "<game><path>./Three.zip</path><name>Three</name></game>",
    )
    handler = GamelistHandler()
    platform_fs_path = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)

    def rom_named(fs_name: str) -> Rom:
        return Rom(platform_id=platform.id, fs_name=fs_name, fs_path=platform_fs_path)

    with (
        patch(
            "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
            return_value=MOCK_METADATA,
        ) as extract,
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
        patch.object(handler, "_find_gamelist_file", return_value=gamelist_path),
    ):
        await handler.populate_cache(platform, fs_names=["One.zip"])
        one = await handler.get_rom("One.zip", platform, rom_named("One.zip"))
        assert extract.call_count == 1

        two = await handler.get_rom("Two.zip", platform, rom_named("Two.zip"))
        assert extract.call_count == 2

        await handler.get_rom("One.zip", platform, rom_named("One.zip"))
        await handler.populate_cache(platform, fs_names=["Two.zip"])
        assert extract.call_count == 2

    assert set(handler._gamelist_cache[platform.id]) == {"One.zip", "Two.zip"}

    assert one.get("name") == "One"
    assert two.get("name") == "Two"


def test_parse_gamelist_xml_title_screen_not_in_screenshots(
    tmp_path: Path, platform: Platform
):
    """The title screen is stored in its dedicated media folder, so it must
    not also land in url_screenshots (issue #3911)."""
    gamelist_path = tmp_path / "gamelist.xml"
    gamelist_path.write_text(
        """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./test-rom.zip</path>
    <name>Game Entry</name>
  </game>
</gameList>""",
        encoding="utf-8",
    )
    handler = GamelistHandler()

    metadata = dict(
        MOCK_METADATA,
        screenshot_url="file:///media/screenshot.png",
        title_screen_url="file:///media/titlescreen.png",
    )
    with (
        patch(
            "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
            return_value=metadata,
        ),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[
                MetadataMediaType.SCREENSHOT,
                MetadataMediaType.TITLE_SCREEN,
            ],
        ),
    ):
        roms_data = handler._parse_gamelist_xml(gamelist_path, platform)

    assert roms_data["test-rom.zip"]["url_screenshots"] == [
        "file:///media/screenshot.png"
    ]


def test_extract_metadata_from_gamelist_rom_includes_sort_name(platform: Platform):
    game = ET.fromstring("""<game>
  <path>./test-rom.zip</path>
  <sortname>Akumajou Dracula</sortname>
</game>""")

    with patch(
        "handler.metadata.gamelist_handler.extract_media_from_gamelist_rom",
        return_value=MOCK_MEDIA,
    ):
        metadata = extract_metadata_from_gamelist_rom(game, platform, {})

    assert metadata["sort_name"] == "Akumajou Dracula"


def _platform_dir(platform: Platform) -> str:
    return fs_platform_handler.get_platform_fs_structure(platform.fs_slug)


def _write_media(root: Path, platform: Platform, folder: str, name: str) -> None:
    media_dir = root / _platform_dir(platform) / folder
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / name).write_bytes(b"")


def _extract_media(
    tmp_path: Path, platform: Platform, game_xml: str
) -> GamelistMetadataMedia:
    with patch.object(fs_platform_handler, "base_path", tmp_path):
        return extract_media_from_gamelist_rom(
            ET.fromstring(game_xml), platform, build_media_file_index(platform)
        )


def _write_gamelist(tmp_path: Path, platform: Platform, games_xml: str) -> Path:
    gamelist_path = tmp_path / _platform_dir(platform) / "gamelist.xml"
    gamelist_path.parent.mkdir(parents=True, exist_ok=True)
    gamelist_path.write_text(
        f'<?xml version="1.0"?>\n<gameList>{games_xml}</gameList>', encoding="utf-8"
    )
    return gamelist_path


def test_build_media_file_index_maps_stems_to_uris(tmp_path: Path, platform: Platform):
    _write_media(tmp_path, platform, "covers", "Game.png")
    _write_media(tmp_path, platform, "videos", "Game.mp4")
    platform_dir = _platform_dir(platform)
    (tmp_path / platform_dir / "covers" / "Other.d").mkdir()

    with patch.object(fs_platform_handler, "base_path", tmp_path):
        index = build_media_file_index(platform)

    assert index["box2d_url"] == {"Game": f"file://{platform_dir}/covers/Game.png"}
    assert index["video_url"] == {"Game": f"file://{platform_dir}/videos/Game.mp4"}
    assert index["manual_url"] == {}


def test_build_media_file_index_follows_esde_extension_order(
    tmp_path: Path, platform: Platform
):
    for name in ("Game.jpg", "Game.png", "Game.webp"):
        _write_media(tmp_path, platform, "covers", name)
    for name in ("Game.avi", "Game.mkv", "Game.mp4"):
        _write_media(tmp_path, platform, "videos", name)
    platform_dir = _platform_dir(platform)

    with patch.object(fs_platform_handler, "base_path", tmp_path):
        index = build_media_file_index(platform)

    assert index["box2d_url"]["Game"] == f"file://{platform_dir}/covers/Game.png"
    assert index["video_url"]["Game"] == f"file://{platform_dir}/videos/Game.mp4"


@pytest.mark.parametrize(
    "media_names, game_xml, expected",
    [
        # A name with a dot in it isn't a prefix of a longer title
        (
            ["Super Mario Bros. 3.png"],
            "<game><path>./Super Mario Bros.zip</path></game>",
            None,
        ),
        (
            ["Super Mario Bros. 3.png"],
            "<game><path>./Super Mario Bros. 3.zip</path></game>",
            "covers/Super Mario Bros. 3.png",
        ),
        # Directories are named in full
        (
            ["Final Fantasy VII.m3u.png"],
            "<game><path>./Final Fantasy VII.m3u</path></game>",
            "covers/Final Fantasy VII.m3u.png",
        ),
        (
            ["Dr.png", "Dr. Mario.png"],
            "<folder><path>./Dr. Mario</path></folder>",
            "covers/Dr. Mario.png",
        ),
        # A file keeps its stem when media exists under both names
        (
            ["Game.png", "Game.zip.png"],
            "<game><path>./Game.zip</path></game>",
            "covers/Game.png",
        ),
        # An explicit tag wins over the media folder
        (
            ["Game.png"],
            "<game><path>./Game.zip</path><cover>./art/box.png</cover></game>",
            "art/box.png",
        ),
    ],
)
def test_extract_media_matches_the_rom_name(
    tmp_path: Path,
    platform: Platform,
    media_names: list[str],
    game_xml: str,
    expected: str | None,
):
    for name in media_names:
        _write_media(tmp_path, platform, "covers", name)

    media = _extract_media(tmp_path, platform, game_xml)

    assert media["box2d_url"] == (
        f"file://{_platform_dir(platform)}/{expected}" if expected else None
    )


def test_extract_media_names_a_game_directory_in_full(
    tmp_path: Path, platform: Platform
):
    for name in ("Final Fantasy VII.png", "Final Fantasy VII.m3u.png"):
        _write_media(tmp_path, platform, "covers", name)
    (tmp_path / _platform_dir(platform) / "Final Fantasy VII.m3u").mkdir()

    media = _extract_media(
        tmp_path, platform, "<game><path>./Final Fantasy VII.m3u</path></game>"
    )

    assert media["box2d_url"] == (
        f"file://{_platform_dir(platform)}/covers/Final Fantasy VII.m3u.png"
    )


def test_parse_gamelist_xml_indexes_media_once(tmp_path: Path, platform: Platform):
    for name in ("One", "Two", "Three"):
        _write_media(tmp_path, platform, "covers", f"{name}.png")
    gamelist_path = _write_gamelist(
        tmp_path,
        platform,
        "<game><path>./One.zip</path></game>"
        "<game><path>./Two.zip</path></game>"
        "<game><path>./Three.zip</path></game>",
    )

    with (
        patch.object(fs_platform_handler, "base_path", tmp_path),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
        patch(
            "handler.metadata.gamelist_handler.build_media_file_index",
            wraps=build_media_file_index,
        ) as build_index,
    ):
        roms_data = GamelistHandler()._parse_gamelist_xml(gamelist_path, platform)

    build_index.assert_called_once_with(platform)
    assert roms_data["Two.zip"].get("url_cover", "").endswith("/covers/Two.png")


def test_parse_gamelist_xml_skips_media_tags_outside_the_library(
    tmp_path: Path, platform: Platform
):
    _write_media(tmp_path, platform, "covers", "One.png")
    gamelist_path = _write_gamelist(
        tmp_path,
        platform,
        "<game><path>./One.zip</path><cover>/home/pi/covers/One.png</cover></game>"
        "<game><path>./Two.zip</path></game>",
    )

    with (
        patch.object(fs_platform_handler, "base_path", tmp_path),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
    ):
        roms_data = GamelistHandler()._parse_gamelist_xml(gamelist_path, platform)

    assert roms_data["One.zip"].get("url_cover", "").endswith("/covers/One.png")
    assert "Two.zip" in roms_data


def test_parse_gamelist_xml_follows_media_symlinked_out_of_the_library(
    tmp_path: Path, platform: Platform
):
    library = tmp_path / "library"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "One.png").write_bytes(b"")
    platform_dir = library / _platform_dir(platform)
    platform_dir.mkdir(parents=True)
    (platform_dir / "linked").symlink_to(outside, target_is_directory=True)
    gamelist_path = _write_gamelist(
        library,
        platform,
        "<game><path>./One.zip</path><cover>./linked/One.png</cover></game>",
    )

    with (
        patch.object(fs_platform_handler, "base_path", library),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
    ):
        roms_data = GamelistHandler()._parse_gamelist_xml(gamelist_path, platform)
        # The parse must agree with validate_path, which trusts in-library symlinks
        fs_platform_handler.validate_path(f"{_platform_dir(platform)}/linked/One.png")

    assert roms_data["One.zip"].get("url_cover") == (
        f"file://{_platform_dir(platform)}/linked/One.png"
    )


def test_parse_gamelist_xml_validates_each_media_folder_once(
    tmp_path: Path, platform: Platform
):
    gamelist_path = _write_gamelist(
        tmp_path,
        platform,
        "".join(
            f"<game><path>./{name}.zip</path><cover>./covers/{name}.png</cover>"
            f"<video>./videos/{name}.mp4</video></game>"
            for name in ("One", "Two", "Three")
        ),
    )

    with (
        patch.object(fs_platform_handler, "base_path", tmp_path),
        patch(
            "handler.metadata.gamelist_handler.get_preferred_media_types",
            return_value=[],
        ),
        patch(
            "handler.metadata.gamelist_handler.build_media_file_index",
            return_value={key: {} for key in ESDE_MEDIA_MAP},
        ),
        patch.object(
            fs_platform_handler,
            "validate_path",
            wraps=fs_platform_handler.validate_path,
        ) as validate_path,
    ):
        roms_data = GamelistHandler()._parse_gamelist_xml(gamelist_path, platform)

    platform_dir = _platform_dir(platform)
    assert Counter(call.args[0] for call in validate_path.call_args_list) == {
        f"{platform_dir}/covers": 1,
        f"{platform_dir}/videos": 1,
    }
    assert roms_data["Three.zip"].get("url_cover", "").endswith("/covers/Three.png")


@pytest.mark.parametrize(
    "url_key, media_type, expected_path_key, expected_filename",
    [
        (
            "box2d_back_url",
            MetadataMediaType.BOX2D_BACK,
            "box2d_back_path",
            "box2d_back.png",
        ),
        ("fanart_url", MetadataMediaType.FANART, "fanart_path", "fanart.png"),
    ],
)
def test_populate_rom_specific_paths_records_discovered_media(
    url_key, media_type, expected_path_key, expected_filename
):
    """Media the handler discovers locally must get a path recorded, otherwise
    it is never copied into the resources directory (issue #4128)."""
    rom = cast(Rom, SimpleNamespace(id=7, platform_id=3))
    metadata = dict(MOCK_METADATA, **{url_key: "file:///media/asset.png"})

    with patch(
        "handler.metadata.gamelist_handler.get_preferred_media_types",
        return_value=[media_type],
    ):
        paths = populate_rom_specific_paths(metadata, rom)  # type: ignore[arg-type]

    assert (
        paths[expected_path_key] == f"roms/3/7/{media_type.value}/{expected_filename}"
    )


def test_populate_rom_specific_paths_skips_unpreferred_media():
    rom = cast(Rom, SimpleNamespace(id=7, platform_id=3))
    metadata = dict(MOCK_METADATA, box2d_back_url="file:///media/back.png")

    with patch(
        "handler.metadata.gamelist_handler.get_preferred_media_types",
        return_value=[],
    ):
        paths = populate_rom_specific_paths(metadata, rom)  # type: ignore[arg-type]

    assert "box2d_back_path" not in paths


class TestGamelistHandler:
    def test_parse_gamelist_with_malformed_alternative_emulator_tag(self, tmp_path):
        gamelist_path = tmp_path / "gamelist.xml"
        gamelist_path.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<gameList>
  <game>
    <path>./Test Game.zip</path>
    <name>Test Game</name>
    <desc>Test Summary</desc>
    <alternativeEmulator label="RetroArch & Standalone">duckstation</alternativeEmulator>
  </game>
</gameList>
""",
            encoding="utf-8",
        )

        handler = GamelistHandler()
        platform = SimpleNamespace(id=1, fs_slug="psx")
        metadata = {
            "box2d_url": None,
            "image_url": None,
            "manual_url": None,
            "screenshot_url": None,
            "sort_name": None,
            "title_screen_url": None,
        }

        with (
            patch(
                "handler.metadata.gamelist_handler.get_preferred_media_types",
                return_value=[],
            ),
            patch(
                "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
                return_value=metadata,
            ),
        ):
            roms_data = handler._parse_gamelist_xml(
                gamelist_path, cast(Platform, platform)
            )

        assert "Test Game.zip" in roms_data
        assert roms_data["Test Game.zip"].get("name") == "Test Game"
        assert roms_data["Test Game.zip"].get("summary") == "Test Summary"

    def test_parse_gamelist_with_es_de_alternative_emulator_sibling(self, tmp_path):
        gamelist_path = tmp_path / "gamelist.xml"
        gamelist_path.write_text(
            """<?xml version="1.0"?>
<alternativeEmulator>
    <label>Gambatte</label>
</alternativeEmulator>
<gameList>
  <game>
    <path>./Tetris.gb</path>
    <name>Tetris</name>
    <desc>Block stacking</desc>
  </game>
</gameList>
""",
            encoding="utf-8",
        )

        handler = GamelistHandler()
        platform = SimpleNamespace(id=2, fs_slug="gb")
        metadata = {
            "box2d_url": None,
            "image_url": None,
            "manual_url": None,
            "screenshot_url": None,
            "sort_name": None,
            "title_screen_url": None,
        }

        with (
            patch(
                "handler.metadata.gamelist_handler.get_preferred_media_types",
                return_value=[],
            ),
            patch(
                "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
                return_value=metadata,
            ),
        ):
            roms_data = handler._parse_gamelist_xml(
                gamelist_path, cast(Platform, platform)
            )

        assert "Tetris.gb" in roms_data
        assert roms_data["Tetris.gb"].get("name") == "Tetris"
        assert roms_data["Tetris.gb"].get("summary") == "Block stacking"

    def test_parse_gamelist_with_trailing_alternative_emulator_sibling(self, tmp_path):
        """ES-DE may write the sibling after </gameList>.

        Games are parsed incrementally, so entries are already consumed by the
        time the trailing element makes the document invalid.
        """
        gamelist_path = tmp_path / "gamelist.xml"
        gamelist_path.write_text(
            """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./Tetris.gb</path>
    <name>Tetris</name>
    <desc>Block stacking</desc>
  </game>
  <game>
    <path>./Zelda.gb</path>
    <name>Zelda</name>
    <desc>Adventure</desc>
  </game>
</gameList>
<alternativeEmulator>
    <label>Gambatte</label>
</alternativeEmulator>
""",
            encoding="utf-8",
        )

        handler = GamelistHandler()
        platform = SimpleNamespace(id=3, fs_slug="gb")

        with (
            patch(
                "handler.metadata.gamelist_handler.get_preferred_media_types",
                return_value=[],
            ),
            patch(
                "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
                return_value=dict(MOCK_METADATA),
            ),
        ):
            roms_data = handler._parse_gamelist_xml(
                gamelist_path, cast(Platform, platform)
            )

        assert set(roms_data) == {"Tetris.gb", "Zelda.gb"}
        assert roms_data["Tetris.gb"].get("name") == "Tetris"
        assert roms_data["Zelda.gb"].get("summary") == "Adventure"

    def test_parse_gamelist_truncated_after_valid_entries_returns_nothing(
        self, tmp_path
    ):
        """A corrupt document imports nothing, not the part read before the error.

        Entries are streamed, so valid games are consumed before the parser
        reaches the damage.
        """
        gamelist_path = tmp_path / "gamelist.xml"
        gamelist_path.write_text(
            """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./Tetris.gb</path>
    <name>Tetris</name>
  </game>
  <game>
    <path>./Zelda.gb</path>
    <name>Zelda</name>
  </game>
  <game>
    <path>./Truncated.gb</path>
    <name>Trunca""",
            encoding="utf-8",
        )

        handler = GamelistHandler()
        platform = SimpleNamespace(id=4, fs_slug="gb")

        with (
            patch(
                "handler.metadata.gamelist_handler.get_preferred_media_types",
                return_value=[],
            ),
            patch(
                "handler.metadata.gamelist_handler.extract_metadata_from_gamelist_rom",
                return_value=dict(MOCK_METADATA),
            ),
        ):
            roms_data = handler._parse_gamelist_xml(
                gamelist_path, cast(Platform, platform)
            )

        assert roms_data == {}
        assert 4 not in handler._gamelist_cache

    def test_iter_game_elements_yields_only_game_and_folder(self, tmp_path):
        gamelist_path = tmp_path / "gamelist.xml"
        gamelist_path.write_text(
            """<?xml version="1.0"?>
<gameList>
  <provider><System>gb</System></provider>
  <game><path>./Tetris.gb</path></game>
  <folder><path>./Sub</path></folder>
</gameList>
""",
            encoding="utf-8",
        )

        handler = GamelistHandler()
        tags = [elem.tag for elem in handler._iter_game_elements(gamelist_path)]

        assert tags == ["game", "folder"]

    def test_iter_game_elements_filters_on_the_fallback_path(self, tmp_path):
        """The ES-DE sibling forces the fallback, which must filter identically."""
        gamelist_path = tmp_path / "gamelist.xml"
        gamelist_path.write_text(
            """<?xml version="1.0"?>
<alternativeEmulator>
    <label>Gambatte</label>
</alternativeEmulator>
<gameList>
  <provider><System>gb</System></provider>
  <game><path>./Tetris.gb</path></game>
  <folder><path>./Sub</path></folder>
</gameList>
""",
            encoding="utf-8",
        )

        handler = GamelistHandler()
        tags = [elem.tag for elem in handler._iter_game_elements(gamelist_path)]

        assert tags == ["game", "folder"]
