from types import SimpleNamespace
from unittest.mock import patch

from handler.metadata.gamelist_handler import GamelistHandler


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
            roms_data = handler._parse_gamelist_xml(gamelist_path, platform)

        assert "Test Game.zip" in roms_data
        assert roms_data["Test Game.zip"]["name"] == "Test Game"
        assert roms_data["Test Game.zip"]["summary"] == "Test Summary"
