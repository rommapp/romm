from collections.abc import Callable
from xml.etree.ElementTree import fromstring

import pytest
from fastapi import Request
from main import app
from tests.factories import make_platform, make_rom

from utils.gamelist_exporter import GamelistExporter, parse_existing_gamelist
from utils.pegasus_exporter import PegasusExporter, parse_existing_pegasus

REQUEST = Request(
    {
        "type": "http",
        "scheme": "https",
        "server": ("example.test", 443),
        "headers": [],
        "root_path": "/romm",
        "router": app.router,
    }
)


def pegasus_path(platform_id: int, request: Request) -> str:
    content = PegasusExporter(local_export=False).export_platform_to_pegasus(
        platform_id, request=request
    )
    return next(
        line.removeprefix("file: ")
        for line in content.splitlines()
        if line.startswith("file: ")
    )


def gamelist_path(platform_id: int, request: Request) -> str:
    content = GamelistExporter(local_export=False).export_platform_to_xml(
        platform_id, request=request
    )
    return fromstring(content).findtext("game/path", default="")


@pytest.mark.parametrize(
    "export_path",
    [
        pytest.param(pegasus_path, id="pegasus"),
        pytest.param(gamelist_path, id="gamelist"),
    ],
)
@pytest.mark.parametrize(
    ("fs_stem", "encoded_name"),
    [
        ("Game #1?", "Game%20%231%3F.zip"),
        ("100% + game", "100%25%20%2B%20game.zip"),
        ("Game%20", "Game%2520.zip"),
        ("Café", "Caf%C3%A9.zip"),
        ("game", "game.zip"),
    ],
)
def test_export_content_url_encodes_filename(
    export_path: Callable[[int, Request], str], fs_stem: str, encoded_name: str
) -> None:
    platform = make_platform("nes")
    rom = make_rom(platform, "URL test", fs_stem=fs_stem)

    assert (
        export_path(platform.id, REQUEST)
        == f"https://example.test/romm/api/roms/{rom.id}/content/{encoded_name}"
    )


def test_gamelist_url_reexport_matches_entry_by_rom_id() -> None:
    platform = make_platform("nes")
    rom = make_rom(platform, "URL test", fs_stem="Game #1?")
    existing = parse_existing_gamelist(f"""<gameList>
  <game>
    <path>http://old.host/api/roms/{rom.id}/content/Game #1?.zip</path>
    <favorite>true</favorite>
  </game>
</gameList>""")

    xml, _ = GamelistExporter(local_export=False)._build_gamelist_xml(
        platform.id, request=REQUEST, platform_dir=None, existing=existing
    )

    games = fromstring(xml).findall("game")
    assert len(games) == 1
    assert games[0].findtext("path") == (
        f"https://example.test/romm/api/roms/{rom.id}/content/Game%20%231%3F.zip"
    )
    assert games[0].findtext("favorite") == "true"


def test_pegasus_url_reexport_matches_entry_by_rom_id() -> None:
    platform = make_platform("nes")
    rom = make_rom(platform, "URL test", fs_stem="Game #1?")
    existing = parse_existing_pegasus(f"""game: URL test
file: http://old.host/api/roms/{rom.id}/content/Game #1?.zip
x-favorite: yes
""")

    content, _ = PegasusExporter(local_export=False)._build_pegasus(
        platform.id, request=REQUEST, platform_dir=None, existing=existing
    )

    file_lines = [line for line in content.splitlines() if line.startswith("file:")]
    assert file_lines == [
        f"file: https://example.test/romm/api/roms/{rom.id}/content/Game%20%231%3F.zip"
    ]
    assert "x-favorite: yes" in content.splitlines()
