import os
from pathlib import Path

from config.config_manager import ConfigManager


def test_config_loader():
    loader = ConfigManager(
        os.path.join(Path(__file__).resolve().parent, "fixtures", "config/config.yml")
    )

    assert loader.config.EXCLUDED_PLATFORMS == ["romm"]
    assert loader.config.EXCLUDED_SINGLE_EXT == ["xml"]
    assert loader.config.EXCLUDED_SINGLE_FILES == ["info.txt"]
    assert loader.config.EXCLUDED_MULTI_FILES == ["my_multi_file_game", "DLC"]
    assert loader.config.EXCLUDED_MULTI_PARTS_EXT == ["txt"]
    assert loader.config.EXCLUDED_MULTI_PARTS_FILES == ["data.xml"]
    assert loader.config.PLATFORMS_BINDING == {"gc": "ngc"}
    assert loader.config.PLATFORMS_VERSIONS == {"naomi": "arcade"}
    assert loader.config.ROMS_FOLDER_NAME == "ROMS"
    assert loader.config.FIRMWARE_FOLDER_NAME == "BIOS"


def test_empty_config_loader():
    loader = ConfigManager("config/tests/fixtures/config/empty_config.yml")

    assert loader.config.EXCLUDED_PLATFORMS == []
    assert loader.config.EXCLUDED_SINGLE_EXT == []
    assert loader.config.EXCLUDED_SINGLE_FILES == []
    assert loader.config.EXCLUDED_MULTI_FILES == []
    assert loader.config.EXCLUDED_MULTI_PARTS_EXT == []
    assert loader.config.EXCLUDED_MULTI_PARTS_FILES == []
    assert loader.config.PLATFORMS_BINDING == {}
    assert loader.config.PLATFORMS_VERSIONS == {}
    assert loader.config.ROMS_FOLDER_NAME == "roms"
    assert loader.config.FIRMWARE_FOLDER_NAME == "bios"
