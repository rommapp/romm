import pytest
from fastapi import Request
from main import app

from models.rom import Rom, RomFile
from utils.urls import rom_content_url, rom_id_from_content_url, romfile_content_url

REQUEST = Request(
    {
        "type": "http",
        "scheme": "https",
        "server": ("example.test", 443),
        "headers": [],
        "root_path": "",
        "router": app.router,
    }
)


def test_rom_content_url_encodes_fs_name() -> None:
    rom = Rom(id=7, fs_name="Game #1?.zip")

    assert (
        rom_content_url(REQUEST, rom)
        == "https://example.test/api/roms/7/content/Game%20%231%3F.zip"
    )


def test_romfile_content_url_encodes_file_name() -> None:
    file = RomFile(id=9, file_name="Disc 1/100%.bin")

    assert (
        romfile_content_url(REQUEST, file)
        == "https://example.test/api/roms/9/files/content/Disc%201%2F100%25.bin"
    )


@pytest.mark.parametrize(
    ("value", "rom_id"),
    [
        ("https://example.test/romm/api/roms/12/content/Game%20%231.zip", 12),
        ("http://old.host/api/roms/3/content/Game #1?.zip", 3),
        ("https://example.test/api/roms/3/files/content/Game.zip", None),
        ("./Game.zip", None),
    ],
)
def test_rom_id_from_content_url(value: str, rom_id: int | None) -> None:
    assert rom_id_from_content_url(value) == rom_id
