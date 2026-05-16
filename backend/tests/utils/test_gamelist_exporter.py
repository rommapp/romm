from os.path import isabs
from xml.etree.ElementTree import fromstring

import pytest

from config import FRONTEND_RESOURCES_PATH
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_platform_handler, fs_resource_handler
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
            },
            "path_cover_l": "snes/covers/super-mario-world.jpg",
            "path_manual": "snes/manuals/super-mario-world.pdf",
            "path_screenshots": ["snes/screenshots/super-mario-world-1.jpg"],
            "gamelist_metadata": {
                "player_count": "2",
                "video_path": "snes/videos/super-mario-world.mp4",  # feeds rom.path_video property
            },
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


@pytest.mark.parametrize("tag", ["thumbnail", "image", "video", "screenshot", "manual"])
def test_export_gamelist_xml_local_media_relative_path(platform_with_roms, tag):
    platform, _ = platform_with_roms
    exporter = GamelistExporter(local_export=True)
    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)
    game = root.findall("game")[0]

    elem = game.find(tag)
    assert elem is not None
    assert elem.text is not None
    assert not isabs(elem.text)


def test_export_gamelist_xml_local_ss_metadata_media_relative(platform_with_roms):
    platform, roms = platform_with_roms

    db_rom_handler.update_rom(
        roms[0].id,
        {
            "ss_metadata": {
                "box3d_path": "snes-ss/box3d/test.png",
                "box2d_back_path": "snes-ss/boxback/test.png",
                "fanart_path": "snes-ss/fanart/test.png",
                "logo_path": "snes-ss/logo/test.png",
                "miximage_path": "snes-ss/miximage/test.png",
                "physical_path": "snes-ss/physical/test.png",
                "title_screen_path": "snes-ss/titlescreen/test.png",
                "bezel_path": "snes-ss/bezel/test.png",
            }
        },
    )

    exporter = GamelistExporter(local_export=True)
    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)
    game = root.findall("game")[0]

    media_tags = [
        "box3d",
        "boxback",
        "fanart",
        "marquee",
        "miximage",
        "physicalmedia",
        "title_screen",
        "bezel",
    ]
    for tag in media_tags:
        elem = game.find(tag)
        assert elem is not None and elem.text is not None

        assert not isabs(elem.text)


def test_export_gamelist_xml_local_no_absolute_paths_anywhere(platform_with_roms):
    """Catch-all: when local_export=True, no element text should contain
    the FRONTEND_RESOURCES_PATH absolute prefix."""
    platform, _ = platform_with_roms

    exporter = GamelistExporter(local_export=True)
    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    root = fromstring(xml_str)

    for elem in root.iter():
        if elem.text and FRONTEND_RESOURCES_PATH in elem.text:
            pytest.fail(
                f"<{elem.tag}> contains absolute FRONTEND_RESOURCES_PATH: {elem.text}"
            )


def test_export_gamelist_xml_rejects_path_traversal(platform_with_roms):
    """Paths with traversal segments must not escape the resources directory."""
    platform, roms = platform_with_roms

    db_rom_handler.update_rom(roms[0].id, {"path_cover_l": "../../etc/passwd"})

    exporter = GamelistExporter(local_export=True)
    with pytest.raises(ValueError, match="invalid parent directory references"):
        exporter.export_platform_to_xml(platform.id, request=None)


@pytest.fixture
def isolated_filesystem(tmp_path, monkeypatch):
    """Redirect resource and library base paths to a temp directory so that
    export_platform_to_file() can copy real assets and write gamelist.xml
    without touching the host filesystem."""
    resources_base = tmp_path / "resources"
    library_base = tmp_path / "library"
    monkeypatch.setattr(fs_resource_handler, "base_path", resources_base)
    monkeypatch.setattr(fs_platform_handler, "base_path", library_base)
    return resources_base, library_base


async def test_export_platform_to_file_copies_assets(
    platform_with_roms, isolated_filesystem
):
    """export_platform_to_file copies each media file into <platform>/assets/<subdir>/
    and writes gamelist.xml referencing those relative paths."""
    resources_base, library_base = isolated_filesystem
    platform, _ = platform_with_roms

    sources = {
        "snes/covers/super-mario-world.jpg": b"cover-bytes",
        "snes/screenshots/super-mario-world-1.jpg": b"shot-bytes",
        "snes/manuals/super-mario-world.pdf": b"manual-bytes",
        "snes/videos/super-mario-world.mp4": b"video-bytes",
    }
    for rel, content in sources.items():
        src = resources_base / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(content)

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    platform_dir = library_base / fs_platform_handler.get_platform_fs_structure(
        platform.fs_slug
    )

    expected_assets = {
        "assets/covers/Super Mario World (USA).jpg": b"cover-bytes",
        "assets/screenshots/Super Mario World (USA).jpg": b"shot-bytes",
        "assets/manuals/Super Mario World (USA).pdf": b"manual-bytes",
        "assets/videos/Super Mario World (USA).mp4": b"video-bytes",
    }
    for rel, content in expected_assets.items():
        dest = platform_dir / rel
        assert dest.is_file(), f"missing asset {dest}"
        assert dest.read_bytes() == content

    gamelist = platform_dir / "gamelist.xml"
    assert gamelist.is_file()
    game = fromstring(gamelist.read_text()).findall("game")[0]

    expected_refs = {
        "thumbnail": "./assets/covers/Super Mario World (USA).jpg",
        "screenshot": "./assets/screenshots/Super Mario World (USA).jpg",
        "video": "./assets/videos/Super Mario World (USA).mp4",
        "manual": "./assets/manuals/Super Mario World (USA).pdf",
    }
    for tag, expected in expected_refs.items():
        elem = game.find(tag)
        assert elem is not None and elem.text == expected


async def test_export_platform_to_file_omits_tags_when_copy_fails(
    platform_with_roms, isolated_filesystem
):
    """When a source resource is missing, _copy_asset returns False; the
    corresponding tag must be omitted from gamelist.xml and no asset file
    must be written for it. Other assets still export normally."""
    resources_base, library_base = isolated_filesystem
    platform, _ = platform_with_roms

    # Provide cover and screenshot, deliberately omit manual + video sources.
    for rel in (
        "snes/covers/super-mario-world.jpg",
        "snes/screenshots/super-mario-world-1.jpg",
    ):
        src = resources_base / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"X")

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    platform_dir = library_base / fs_platform_handler.get_platform_fs_structure(
        platform.fs_slug
    )

    # Successful copies present
    assert (platform_dir / "assets/covers/Super Mario World (USA).jpg").is_file()
    assert (platform_dir / "assets/screenshots/Super Mario World (USA).jpg").is_file()
    # Failed copies don't produce destination files (an empty subdir may be
    # left behind because _copy_asset mkdirs before opening the source).
    assert not (platform_dir / "assets/manuals/Super Mario World (USA).pdf").exists()
    assert not (platform_dir / "assets/videos/Super Mario World (USA).mp4").exists()

    game = fromstring((platform_dir / "gamelist.xml").read_text()).findall("game")[0]
    assert game.find("manual") is None
    assert game.find("video") is None
    thumbnail = game.find("thumbnail")
    assert thumbnail is not None
    assert thumbnail.text == "./assets/covers/Super Mario World (USA).jpg"
    screenshot = game.find("screenshot")
    assert screenshot is not None
    assert screenshot.text == "./assets/screenshots/Super Mario World (USA).jpg"
