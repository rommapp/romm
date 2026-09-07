from pathlib import Path
from typing import TypedDict
from unittest.mock import MagicMock

import pytest

from config.config_manager import PLATFORM_MEDIA_DIRS
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import (
    fs_platform_handler,
    fs_resource_handler,
    fs_rom_handler,
)
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils.pegasus_exporter import (
    PEGASUS_MEDIA_KEYS,
    PegasusExporter,
    canonical_pegasus_key,
    parse_pegasus,
)


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

        assert parsed["collection"] == {
            "name": "Super Nintendo Entertainment System",
            "shortname": "snes",
        }
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

    def test_prefers_explicit_publisher_developer(self, admin_user: User):
        platform = Platform(name="NES", slug="nes", fs_slug="nes")
        platform = db_platform_handler.add_platform(platform)

        rom = Rom(
            platform_id=platform.id,
            name="Test Game",
            slug="test-game",
            fs_name="test.nes",
            fs_name_no_tags="test",
            fs_name_no_ext="test",
            fs_extension="nes",
            fs_path="nes/roms",
        )
        rom = db_rom_handler.add_rom(rom)
        db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)

        # companies order would give developer=Atari / publisher=Artech; the
        # explicit split fields (reversed here) must take precedence.
        db_rom_handler.update_rom(
            rom.id,
            {
                "igdb_metadata": {
                    "companies": ["Atari", "Artech Studios"],
                    "publishers": ["Atari"],
                    "developers": ["Artech Studios"],
                }
            },
        )

        parsed = _parse_pegasus(
            PegasusExporter(local_export=True).export_platform_to_pegasus(
                platform.id, request=None
            )
        )
        game = parsed["games"][0]
        assert game["developer"] == "Artech Studios"
        assert game["publisher"] == "Atari"

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

    def test_skips_physical_roms(self, admin_user: User):
        platform = Platform(name="NES", slug="nes", fs_slug="nes")
        platform = db_platform_handler.add_platform(platform)

        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="Boxed Copy",
                slug="boxed-copy",
                fs_name="Boxed Copy",
                fs_name_no_tags="Boxed Copy",
                fs_name_no_ext="Boxed Copy",
                fs_extension="",
                fs_path="nes/roms/.physical",
                is_physical=True,
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

    def test_collection_name_mapped_slug(self, admin_user: User):
        """Known slug → canonical Pegasus name overrides RomM custom_name."""
        platform = Platform(
            name="Game Boy Advance", slug="gba", fs_slug="gba", custom_name="GBA"
        )
        platform = db_platform_handler.add_platform(platform)

        parsed = _parse_pegasus(
            PegasusExporter(local_export=True).export_platform_to_pegasus(
                platform.id, request=None
            )
        )
        assert parsed["collection"] == {
            "name": "Game Boy Advance",
            "shortname": "gba",
        }

    def test_collection_name_unmapped_slug_uses_custom_name(self, admin_user: User):
        """Unknown slug → falls back to custom_name (or name) and raw slug."""
        platform = Platform(
            name="My Homebrew Console",
            slug="my-homebrew",
            fs_slug="my-homebrew",
            custom_name="Homebrew",
        )
        platform = db_platform_handler.add_platform(platform)

        parsed = _parse_pegasus(
            PegasusExporter(local_export=True).export_platform_to_pegasus(
                platform.id, request=None
            )
        )
        assert parsed["collection"] == {
            "name": "Homebrew",
            "shortname": "my-homebrew",
        }

    def test_collection_name_unmapped_slug_no_custom_name(self, admin_user: User):
        """Unknown slug, no custom_name → falls back to platform.name and raw slug."""
        platform = Platform(
            name="Obscure Platform",
            slug="obscure-plat",
            fs_slug="obscure-plat",
        )
        platform = db_platform_handler.add_platform(platform)

        parsed = _parse_pegasus(
            PegasusExporter(local_export=True).export_platform_to_pegasus(
                platform.id, request=None
            )
        )
        assert parsed["collection"] == {
            "name": "Obscure Platform",
            "shortname": "obscure-plat",
        }

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

    @pytest.mark.parametrize(
        "gl_key, gl_value, expected_pegasus_key",
        [
            ("marquee_path", "roms/1/1/marquee/m.png", "marquee"),
            ("box2d_back_path", "roms/1/1/box2d_back/b.png", "box_back"),
            ("fanart_path", "roms/1/1/fanart/f.jpg", "background"),
        ],
    )
    def test_gamelist_metadata(
        self, tmp_path, monkeypatch, gl_key, gl_value, expected_pegasus_key
    ):
        monkeypatch.setattr(fs_resource_handler, "base_path", tmp_path)
        f = tmp_path / gl_value
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")

        rom = _mock_rom(ss_metadata=None, gamelist_metadata={gl_key: gl_value})
        assets = PegasusExporter(local_export=True)._collect_assets(rom)
        assert assets[expected_pegasus_key] == f


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
        metadatum.publishers = metadatum.developers = None
        metadatum.first_release_date = metadatum.average_rating = None

        rom = _mock_rom(
            name="Test", fs_name="test.sfc", fs_name_no_tags="test", metadatum=metadatum
        )
        exported_assets = {
            "box_front": "covers/test.png",
            "screenshot": "screenshots/test.jpg",
            "video": "videos/test.mp4",
        }

        entry = PegasusExporter(local_export=True)._create_game_entry(
            rom, request=None, exported_assets=exported_assets
        )
        for key, path in exported_assets.items():
            assert f"assets.{key}: {path}" in entry


@pytest.fixture
def snes_platform(admin_user: User) -> Platform:
    platform = db_platform_handler.add_platform(
        Platform(name="Super Nintendo", slug="snes", fs_slug="snes")
    )
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Super Mario World",
            slug="super-mario-world",
            fs_name="Super Mario World (USA).sfc",
            fs_name_no_tags="Super Mario World",
            fs_name_no_ext="Super Mario World (USA)",
            fs_extension="sfc",
            fs_path="snes/roms",
            summary="A classic platformer game.",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    db_rom_handler.update_rom(
        rom.id, {"igdb_metadata": {"genres": ["Platformer", "Adventure"]}}
    )
    return platform


@pytest.fixture
def metadata_file(tmp_path, monkeypatch, snes_platform: Platform) -> Path:
    """Path of the platform's metadata.pegasus.txt inside a temp library."""
    library_base = tmp_path / "library"
    monkeypatch.setattr(fs_platform_handler, "base_path", library_base)
    platform_dir = library_base / fs_platform_handler.get_platform_fs_structure(
        snes_platform.fs_slug
    )
    platform_dir.mkdir(parents=True)
    return platform_dir / "metadata.pegasus.txt"


def _write_metadata(metadata_file: Path, content: str | bytes) -> None:
    if isinstance(content, bytes):
        metadata_file.write_bytes(content)
    else:
        metadata_file.write_text(content, encoding="utf-8")


def _read_metadata(metadata_file: Path) -> str:
    return metadata_file.read_text(encoding="utf-8")


def _read_metadata_bytes(metadata_file: Path) -> bytes:
    return metadata_file.read_bytes()


class TestExportToFile:
    async def test_keeps_collection_and_game_extras(
        self, snes_platform: Platform, metadata_file: Path
    ):
        """Launch commands and custom fields survive; RomM's own keys replace
        the old values; unknown games are carried over untouched."""
        _write_metadata(
            metadata_file,
            """# hand-maintained
collection: Old SNES
shortname: oldsnes
launch: retroarch -L snes9x_libretro.so {file.path}
extensions: sfc, smc

game: Old Title
file: ./Super Mario World (USA).sfc
launch: custom-launcher {file.path}
x-favorite: yes
genre: Old Genre
description: Old description

game: Not In RomM
file: Missing.sfc
description: kept as is
""",
        )

        exporter = PegasusExporter(local_export=True)
        assert (
            await exporter.export_platform_to_file(snes_platform.id, request=None)
            is True
        )

        content = _read_metadata(metadata_file)
        assert content.startswith("# hand-maintained\n")
        header, _, _ = content.partition("\n\n")
        assert header.splitlines() == [
            "# hand-maintained",
            "collection: Super Nintendo Entertainment System",
            "shortname: snes",
            "launch: retroarch -L snes9x_libretro.so {file.path}",
            "extensions: sfc, smc",
        ]

        parsed = _parse_pegasus(content)
        assert len(parsed["games"]) == 2
        mario, missing = parsed["games"]
        assert mario["game"] == "Super Mario World"
        assert mario["file"] == "Super Mario World (USA).sfc"
        assert mario["launch"] == "custom-launcher {file.path}"
        assert mario["x-favorite"] == "yes"
        assert mario["genre"] == ["Platformer", "Adventure"]
        assert mario["description"] == "A classic platformer game."
        assert missing == {
            "game": "Not In RomM",
            "file": "Missing.sfc",
            "description": "kept as is",
        }

    async def test_matches_files_list_and_keeps_later_collections(
        self, snes_platform: Platform, metadata_file: Path
    ):
        """A ROM listed under `files:` is recognised, and any collection after
        the first is written back verbatim after RomM's entries."""
        _write_metadata(
            metadata_file,
            """collection: SNES
shortname: snes

game: Multi
files:
  Disc1.chd
  Super Mario World (USA).sfc
x-note: multi

collection: Hacks
shortname: hacks
launch: other-emulator {file.path}

game: Hack
file: hack.sfc
""",
        )

        exporter = PegasusExporter(local_export=True)
        assert (
            await exporter.export_platform_to_file(snes_platform.id, request=None)
            is True
        )

        content = _read_metadata(metadata_file)
        assert "files:" not in content
        assert "game: Multi" not in content
        assert content.index("x-romm-id") < content.index("collection: Hacks")
        assert content.endswith(
            "collection: Hacks\n"
            "shortname: hacks\n"
            "launch: other-emulator {file.path}\n"
            "\n"
            "game: Hack\n"
            "file: hack.sfc\n"
        )

        mario = _parse_pegasus(content)["games"][0]
        assert mario["game"] == "Super Mario World"
        assert mario["file"] == "Super Mario World (USA).sfc"
        assert mario["x-note"] == "multi"

    async def test_refuses_to_overwrite_undecodable_file(
        self, snes_platform: Platform, metadata_file: Path
    ):
        _write_metadata(metadata_file, b"\xff\xfe not utf-8")

        exporter = PegasusExporter(local_export=True)
        assert (
            await exporter.export_platform_to_file(snes_platform.id, request=None)
            is False
        )
        assert _read_metadata_bytes(metadata_file) == b"\xff\xfe not utf-8"

    async def test_reads_bom_prefixed_file(
        self, snes_platform: Platform, metadata_file: Path
    ):
        """A UTF-8 BOM does not hide the collection header or the game keys."""
        _write_metadata(
            metadata_file,
            "﻿collection: SNES\nshortname: snes\n\n"
            "game: Old\nfile: Super Mario World (USA).sfc\nx-favorite: yes\n",
        )

        exporter = PegasusExporter(local_export=True)
        assert (
            await exporter.export_platform_to_file(snes_platform.id, request=None)
            is True
        )

        content = _read_metadata(metadata_file)
        assert content.count("collection:") == 1
        assert content.startswith("collection: Super Nintendo Entertainment System\n")
        assert content.count("game:") == 1
        assert _parse_pegasus(content)["games"][0]["x-favorite"] == "yes"

    async def test_matches_multi_file_rom_by_folder(
        self, admin_user: User, snes_platform: Platform, metadata_file: Path
    ):
        """A block listing the discs of a game folder merges into RomM's entry
        for that folder instead of being duplicated."""
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=snes_platform.id,
                name="Multi Disc Game",
                slug="multi-disc-game",
                fs_name="Multi Disc Game (USA)",
                fs_name_no_tags="Multi Disc Game",
                fs_name_no_ext="Multi Disc Game (USA)",
                fs_extension="",
                fs_path="snes/roms",
                multi_file=True,
            )
        )
        db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
        _write_metadata(
            metadata_file,
            """collection: SNES
shortname: snes

game: Multi Disc
files:
  ./Multi Disc Game (USA)/disc1.chd
  ./Multi Disc Game (USA)/disc2.chd
x-note: discs
""",
        )

        exporter = PegasusExporter(local_export=True)
        assert (
            await exporter.export_platform_to_file(snes_platform.id, request=None)
            is True
        )

        content = _read_metadata(metadata_file)
        assert "files:" not in content
        assert "game: Multi Disc\n" not in content
        games = {g["game"]: g for g in _parse_pegasus(content)["games"]}
        assert set(games) == {"Super Mario World", "Multi Disc Game"}
        assert games["Multi Disc Game"]["file"] == "Multi Disc Game (USA)"
        assert games["Multi Disc Game"]["x-note"] == "discs"

    @pytest.mark.parametrize(
        "alias",
        [
            "sort_by",
            "sortby",
            "sort-title",
            "sort_title",
            "sorttitle",
            "sort-name",
            "sort_name",
            "sortname",
        ],
    )
    async def test_sort_aliases_are_replaced(
        self, alias: str, snes_platform: Platform, metadata_file: Path
    ):
        """Every spelling Pegasus accepts for the sort title is replaced by
        RomM's `sort-by`, since Pegasus would otherwise apply the stale one."""
        rom = db_rom_handler.get_roms_scalar(platform_ids=[snes_platform.id])[0]
        db_rom_handler.update_rom(rom.id, {"name": "Super Mario World: SNES"})
        _write_metadata(
            metadata_file,
            f"collection: SNES\nshortname: snes\n\n"
            f"game: Old\nfile: Super Mario World (USA).sfc\n{alias}: Zzz\n",
        )

        exporter = PegasusExporter(local_export=True)
        assert (
            await exporter.export_platform_to_file(snes_platform.id, request=None)
            is True
        )

        content = _read_metadata(metadata_file)
        assert "Zzz" not in content
        mario = _parse_pegasus(content)["games"][0]
        assert mario["sort-by"] == "Super Mario World"
        assert parse_pegasus(content)[-1].keys() >= {"game", "file", "sort-by"}

    async def test_asset_aliases_are_replaced(
        self, tmp_path, monkeypatch, snes_platform: Platform, metadata_file: Path
    ):
        """`asset.` and `assets.` prefixes and Pegasus's asset-name spellings
        all count as the same key, so RomM's cover replaces the old one while
        assets RomM does not emit are kept verbatim."""
        monkeypatch.setattr(fs_resource_handler, "base_path", tmp_path)
        cover = tmp_path / "roms/snes/1/cover/big.png"
        cover.parent.mkdir(parents=True)
        cover.write_bytes(b"x")
        rom = db_rom_handler.get_roms_scalar(platform_ids=[snes_platform.id])[0]
        db_rom_handler.update_rom(rom.id, {"path_cover_l": "roms/snes/1/cover/big.png"})
        _write_metadata(
            metadata_file,
            """collection: SNES
shortname: snes

game: Old
file: Super Mario World (USA).sfc
asset.boxFront: old-cover.png
assets.videos: old-video.mp4
asset.wheel: keep-logo.png
""",
        )

        exporter = PegasusExporter(local_export=True)
        assert (
            await exporter.export_platform_to_file(snes_platform.id, request=None)
            is True
        )

        content = _read_metadata(metadata_file)
        assert "old-cover.png" not in content
        assert "assets.box_front: covers/Super Mario World (USA).png" in content
        assert "assets.videos: old-video.mp4" in content
        assert "asset.wheel: keep-logo.png" in content
        assert content.count("box_front") == 1

    def test_media_keys_resolve_to_esde_dirs(self):
        assert set(PEGASUS_MEDIA_KEYS.values()).issubset(PLATFORM_MEDIA_DIRS.keys())

    @staticmethod
    async def _export(
        admin_user: User,
        tmp_path: Path,
        monkeypatch,
        rom_fields: dict[str, object],
        sources: dict[str, bytes],
    ) -> tuple[Path, str]:
        """Export one SNES ROM with ``rom_fields`` applied and ``sources``
        present under the resources base. Returns the platform dir and the
        written metadata.pegasus.txt."""
        resources_base = tmp_path / "resources"
        library_base = tmp_path / "library"
        monkeypatch.setattr(fs_resource_handler, "base_path", resources_base)
        monkeypatch.setattr(fs_platform_handler, "base_path", library_base)

        platform = db_platform_handler.add_platform(
            Platform(name="Super Nintendo", slug="snes", fs_slug="snes")
        )
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="Super Mario World",
                slug="super-mario-world",
                fs_name="Super Mario World (USA).sfc",
                fs_name_no_tags="Super Mario World",
                fs_name_no_ext="Super Mario World (USA)",
                fs_extension="sfc",
                fs_path="snes/roms",
            )
        )
        db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
        db_rom_handler.update_rom(rom.id, rom_fields)
        for rel, content in sources.items():
            src = resources_base / rel
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_bytes(content)

        exporter = PegasusExporter(local_export=True)
        assert await exporter.export_platform_to_file(platform.id, request=None)

        platform_dir = library_base / fs_platform_handler.get_platform_fs_structure(
            platform.fs_slug
        )
        return platform_dir, (platform_dir / "metadata.pegasus.txt").read_text()

    async def test_media_shares_esde_dirs(
        self, admin_user: User, tmp_path, monkeypatch
    ):
        """Media lands in the same per-type folders the gamelist export uses, so
        exporting for both frontends yields one copy and no assets/ tree."""
        platform_dir, content = await self._export(
            admin_user,
            tmp_path,
            monkeypatch,
            {
                "path_cover_l": "snes/covers/smw.jpg",
                "path_screenshots": ["snes/screenshots/smw-1.jpg"],
                "ss_metadata": {
                    "logo_path": "snes-ss/logo/smw.png",
                    "physical_path": "snes-ss/physical/smw.png",
                    "fanart_path": "snes-ss/fanart/smw.jpg",
                },
            },
            {
                rel: b"x"
                for rel in (
                    "snes/covers/smw.jpg",
                    "snes/screenshots/smw-1.jpg",
                    "snes-ss/logo/smw.png",
                    "snes-ss/physical/smw.png",
                    "snes-ss/fanart/smw.jpg",
                )
            },
        )

        expected = {
            "box_front": "covers/Super Mario World (USA).jpg",
            "screenshot": "screenshots/Super Mario World (USA).jpg",
            "logo": "marquees/Super Mario World (USA).png",
            "cartridge": "physicalmedia/Super Mario World (USA).png",
            "background": "fanart/Super Mario World (USA).jpg",
        }
        for rel in expected.values():
            assert (platform_dir / rel).is_file(), f"missing media {rel}"
        assert not (platform_dir / "assets").exists()

        for key, rel in expected.items():
            assert f"assets.{key}: {rel}" in content

        written_dirs = [p.name for p in platform_dir.iterdir() if p.is_dir()]
        assert written_dirs
        assert fs_rom_handler.exclude_multi_roms(written_dirs) == []

    async def test_logo_and_marquee_both_survive(
        self, admin_user: User, tmp_path, monkeypatch
    ):
        """Both map to marquees/; the second gets its own filename instead of
        being dropped or pointed at the first."""
        platform_dir, content = await self._export(
            admin_user,
            tmp_path,
            monkeypatch,
            {
                "ss_metadata": {"logo_path": "snes-ss/logo/smw.png"},
                "gamelist_metadata": {"marquee_path": "snes-gl/marquee/smw.png"},
            },
            {
                "snes-ss/logo/smw.png": b"logo",
                "snes-gl/marquee/smw.png": b"marquee",
            },
        )

        logo = platform_dir / "marquees/Super Mario World (USA).png"
        marquee = platform_dir / "marquees/Super Mario World (USA)-marquee.png"
        assert logo.read_bytes() == b"logo"
        assert marquee.read_bytes() == b"marquee"
        assert "assets.logo: marquees/Super Mario World (USA).png" in content
        assert "assets.marquee: marquees/Super Mario World (USA)-marquee.png" in content


@pytest.mark.parametrize(
    "key, expected",
    [
        ("asset.boxfront", "assets.box_front"),
        ("assets.boxart2d", "assets.box_front"),
        ("asset.box_front", "assets.box_front"),
        ("assets.screenshots", "assets.screenshot"),
        ("asset.videos", "assets.video"),
        ("asset.wheel", "assets.logo"),
        ("assets.border", "assets.bezel"),
        ("assets.titlescreen", "assets.titlescreen"),
        ("assets.custom", "assets.custom"),
        ("sortname", "sort-by"),
        ("files", "file"),
        ("x-favorite", "x-favorite"),
    ],
)
def test_canonical_pegasus_key(key: str, expected: str):
    assert canonical_pegasus_key(key) == expected
