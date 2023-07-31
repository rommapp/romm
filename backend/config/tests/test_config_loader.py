from config.config_loader import ConfigLoader


def test_config_loader():
    cl = ConfigLoader("backend/config/tests/fixtures/config.yml")

    assert cl.config["EXCLUDED_PLATFORMS"] == ["romm"]
    assert cl.config["EXCLUDED_EXTENSIONS"] == ["xml"]
    assert cl.config["EXCLUDED_FILES"] == ["info.txt"]
    assert cl.config["EXCLUDED_MULTI_FILES"] == ["my_multi_file_game", "DLC"]
    assert cl.config["EXCLUDED_MULTI_PARTS_EXT"] == ["txt"]
    assert cl.config["EXCLUDED_MULTI_PARTS_FILES"] == ["data.xml"]
    assert cl.config["PLATFORMS_BINDING"] == {"gc": "ngc", "psx": "ps"}


def test_empty_config_loader():
    cl = ConfigLoader("")

    assert cl.config.get("EXCLUDED_PLATFORMS") == []
    assert cl.config.get("EXCLUDED_EXTENSIONS") == []
    assert cl.config.get("EXCLUDED_FILES") == []
    assert cl.config.get("EXCLUDED_MULTI_FILES") == []
    assert cl.config.get("EXCLUDED_MULTI_PARTS_EXT") == []
    assert cl.config.get("EXCLUDED_MULTI_PARTS_FILES") == []
    assert cl.config.get("PLATFORMS_BINDING") == {}
