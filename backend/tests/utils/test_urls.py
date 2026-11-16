from types import SimpleNamespace
from unittest.mock import MagicMock

from utils.urls import generate_rom_download_url


def _request() -> MagicMock:
    request = MagicMock()
    request.url_for.side_effect = lambda _name, **params: (
        f"http://romm.test/api/roms/{params['id']}/content/{params['file_name']}"
    )
    return request


def test_rom_download_url_encodes_reserved_characters():
    rom = SimpleNamespace(id=1, fs_name="Game #1?.zip")

    url = generate_rom_download_url(_request(), rom)

    assert url == "http://romm.test/api/roms/1/content/Game%20%231%3F.zip"


def test_rom_download_url_keeps_folder_separators():
    rom = SimpleNamespace(id=2, fs_name="Game #1/disc 1.cue")

    url = generate_rom_download_url(_request(), rom)

    assert url == "http://romm.test/api/roms/2/content/Game%20%231/disc%201.cue"
