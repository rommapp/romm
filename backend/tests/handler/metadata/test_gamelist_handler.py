from pathlib import Path
from unittest.mock import patch

from handler.metadata.gamelist_handler import GamelistHandler
from models.platform import Platform

MOCK_METADATA = {
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
</gameList>"""
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
    assert folder_entry["name"] == "Folder Entry"
    assert folder_entry["summary"] == "Folder summary"
    assert folder_entry["languages"] == ["en", "fr"]
    assert folder_entry["regions"] == ["us", "eu"]


def test_parse_gamelist_xml_keeps_game_entries(tmp_path: Path, platform: Platform):
    gamelist_path = tmp_path / "gamelist.xml"
    gamelist_path.write_text(
        """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./test-rom.zip</path>
    <name>Game Entry</name>
  </game>
</gameList>"""
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
    assert roms_data["test-rom.zip"]["name"] == "Game Entry"
