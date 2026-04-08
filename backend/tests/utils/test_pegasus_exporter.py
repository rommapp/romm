from typing import TypedDict
from unittest.mock import MagicMock

import pytest

from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_resource_handler
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils.pegasus_exporter import PegasusExporter


class ParsedPegasus(TypedDict):
    collection: dict[str, str]
    games: list[dict[str, str | list[str]]]


def _mock_rom(**overrides) -> Rom:
    defaults = {
        "id": 1,
        "name": None,
        "fs_name": "rom.bin",
        "fs_name_no_tags": "rom",
        "fs_name_no_ext": "rom",
        "fs_resources_path": "roms/1/1",
        "summary": None,
        "regions": None,
        "languages": None,
        "tags": None,
        "ss_metadata": None,
        "gamelist_metadata": None,
        "path_cover_l": None,
        "path_screenshots": None,
        "path_video": None,
        "metadatum": None,
    }
    defaults.update(overrides)
    mock = MagicMock(spec=Rom)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _parse_pegasus(content: str) -> ParsedPegasus:
    result: ParsedPegasus = {"collection": {}, "games": []}
    current_game: dict[str, str | list[str]] | None = None
    current_key = None

    for line in content.splitlines():
        if not line.strip():
            if current_game:
                result["games"].append(current_game)
                current_game = None
                current_key = None
            continue

        if line.startswith("  "):
            if current_game and current_key:
                val = line.strip()
                if val == ".":
                    val = ""
                existing = current_game[current_key]
                if isinstance(existing, str):
                    current_game[current_key] = existing + "\n" + val
            continue

        if ":" not in line:
            continue

        key, _, value = line.partition(": ")
        value = value.strip()

        if key == "collection":
            result["collection"]["name"] = value
        elif key == "shortname":
            result["collection"]["shortname"] = value
        elif key == "game":
            if current_game:
                result["games"].append(current_game)
            current_game = {"game": value}
            current_key = None
        elif current_game is not None:
            if key in current_game:
                existing_value = current_game[key]
                if isinstance(existing_value, list):
                    existing_value.append(value)
                else:
                    current_game[key] = [existing_value, value]
            else:
                current_game[key] = value
            current_key = key

    if current_game:
        result["games"].append(current_game)

    return result


class TestExportMetadata:
    def test_full_metadata(self, admin_user: User):
        platform = Platform(
            name="Super Nintendo", slug="snes", fs_slug="snes", custom_name="SNES"
        )
        platform = db_platform_handler.add_platform(platform)

        rom = Rom(
            platform_id=platform.id,
            name="Super Mario World",
            slug="super-mario-world",
            fs_name="Super Mario World (USA).sfc",
            fs_name_no_tags="Super Mario World",
            fs_name_no_ext="Super Mario World (USA)",
            fs_extension="sfc",
            fs_path="snes/roms",
            summary="A classic platformer game.",
            regions=["USA"],
            languages=["en"],
            tags=["Retro"],
        )
        rom = db_rom_handler.add_rom(rom)
        db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)

        db_rom_handler.update_rom(
            rom.id,
            {
                "igdb_metadata": {
                    "genres": ["Platformer", "Adventure"],
                    "companies": ["Nintendo", "Nintendo EAD"],
                    "first_release_date": 709257600,  # 1992-06-23 UTC in seconds; view *1000
                    "total_rating": 92.0,  # view uses this directly as a 0-100 igdb_rating
                }
            },
        )

        exporter = PegasusExporter(local_export=True)
        parsed = _parse_pegasus(
            exporter.export_platform_to_pegasus(platform.id, request=None)
        )

        assert parsed["collection"] == {"name": "SNES", "shortname": "snes"}
        assert len(parsed["games"]) == 1
        game = parsed["games"][0]

        assert game["game"] == "Super Mario World"
        assert game["file"] == "Super Mario World (USA).sfc"
        assert game["developer"] == "Nintendo"
        assert game["publisher"] == "Nintendo EAD"
        assert game["genre"] == ["Platformer", "Adventure"]
        assert game["tag"] == "Retro"
        assert game["description"] == "A classic platformer game."
        assert game["rating"] == "92%"
        assert game["release"] == "1992-06-23"
        assert game["x-region"] == "USA"
        assert game["x-language"] == "en"
        assert "x-romm-id" in game
        assert "sort-by" not in game

    def test_minimal_rom(self, admin_user: User):
        platform = Platform(name="Game Boy", slug="gb", fs_slug="gb")
        platform = db_platform_handler.add_platform(platform)

        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=None,
                slug="unknown",
                fs_name="unknown.gb",
                fs_name_no_tags="unknown",
                fs_name_no_ext="unknown",
                fs_extension="gb",
                fs_path="gb/roms",
            )
        )

        parsed = _parse_pegasus(
            PegasusExporter(local_export=True).export_platform_to_pegasus(
                platform.id, request=None
            )
        )
        game = parsed["games"][0]
        assert game["game"] == "unknown.gb"
        assert game["file"] == "unknown.gb"
        for key in ("developer", "genre", "description", "rating", "release"):
            assert key not in game

    def test_skips_missing_roms(self, admin_user: User):
        platform = Platform(name="NES", slug="nes", fs_slug="nes")
        platform = db_platform_handler.add_platform(platform)

        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="missing.nes",
                slug="missing",
                fs_name="missing.nes",
                fs_name_no_tags="missing",
                fs_name_no_ext="missing",
                fs_extension="nes",
                fs_path="nes/roms",
                missing_from_fs=True,
            )
        )

        parsed = _parse_pegasus(
            PegasusExporter(local_export=True).export_platform_to_pegasus(
                platform.id, request=None
            )
        )
        assert len(parsed["games"]) == 0

    def test_invalid_platform(self):
        with pytest.raises(ValueError, match="not found"):
            PegasusExporter(local_export=True).export_platform_to_pegasus(
                99999, request=None
            )

    def test_multiline_description(self, admin_user: User):
        platform = Platform(name="GBA", slug="gba", fs_slug="gba")
        platform = db_platform_handler.add_platform(platform)

        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="Test",
                slug="test",
                fs_name="test.gba",
                fs_name_no_tags="test",
                fs_name_no_ext="test",
                fs_extension="gba",
                fs_path="gba/roms",
                summary="First line.\n\nThird line.",
            )
        )

        content = PegasusExporter(local_export=True).export_platform_to_pegasus(
            platform.id, request=None
        )
        assert "description: First line." in content
        assert "  ." in content
        assert "  Third line." in content


class TestFormatHelpers:
    def test_format_rating(self):
        exporter = PegasusExporter()
        assert exporter._format_rating(100.0) == "100%"
        assert exporter._format_rating(0.0) == "0%"
        assert exporter._format_rating(75.0) == "75%"

    def test_escape_multiline(self):
        exporter = PegasusExporter()
        assert exporter._escape_multiline("single line") == "single line"
        assert exporter._escape_multiline("line1\nline2") == "line1\n  line2"
        assert exporter._escape_multiline("line1\n\nline3") == "line1\n  .\n  line3"


class TestCollectAssets:
    def test_empty_when_no_paths(self):
        rom = _mock_rom(ss_metadata=None, gamelist_metadata=None)
        assert PegasusExporter(local_export=True)._collect_assets(rom) == {}

    def test_core_media(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs_resource_handler, "base_path", tmp_path)

        for rel in ["cover/big.png", "screenshots/0.jpg", "video/video.mp4"]:
            f = tmp_path / "roms" / "1" / "1" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"x")

        rom = _mock_rom(
            path_cover_l="roms/1/1/cover/big.png",
            path_screenshots=["roms/1/1/screenshots/0.jpg"],
            path_video="roms/1/1/video/video.mp4",
            ss_metadata=None,
            gamelist_metadata=None,
        )
        assets = PegasusExporter(local_export=True)._collect_assets(rom)

        assert assets["box_front"] == tmp_path / "roms/1/1/cover/big.png"
        assert assets["screenshot"] == tmp_path / "roms/1/1/screenshots/0.jpg"
        assert assets["video"] == tmp_path / "roms/1/1/video/video.mp4"

    @pytest.mark.parametrize(
        "ss_key, ss_value, expected_pegasus_key",
        [
            ("box3d_path", "roms/1/1/box3d/f.png", "box_full"),
            ("box2d_back_path", "roms/1/1/back/f.png", "box_back"),
            ("logo_path", "roms/1/1/logo/f.png", "logo"),
            ("physical_path", "roms/1/1/phys/f.png", "cartridge"),
            ("fanart_path", "roms/1/1/fan/f.jpg", "background"),
            ("title_screen_path", "roms/1/1/ts/f.png", "titlescreen"),
            ("bezel_path", "roms/1/1/bez/f.png", "bezel"),
        ],
    )
    def test_ss_metadata(
        self, tmp_path, monkeypatch, ss_key, ss_value, expected_pegasus_key
    ):
        monkeypatch.setattr(fs_resource_handler, "base_path", tmp_path)
        f = tmp_path / ss_value
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")

        rom = _mock_rom(ss_metadata={ss_key: ss_value}, gamelist_metadata=None)
        assets = PegasusExporter(local_export=True)._collect_assets(rom)
        assert assets[expected_pegasus_key] == f

    def test_gamelist_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs_resource_handler, "base_path", tmp_path)
        f = tmp_path / "roms/1/1/marquee/m.png"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")

        rom = _mock_rom(
            ss_metadata=None,
            gamelist_metadata={"marquee_path": "roms/1/1/marquee/m.png"},
        )
        assets = PegasusExporter(local_export=True)._collect_assets(rom)
        assert assets["marquee"] == f


class TestCopyAndEntry:
    def test_copy_asset(self, tmp_path):
        source = tmp_path / "source.png"
        source.write_bytes(b"data")
        dest = tmp_path / "out" / "dest.png"

        assert PegasusExporter(local_export=True)._copy_asset(source, dest)
        assert dest.read_bytes() == b"data"

    def test_copy_asset_skips_existing(self, tmp_path):
        source = tmp_path / "source.png"
        source.write_bytes(b"new")
        dest = tmp_path / "dest.png"
        dest.write_bytes(b"old")

        assert PegasusExporter(local_export=True)._copy_asset(source, dest)
        assert dest.read_bytes() == b"old"

    def test_game_entry_with_assets(self):
        metadatum = MagicMock()
        metadatum.companies = metadatum.genres = metadatum.player_count = None
        metadatum.first_release_date = metadatum.average_rating = None

        rom = _mock_rom(
            name="Test", fs_name="test.sfc", fs_name_no_tags="test", metadatum=metadatum
        )
        exported_assets = {
            "box_front": "assets/covers/test.png",
            "screenshot": "assets/screenshots/test.jpg",
            "video": "assets/videos/test.mp4",
        }

        entry = PegasusExporter(local_export=True)._create_game_entry(
            rom, request=None, exported_assets=exported_assets
        )
        for key, path in exported_assets.items():
            assert f"assets.{key}: {path}" in entry
