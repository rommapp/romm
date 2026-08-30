from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest
from defusedxml import ElementTree as ET

from config.config_manager import MetadataMediaType
from handler.metadata.gamelist_handler import (
    GamelistHandler,
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
    assert folder_entry.get("languages") == ["en", "fr"]
    assert folder_entry.get("regions") == ["us", "eu"]


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
        metadata = extract_metadata_from_gamelist_rom(game, platform)

    assert metadata["sort_name"] == "Akumajou Dracula"


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
