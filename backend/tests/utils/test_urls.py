from fastapi import Request
from main import app

from models.rom import Rom, RomFile
from utils.urls import rom_content_url, romfile_content_url

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
