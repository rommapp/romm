import os
from pathlib import Path

from config.config_loader import ConfigLoader


def test_config_loader():
    loader = ConfigLoader(
        os.path.join(Path(__file__).resolve().parent, "fixtures", "config.yml")
    )

    assert loader.config["EXCLUDED_PLATFORMS"] == ["romm"]
    assert loader.config["EXCLUDED_SINGLE_EXT"] == ["xml"]
    assert loader.config["EXCLUDED_SINGLE_FILES"] == ["info.txt"]
    assert loader.config["EXCLUDED_MULTI_FILES"] == ["my_multi_file_game", "DLC"]
    assert loader.config["EXCLUDED_MULTI_PARTS_EXT"] == ["txt"]
    assert loader.config["EXCLUDED_MULTI_PARTS_FILES"] == ["data.xml"]
    assert loader.config["PLATFORMS_BINDING"] == {"gc": "ngc", "psx": "ps"}


def test_empty_config_loader():
    loader = ConfigLoader("")

    assert loader.config.get("EXCLUDED_PLATFORMS") == []
    assert loader.config.get("EXCLUDED_SINGLE_EXT") == []
    assert loader.config.get("EXCLUDED_SINGLE_FILES") == []
    assert loader.config.get("EXCLUDED_MULTI_FILES") == []
    assert loader.config.get("EXCLUDED_MULTI_PARTS_EXT") == []
    assert loader.config.get("EXCLUDED_MULTI_PARTS_FILES") == []
    assert loader.config.get("PLATFORMS_BINDING") == {}
