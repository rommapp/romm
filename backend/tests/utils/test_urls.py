import pytest
from fastapi import Request
from main import app
from pytest_mock import MockerFixture

from models.rom import Rom, RomFile
from utils.urls import (
    get_public_base_url,
    is_shareable_host,
    rom_content_url,
    rom_id_from_content_url,
    romfile_content_url,
    youtube_id_from_url,
)

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


@pytest.mark.parametrize(
    "host, shareable",
    [
        ("localhost", False),
        ("localhost.", False),
        ("LOCALHOST.", False),
        ("127.0.0.1", False),
        ("romm.example.com", True),
        ("romm.example.com.", True),
    ],
)
def test_is_shareable_host(host: str, shareable: bool) -> None:
    assert is_shareable_host(host) is shareable


@pytest.mark.parametrize(
    "base_url, expected",
    [
        ("https://romm.example.com/", "https://romm.example.com"),
        ("http://localhost:8080", None),
        ("http://[invalid", None),
    ],
)
def test_get_public_base_url(
    mocker: MockerFixture, base_url: str, expected: str | None
) -> None:
    mocker.patch("utils.urls.config.ROMM_BASE_URL", base_url)
    assert get_public_base_url() == expected


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ#t=30", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=30", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ#t=30", "dQw4w9WgXcQ"),
        ("https://www.youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        (" https://youtu.be/dQw4w9WgXcQ ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=abc123", None),
        ("https://www.youtube.com/user/futurecrew", None),
        ("https://youtu.be/", None),
        ("https://[youtube.com/watch?v=dQw4w9WgXcQ", None),
        ("https://vimeo.com/123456", None),
        ("", None),
        (None, None),
    ],
)
def test_youtube_id_from_url(url: str | None, video_id: str | None) -> None:
    assert youtube_id_from_url(url) == video_id
