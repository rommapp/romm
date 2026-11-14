from urllib.parse import unquote, urlsplit
from xml.etree.ElementTree import fromstring

import pytest
from fastapi import Request
from starlette.routing import Route, Router
from tests.factories import make_platform, make_rom

from models.user import User
from utils.gamelist_exporter import GamelistExporter
from utils.pegasus_exporter import PegasusExporter


@pytest.mark.parametrize("export_format", ["pegasus", "gamelist"])
@pytest.mark.parametrize("local_export", [False, True])
@pytest.mark.parametrize(
    ("fs_name", "encoded_name"),
    [
        ("Game #1?.zip", "Game%20%231%3F.zip"),
        ("100% + game.zip", "100%25%20%2B%20game.zip"),
        ("Game%20.zip", "Game%2520.zip"),
        ("Café.zip", "Caf%C3%A9.zip"),
        ("game.zip", "game.zip"),
    ],
)
def test_export_content_filename(
    admin_user: User,
    export_format: str,
    local_export: bool,
    fs_name: str,
    encoded_name: str,
) -> None:
    platform = make_platform("nes")
    rom = make_rom(platform, "URL test", fs_stem=fs_name.removesuffix(".zip"))
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": ("example.test", 443),
            "headers": [],
            "root_path": "/romm",
            "router": Router(
                [
                    Route(
                        "/api/roms/{id}/content/{file_name:path}",
                        lambda _: None,
                        name="get_rom_content",
                    )
                ]
            ),
        }
    )
    if export_format == "pegasus":
        content = PegasusExporter(local_export=local_export).export_platform_to_pegasus(
            platform.id, request=None if local_export else request
        )
        path = next(
            line.removeprefix("file: ")
            for line in content.splitlines()
            if line.startswith("file: ")
        )
    else:
        content = GamelistExporter(local_export=local_export).export_platform_to_xml(
            platform.id, request=None if local_export else request
        )
        xml_path = fromstring(content).findtext("game/path")
        assert xml_path is not None
        path = xml_path
    if local_export:
        prefix = "./" if export_format == "gamelist" else ""
        assert path == prefix + fs_name
    else:
        assert (
            path
            == f"https://example.test/romm/api/roms/{rom.id}/content/{encoded_name}"
        )
        parsed = urlsplit(path)
        assert not parsed.query
        assert not parsed.fragment
        assert unquote(parsed.path.rsplit("/", 1)[1]) == fs_name
