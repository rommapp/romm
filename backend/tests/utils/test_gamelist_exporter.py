from xml.etree.ElementTree import fromstring

import pytest

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils.gamelist_exporter import GamelistExporter


@pytest.fixture
def platform_with_roms(admin_user: User):
    platform = Platform(name="Super Nintendo", slug="snes", fs_slug="snes")
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
        gamelist_id="12345",
        gamelist_metadata={"player_count": "2"},
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

    # Re-fetch to get joined metadata
    rom = db_rom_handler.get_rom(rom.id)

    return platform, [rom]


@pytest.fixture
def platform_with_minimal_rom(admin_user: User):
    platform = Platform(name="Game Boy", slug="gb", fs_slug="gb")
    platform = db_platform_handler.add_platform(platform)

    rom = Rom(
        platform_id=platform.id,
        name=None,
        slug="unknown-rom",
        fs_name="unknown.gb",
        fs_name_no_tags="unknown",
        fs_name_no_ext="unknown",
        fs_extension="gb",
        fs_path="gb/roms",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)

    return platform, [rom]


def test_export_gamelist_xml_basic(platform_with_roms):
    platform, _roms = platform_with_roms
    exporter = GamelistExporter(local_export=True)

    xml_str = exporter.export_platform_to_xml(platform.id, request=None)

    root = fromstring(xml_str)
    assert root.tag == "gameList"

    games = root.findall("game")
    assert len(games) == 1

    game = games[0]
    name = game.find("name")
    path = game.find("path")
    desc = game.find("desc")
    developer = game.find("developer")
    publisher = game.find("publisher")
    genre = game.find("genre")
    lang = game.find("lang")
    region = game.find("region")
    gamelist_id = game.find("id")
    players = game.find("players")

    assert name is not None
    assert path is not None
    assert desc is not None
    assert developer is not None
    assert publisher is not None
    assert genre is not None
    assert lang is not None
    assert region is not None
    assert gamelist_id is not None
    assert players is not None

    assert name.text == "Super Mario World"
    assert path.text == "./Super Mario World (USA).sfc"
    assert desc.text == "A classic platformer game."
    assert developer.text == "Nintendo"
    assert publisher.text == "Nintendo EAD"
    assert genre.text == "Platformer"
    assert lang.text == "en"
    assert region.text == "USA"
    assert gamelist_id.text == "12345"
    assert players.text == "2"


def test_export_gamelist_xml_rating(platform_with_roms):
    platform, _ = platform_with_roms
    exporter = GamelistExporter(local_export=True)

    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)
    game = root.findall("game")[0]

    # Rating should be on 0-1 scale (9.2 / 10 = 0.92)
    rating = game.find("rating")
    assert rating is not None
    assert rating.text == "0.92"


def test_export_gamelist_xml_release_date(platform_with_roms):
    platform, _ = platform_with_roms
    exporter = GamelistExporter(local_export=True)

    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)
    game = root.findall("game")[0]

    release_date = game.find("releasedate")
    assert release_date is not None
    assert release_date.text == "19920623T000000"


def test_export_gamelist_xml_minimal_rom(platform_with_minimal_rom):
    platform, _ = platform_with_minimal_rom
    exporter = GamelistExporter(local_export=True)

    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)

    games = root.findall("game")
    assert len(games) == 1

    game = games[0]
    # Falls back to fs_name when name is None
    name = game.find("name")
    path = game.find("path")
    assert name is not None
    assert path is not None
    assert name.text == "unknown.gb"
    assert path.text == "./unknown.gb"
    # Optional fields should not be present
    assert game.find("desc") is None
    assert game.find("developer") is None
    assert game.find("genre") is None


def test_export_gamelist_xml_skips_missing_roms(admin_user: User):
    platform = Platform(name="NES", slug="nes", fs_slug="nes")
    platform = db_platform_handler.add_platform(platform)

    rom = Rom(
        platform_id=platform.id,
        name="Missing ROM",
        slug="missing-rom",
        fs_name="missing.nes",
        fs_name_no_tags="missing",
        fs_name_no_ext="missing",
        fs_extension="nes",
        fs_path="nes/roms",
        missing_from_fs=True,
    )
    db_rom_handler.add_rom(rom)

    exporter = GamelistExporter(local_export=True)
    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)

    assert len(root.findall("game")) == 0


def test_export_gamelist_xml_invalid_platform():
    exporter = GamelistExporter(local_export=True)

    with pytest.raises(ValueError, match="not found"):
        exporter.export_platform_to_xml(99999, request=None)


def test_export_gamelist_xml_scrap_element(platform_with_roms):
    platform, _ = platform_with_roms
    exporter = GamelistExporter(local_export=True)

    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)
    game = root.findall("game")[0]

    scrap = game.find("scrap")
    assert scrap is not None
    assert scrap.get("name") == "RomM"
