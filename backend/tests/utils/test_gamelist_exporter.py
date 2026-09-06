from dataclasses import dataclass
from os.path import isabs
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest

from config import FRONTEND_RESOURCES_PATH
from config.config_manager import PLATFORM_MEDIA_DIRS
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import (
    fs_platform_handler,
    fs_resource_handler,
    fs_rom_handler,
)
from handler.metadata.gamelist_handler import GamelistHandler
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


def test_export_gamelist_prefers_explicit_publisher_developer(platform_with_roms):
    platform, roms = platform_with_roms
    # The companies order would map developer=Nintendo / publisher=Nintendo EAD;
    # the explicit split fields (deliberately reversed) must take precedence.
    db_rom_handler.update_rom(
        roms[0].id,
        {
            "igdb_metadata": {
                "companies": ["Nintendo", "Nintendo EAD"],
                "publishers": ["Nintendo"],
                "developers": ["Nintendo EAD"],
            }
        },
    )

    xml_str = GamelistExporter(local_export=True).export_platform_to_xml(
        platform.id, request=None
    )
    game = fromstring(xml_str).findall("game")[0]
    developer = game.find("developer")
    publisher = game.find("publisher")
    assert developer is not None and developer.text == "Nintendo EAD"
    assert publisher is not None and publisher.text == "Nintendo"


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


def test_export_gamelist_xml_skips_physical_roms(admin_user: User):
    platform = Platform(name="NES", slug="nes", fs_slug="nes")
    platform = db_platform_handler.add_platform(platform)

    rom = Rom(
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
        "cartridge",
        "title_screen",
        "titleshot",
        "bezel",
        "mix",
    ]
    for tag in media_tags:
        elem = game.find(tag)
        assert elem is not None and elem.text is not None

        assert not isabs(elem.text)


def test_export_gamelist_xml_miximage_variants_use_distinct_tags(platform_with_roms):
    """Both miximage variants must reach the XML under their own tag."""
    platform, roms = platform_with_roms

    db_rom_handler.update_rom(
        roms[0].id,
        {
            "ss_metadata": {
                "miximage_path": "snes-ss/miximage/test.png",
                "miximage_v2_path": "snes-ss/miximage_v2/test.png",
            }
        },
    )

    exporter = GamelistExporter(local_export=True)
    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    game = fromstring(xml_str).findall("game")[0]

    miximages = game.findall("miximage")
    miximages_v2 = game.findall("miximage_v2")
    assert len(miximages) == 1
    assert len(miximages_v2) == 1
    assert miximages[0].text != miximages_v2[0].text


def test_export_gamelist_xml_gamelist_backcover_fallback(platform_with_roms):
    """A back cover discovered by the gamelist handler must reach <boxback>."""
    platform, roms = platform_with_roms

    db_rom_handler.update_rom(
        roms[0].id,
        {"gamelist_metadata": {"box2d_back_path": "snes-gl/box2d_back/test.png"}},
    )

    exporter = GamelistExporter(local_export=True)
    xml_str = exporter.export_platform_to_xml(platform.id, request=None)
    game = fromstring(xml_str).findall("game")[0]

    boxback = game.find("boxback")
    assert boxback is not None
    assert boxback.text == "./backcovers/Super Mario World (USA).png"


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


@dataclass
class IsolatedFilesystem:
    resources_base: Path
    library_base: Path

    def write_resource(self, rel: str, content: bytes = b"X") -> Path:
        src = self.resources_base / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(content)
        return src

    def platform_dir(self, platform: Platform) -> Path:
        return self.library_base / fs_platform_handler.get_platform_fs_structure(
            platform.fs_slug
        )


@pytest.fixture
def isolated_filesystem(tmp_path, monkeypatch):
    """Redirect resource and library base paths to a temp directory so that
    export_platform_to_file() can copy real assets and write gamelist.xml
    without touching the host filesystem."""
    resources_base = tmp_path / "resources"
    library_base = tmp_path / "library"
    monkeypatch.setattr(fs_resource_handler, "base_path", resources_base)
    monkeypatch.setattr(fs_platform_handler, "base_path", library_base)
    return IsolatedFilesystem(resources_base, library_base)


async def test_export_platform_to_file_copies_assets(
    platform_with_roms, isolated_filesystem
):
    """export_platform_to_file copies each media file into <platform>/<media dir>/
    and writes gamelist.xml referencing those relative paths."""
    platform, _ = platform_with_roms

    sources = {
        "snes/covers/super-mario-world.jpg": b"cover-bytes",
        "snes/screenshots/super-mario-world-1.jpg": b"shot-bytes",
        "snes/manuals/super-mario-world.pdf": b"manual-bytes",
        "snes/videos/super-mario-world.mp4": b"video-bytes",
    }
    for rel, content in sources.items():
        isolated_filesystem.write_resource(rel, content)

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    platform_dir = isolated_filesystem.platform_dir(platform)

    expected_assets = {
        "covers/Super Mario World (USA).jpg": b"cover-bytes",
        "screenshots/Super Mario World (USA).jpg": b"shot-bytes",
        "manuals/Super Mario World (USA).pdf": b"manual-bytes",
        "videos/Super Mario World (USA).mp4": b"video-bytes",
    }
    for rel, content in expected_assets.items():
        dest = platform_dir / rel
        assert dest.is_file(), f"missing asset {dest}"
        assert dest.read_bytes() == content

    gamelist = platform_dir / "gamelist.xml"
    assert gamelist.is_file()
    game = fromstring(gamelist.read_text()).findall("game")[0]

    expected_refs = {
        "thumbnail": "./covers/Super Mario World (USA).jpg",
        "screenshot": "./screenshots/Super Mario World (USA).jpg",
        "video": "./videos/Super Mario World (USA).mp4",
        "manual": "./manuals/Super Mario World (USA).pdf",
    }
    for tag, expected in expected_refs.items():
        elem = game.find(tag)
        assert elem is not None and elem.text == expected

    written_dirs = [p.name for p in platform_dir.iterdir() if p.is_dir()]
    assert written_dirs
    assert fs_rom_handler.exclude_multi_roms(written_dirs) == []


async def test_export_platform_to_file_keeps_miximage_variants_separate(
    platform_with_roms, isolated_filesystem
):
    """The two miximage variants share a file extension, so they must land in
    separate asset directories instead of overwriting each other."""
    platform, roms = platform_with_roms

    db_rom_handler.update_rom(
        roms[0].id,
        {
            "ss_metadata": {
                "miximage_path": "snes-ss/miximage/test.png",
                "miximage_v2_path": "snes-ss/miximage_v2/test.png",
            }
        },
    )

    sources = {
        "snes-ss/miximage/test.png": b"mix-v1-bytes",
        "snes-ss/miximage_v2/test.png": b"mix-v2-bytes",
    }
    for rel, content in sources.items():
        isolated_filesystem.write_resource(rel, content)

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    platform_dir = isolated_filesystem.platform_dir(platform)

    v1 = platform_dir / "miximages/Super Mario World (USA).png"
    v2 = platform_dir / "miximages_v2/Super Mario World (USA).png"
    assert v1.read_bytes() == b"mix-v1-bytes"
    assert v2.read_bytes() == b"mix-v2-bytes"

    game = fromstring((platform_dir / "gamelist.xml").read_text()).findall("game")[0]
    miximage = game.find("miximage")
    miximage_v2 = game.find("miximage_v2")
    assert miximage is not None
    assert miximage_v2 is not None
    assert miximage.text == "./miximages/Super Mario World (USA).png"
    assert miximage_v2.text == "./miximages_v2/Super Mario World (USA).png"


async def test_export_platform_to_file_omits_tags_when_copy_fails(
    platform_with_roms, isolated_filesystem
):
    """When a source resource is missing, _copy_asset returns False; the
    corresponding tag must be omitted from gamelist.xml and no asset file
    must be written for it. Other assets still export normally."""
    platform, _ = platform_with_roms

    # Provide cover and screenshot, deliberately omit manual + video sources.
    for rel in (
        "snes/covers/super-mario-world.jpg",
        "snes/screenshots/super-mario-world-1.jpg",
    ):
        isolated_filesystem.write_resource(rel)

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    platform_dir = isolated_filesystem.platform_dir(platform)

    # Successful copies present
    assert (platform_dir / "covers/Super Mario World (USA).jpg").is_file()
    assert (platform_dir / "screenshots/Super Mario World (USA).jpg").is_file()
    # A missing source produces neither a destination file nor an empty subdir
    assert not (platform_dir / "manuals").exists()
    assert not (platform_dir / "videos").exists()

    game = fromstring((platform_dir / "gamelist.xml").read_text()).findall("game")[0]
    assert game.find("manual") is None
    assert game.find("video") is None
    thumbnail = game.find("thumbnail")
    assert thumbnail is not None
    assert thumbnail.text == "./covers/Super Mario World (USA).jpg"
    screenshot = game.find("screenshot")
    assert screenshot is not None
    assert screenshot.text == "./screenshots/Super Mario World (USA).jpg"


async def test_export_platform_to_file_uses_esde_media_dirs(
    platform_with_roms, isolated_filesystem
):
    """3D boxes and physical media land in ES-DE's folder names beside the ROMs."""
    platform, roms = platform_with_roms

    db_rom_handler.update_rom(
        roms[0].id,
        {
            "ss_metadata": {
                "box3d_path": "snes-ss/box3d/test.png",
                "physical_path": "snes-ss/physical/test.png",
            }
        },
    )
    for rel in ("snes-ss/box3d/test.png", "snes-ss/physical/test.png"):
        isolated_filesystem.write_resource(rel)

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    platform_dir = isolated_filesystem.platform_dir(platform)
    assert (platform_dir / "3dboxes/Super Mario World (USA).png").is_file()
    assert (platform_dir / "physicalmedia/Super Mario World (USA).png").is_file()

    game = fromstring((platform_dir / "gamelist.xml").read_text()).findall("game")[0]
    box3d = game.find("box3d")
    physical = game.find("physicalmedia")
    assert box3d is not None and box3d.text == "./3dboxes/Super Mario World (USA).png"
    assert (
        physical is not None
        and physical.text == "./physicalmedia/Super Mario World (USA).png"
    )


async def test_export_platform_to_file_reuses_existing_esde_media(
    platform_with_roms, isolated_filesystem
):
    """Media already scraped by ES-DE into <platform>/covers/ is left untouched."""
    platform, _ = platform_with_roms

    isolated_filesystem.write_resource(
        "snes/covers/super-mario-world.jpg", b"romm-cover"
    )

    existing = (
        isolated_filesystem.platform_dir(platform)
        / "covers/Super Mario World (USA).jpg"
    )
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"esde-cover")

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    assert existing.read_bytes() == b"esde-cover"
    assert list(existing.parent.iterdir()) == [existing]


def test_export_gamelist_xml_mix_falls_back_to_miximage_v2(platform_with_roms):
    """RetroBat has a single <mix> tag, so it takes the v2 miximage when v1 is absent."""
    platform, roms = platform_with_roms

    db_rom_handler.update_rom(
        roms[0].id,
        {"ss_metadata": {"miximage_v2_path": "snes-ss/miximage_v2/test.png"}},
    )

    exporter = GamelistExporter(local_export=True)
    game = fromstring(
        exporter.export_platform_to_xml(platform.id, request=None)
    ).findall("game")[0]

    mix = game.find("mix")
    assert mix is not None
    assert mix.text == "./miximages_v2/Super Mario World (USA).png"


def test_gamelist_media_dirs_are_excluded_from_scan():
    """Media folders beside the ROMs are never scanned as multi-file ROMs."""
    assert fs_rom_handler.exclude_multi_roms(list(PLATFORM_MEDIA_DIRS.values())) == []


def _write_gamelist(
    isolated_filesystem: IsolatedFilesystem, platform: Platform, content: str
) -> Path:
    gamelist = isolated_filesystem.platform_dir(platform) / "gamelist.xml"
    gamelist.parent.mkdir(parents=True, exist_ok=True)
    gamelist.write_text(content, encoding="utf-8")
    return gamelist


async def test_export_platform_to_file_keeps_unmanaged_tags(
    platform_with_roms, isolated_filesystem
):
    """Favorites, play stats and emulator overrides survive a re-export, while
    the tags RomM owns are replaced rather than duplicated."""
    platform, _ = platform_with_roms
    gamelist = _write_gamelist(
        isolated_filesystem,
        platform,
        """<?xml version="1.0"?>
<gameList>
  <game id="77" source="ScreenScraper.fr">
    <path>./Super Mario World (USA).sfc</path>
    <name>Old Name</name>
    <desc>Old description</desc>
    <favorite>true</favorite>
    <playcount>3</playcount>
    <lastplayed>20250101T120000</lastplayed>
    <gametime>3600</gametime>
    <emulator>libretro</emulator>
    <core>snes9x</core>
    <md5>abc</md5>
    <scrap name="Skraper" date="20240101T000000"/>
  </game>
</gameList>
""",
    )

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    games = fromstring(gamelist.read_text()).findall("game")
    assert len(games) == 1
    game = games[0]

    assert game.get("id") == "77"
    assert game.get("source") == "ScreenScraper.fr"
    assert [e.text for e in game.findall("name")] == ["Super Mario World"]
    assert [e.text for e in game.findall("desc")] == ["A classic platformer game."]
    assert [s.get("name") for s in game.findall("scrap")] == ["RomM"]

    preserved = {
        "favorite": "true",
        "playcount": "3",
        "lastplayed": "20250101T120000",
        "gametime": "3600",
        "emulator": "libretro",
        "core": "snes9x",
        "md5": "abc",
    }
    for tag, expected in preserved.items():
        elem = game.find(tag)
        assert elem is not None and elem.text == expected, tag


async def test_export_platform_to_file_keeps_unmatched_entries(
    platform_with_roms, isolated_filesystem
):
    """Entries RomM knows nothing about, folders and scraper blocks stay put."""
    platform, _ = platform_with_roms
    gamelist = _write_gamelist(
        isolated_filesystem,
        platform,
        """<?xml version="1.0"?>
<gameList>
  <provider>
    <software>Skraper</software>
  </provider>
  <game>
    <path>Hack (Unl).sfc</path>
    <name>A Hack</name>
    <favorite>true</favorite>
  </game>
  <folder>
    <path>./Hacks</path>
    <name>Hacks</name>
  </folder>
</gameList>
""",
    )

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    root = fromstring(gamelist.read_text())
    assert [child.tag for child in root] == ["provider", "folder", "game", "game"]

    provider = root.find("provider/software")
    assert provider is not None and provider.text == "Skraper"
    folder = root.find("folder/name")
    assert folder is not None and folder.text == "Hacks"

    by_path = {g.findtext("path"): g for g in root.findall("game")}
    assert set(by_path) == {"./Super Mario World (USA).sfc", "Hack (Unl).sfc"}
    assert by_path["Hack (Unl).sfc"].findtext("favorite") == "true"
    assert by_path["Hack (Unl).sfc"].find("scrap") is None


async def test_export_platform_to_file_keeps_esde_alternative_emulator(
    platform_with_roms, isolated_filesystem
):
    """ES-DE's <alternativeEmulator> sibling and per-game <altemulator> are
    written back, and the result still parses through the gamelist handler."""
    platform, _ = platform_with_roms
    gamelist = _write_gamelist(
        isolated_filesystem,
        platform,
        """<?xml version="1.0"?>
<alternativeEmulator>
	<label>RetroArch</label>
</alternativeEmulator>
<gameList>
	<game>
		<path>./Super Mario World (USA).sfc</path>
		<name>Old Name</name>
		<altemulator>bsnes</altemulator>
	</game>
</gameList>
""",
    )

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    content = gamelist.read_text()
    assert content.startswith("<?xml")
    assert content.index("<alternativeEmulator>") < content.index("<gameList>")
    assert "<label>RetroArch</label>" in content

    games = list(GamelistHandler()._iter_game_elements(gamelist))
    assert [g.findtext("path") for g in games] == ["./Super Mario World (USA).sfc"]
    assert games[0].findtext("altemulator") == "bsnes"
    assert games[0].findtext("name") == "Super Mario World"


async def test_export_platform_to_file_refuses_to_overwrite_unparseable_gamelist(
    platform_with_roms, isolated_filesystem
):
    """A gamelist.xml that cannot be read is never replaced."""
    platform, _ = platform_with_roms
    broken = "<gameList><game><path>./x.sfc</path><favorite>true</favorite>"
    gamelist = _write_gamelist(isolated_filesystem, platform, broken)

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is False
    assert gamelist.read_text() == broken


async def test_export_platform_to_file_reads_bom_prefixed_gamelist(
    platform_with_roms, isolated_filesystem
):
    """A UTF-8 BOM, as Windows editors write it, does not block the merge."""
    platform, _ = platform_with_roms
    gamelist = isolated_filesystem.platform_dir(platform) / "gamelist.xml"
    gamelist.parent.mkdir(parents=True, exist_ok=True)
    gamelist.write_text(
        """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./Super Mario World (USA).sfc</path>
    <favorite>true</favorite>
  </game>
</gameList>
""",
        encoding="utf-8-sig",
    )

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    games = fromstring(gamelist.read_text(encoding="utf-8")).findall("game")
    assert [g.findtext("favorite") for g in games] == ["true"]


async def test_export_platform_to_file_keeps_colliding_filenames(
    platform_with_roms, isolated_filesystem
):
    """Two entries whose paths share a filename are both kept: the first is
    merged with RomM's data, the second is carried over untouched."""
    platform, _ = platform_with_roms
    gamelist = _write_gamelist(
        isolated_filesystem,
        platform,
        """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./Super Mario World (USA).sfc</path>
    <favorite>true</favorite>
  </game>
  <game>
    <path>./Hacks/Super Mario World (USA).sfc</path>
    <name>Kaizo</name>
    <playcount>9</playcount>
  </game>
</gameList>
""",
    )

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    by_path = {
        g.findtext("path"): g for g in fromstring(gamelist.read_text()).findall("game")
    }
    assert set(by_path) == {
        "./Super Mario World (USA).sfc",
        "./Hacks/Super Mario World (USA).sfc",
    }
    assert by_path["./Super Mario World (USA).sfc"].findtext("favorite") == "true"
    assert by_path["./Super Mario World (USA).sfc"].find("scrap") is not None
    hack = by_path["./Hacks/Super Mario World (USA).sfc"]
    assert hack.findtext("name") == "Kaizo"
    assert hack.findtext("playcount") == "9"
    assert hack.find("scrap") is None


async def test_export_platform_to_file_keeps_comments_and_instructions(
    platform_with_roms, isolated_filesystem
):
    """XML comments and processing instructions are written back wherever
    they sat: beside <gameList>, inside it, and inside a <game>."""
    platform, _ = platform_with_roms
    gamelist = _write_gamelist(
        isolated_filesystem,
        platform,
        """<?xml version="1.0"?>
<?xml-stylesheet type="text/xsl" href="gamelist.xsl"?>
<!-- edited by hand -->
<gameList>
  <!-- section: platformers -->
  <game>
    <path>./Super Mario World (USA).sfc</path>
    <!-- do not rescrape -->
    <favorite>true</favorite>
  </game>
</gameList>
""",
    )

    exporter = GamelistExporter(local_export=True)
    assert await exporter.export_platform_to_file(platform.id, request=None) is True

    content = gamelist.read_text()
    for kept in (
        '<?xml-stylesheet type="text/xsl" href="gamelist.xsl"?>',
        "<!-- edited by hand -->",
        "<!-- section: platformers -->",
        "<!-- do not rescrape -->",
    ):
        assert content.count(kept) == 1, kept
    assert content.index("<!-- edited by hand -->") < content.index("<gameList>")

    parsed = [
        (g.findtext("path"), g.findtext("favorite"))
        for g in GamelistHandler()._iter_game_elements(gamelist)
    ]
    assert parsed == [("./Super Mario World (USA).sfc", "true")]
