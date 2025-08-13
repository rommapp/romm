import os
import tempfile
from unittest.mock import patch

import pytest
import yaml
from config.config_manager import Config, ConfigManager
from exceptions.config_exceptions import ConfigNotWritableException
from sqlalchemy import URL


class TestConfig:
    """Test the Config class"""

    def test_config_initialization(self):
        """Test Config class initialization with various parameters"""
        config = Config(
            EXCLUDED_PLATFORMS=["test1", "test2"],
            EXCLUDED_SINGLE_EXT=["zip", "rar"],
            EXCLUDED_SINGLE_FILES=["readme.txt"],
            EXCLUDED_MULTI_FILES=["game.part1"],
            EXCLUDED_MULTI_PARTS_EXT=["txt"],
            EXCLUDED_MULTI_PARTS_FILES=["data.xml"],
            PLATFORMS_BINDING={"gc": "ngc"},
            PLATFORMS_VERSIONS={"naomi": "arcade"},
            ROMS_FOLDER_NAME="ROMS",
            FIRMWARE_FOLDER_NAME="BIOS",
        )

        assert config.EXCLUDED_PLATFORMS == ["test1", "test2"]
        assert config.EXCLUDED_SINGLE_EXT == ["zip", "rar"]
        assert config.EXCLUDED_SINGLE_FILES == ["readme.txt"]
        assert config.EXCLUDED_MULTI_FILES == ["game.part1"]
        assert config.EXCLUDED_MULTI_PARTS_EXT == ["txt"]
        assert config.EXCLUDED_MULTI_PARTS_FILES == ["data.xml"]
        assert config.PLATFORMS_BINDING == {"gc": "ngc"}
        assert config.PLATFORMS_VERSIONS == {"naomi": "arcade"}
        assert config.ROMS_FOLDER_NAME == "ROMS"
        assert config.FIRMWARE_FOLDER_NAME == "BIOS"

    def test_config_high_prio_structure_path(self):
        """Test that HIGH_PRIO_STRUCTURE_PATH is correctly constructed"""
        with patch("config.config_manager.LIBRARY_BASE_PATH", "/test/library"):
            config = Config(ROMS_FOLDER_NAME="roms")
            assert config.HIGH_PRIO_STRUCTURE_PATH == "/test/library/roms"


class TestConfigManager:
    """Test the ConfigManager class"""

    def test_singleton_pattern(self):
        """Test that ConfigManager follows singleton pattern"""
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        assert manager1 is manager2

    def test_init_with_custom_config_file(self):
        """Test ConfigManager initialization with custom config file path"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump({}, f)
            config_file = f.name

        try:
            manager = ConfigManager(config_file)
            assert manager.config_file == config_file
        finally:
            os.unlink(config_file)

    @patch("config.config_manager.sys.exit")
    def test_init_with_invalid_config_file(self, mock_exit):
        """Test ConfigManager initialization with invalid config file"""
        with patch("config.config_manager.log.critical") as mock_log:
            ConfigManager("/nonexistent/file.yml")
            mock_log.assert_called()
            mock_exit.assert_called_with(5)

    def test_get_db_engine_mariadb(self):
        """Test database engine creation for MariaDB"""
        with patch("config.config_manager.ROMM_DB_DRIVER", "mariadb"), patch(
            "config.config_manager.DB_USER", "testuser"
        ), patch("config.config_manager.DB_PASSWD", "testpass"), patch(
            "config.config_manager.DB_HOST", "localhost"
        ), patch(
            "config.config_manager.DB_PORT", 3306
        ), patch(
            "config.config_manager.DB_NAME", "testdb"
        ), patch(
            "config.config_manager.DB_QUERY_JSON", None
        ):

            engine = ConfigManager.get_db_engine()
            assert isinstance(engine, URL)
            assert engine.drivername == "mariadb+mariadbconnector"
            assert engine.username == "testuser"
            assert engine.password == "testpass"
            assert engine.host == "localhost"
            assert engine.port == 3306
            assert engine.database == "testdb"

    def test_get_db_engine_mysql(self):
        """Test database engine creation for MySQL"""
        with patch("config.config_manager.ROMM_DB_DRIVER", "mysql"), patch(
            "config.config_manager.DB_USER", "testuser"
        ), patch("config.config_manager.DB_PASSWD", "testpass"), patch(
            "config.config_manager.DB_HOST", "localhost"
        ), patch(
            "config.config_manager.DB_PORT", 3306
        ), patch(
            "config.config_manager.DB_NAME", "testdb"
        ), patch(
            "config.config_manager.DB_QUERY_JSON", None
        ):

            engine = ConfigManager.get_db_engine()
            assert engine.drivername == "mysql+mysqlconnector"

    def test_get_db_engine_postgresql(self):
        """Test database engine creation for PostgreSQL"""
        with patch("config.config_manager.ROMM_DB_DRIVER", "postgresql"), patch(
            "config.config_manager.DB_USER", "testuser"
        ), patch("config.config_manager.DB_PASSWD", "testpass"), patch(
            "config.config_manager.DB_HOST", "localhost"
        ), patch(
            "config.config_manager.DB_PORT", 5432
        ), patch(
            "config.config_manager.DB_NAME", "testdb"
        ), patch(
            "config.config_manager.DB_QUERY_JSON", None
        ):

            engine = ConfigManager.get_db_engine()
            assert engine.drivername == "postgresql+psycopg"

    @patch("config.config_manager.sys.exit")
    def test_get_db_engine_unsupported_driver(self, mock_exit):
        """Test database engine creation with unsupported driver"""
        with patch("config.config_manager.ROMM_DB_DRIVER", "unsupported"), patch(
            "config.config_manager.log.critical"
        ) as mock_log:

            ConfigManager.get_db_engine()
            mock_log.assert_called()
            mock_exit.assert_called_with(3)

    @patch("config.config_manager.sys.exit")
    def test_get_db_engine_missing_credentials(self, mock_exit):
        """Test database engine creation with missing credentials"""
        with patch("config.config_manager.ROMM_DB_DRIVER", "mysql"), patch(
            "config.config_manager.DB_USER", None
        ), patch("config.config_manager.DB_PASSWD", None), patch(
            "config.config_manager.log.critical"
        ) as mock_log:

            ConfigManager.get_db_engine()
            mock_log.assert_called()
            mock_exit.assert_called_with(3)

    def test_get_db_engine_with_query_json(self):
        """Test database engine creation with query JSON"""
        query_json = '{"charset": "utf8", "ssl": "true"}'
        with patch("config.config_manager.ROMM_DB_DRIVER", "mysql"), patch(
            "config.config_manager.DB_USER", "testuser"
        ), patch("config.config_manager.DB_PASSWD", "testpass"), patch(
            "config.config_manager.DB_HOST", "localhost"
        ), patch(
            "config.config_manager.DB_PORT", 3306
        ), patch(
            "config.config_manager.DB_NAME", "testdb"
        ), patch(
            "config.config_manager.DB_QUERY_JSON", query_json
        ):

            engine = ConfigManager.get_db_engine()
            assert engine.query == {"charset": "utf8", "ssl": "true"}

    @patch("config.config_manager.sys.exit")
    def test_get_db_engine_invalid_query_json(self, mock_exit):
        """Test database engine creation with invalid query JSON"""
        with patch("config.config_manager.ROMM_DB_DRIVER", "mysql"), patch(
            "config.config_manager.DB_USER", "testuser"
        ), patch("config.config_manager.DB_PASSWD", "testpass"), patch(
            "config.config_manager.DB_HOST", "localhost"
        ), patch(
            "config.config_manager.DB_PORT", 3306
        ), patch(
            "config.config_manager.DB_NAME", "testdb"
        ), patch(
            "config.config_manager.DB_QUERY_JSON", "invalid json"
        ), patch(
            "config.config_manager.log.critical"
        ) as mock_log:

            ConfigManager.get_db_engine()
            mock_log.assert_called()
            mock_exit.assert_called_with(3)

    def test_parse_config(self):
        """Test config parsing from raw config"""
        manager = ConfigManager()
        manager._raw_config = {
            "exclude": {
                "platforms": ["test1", "test2"],
                "roms": {
                    "single_file": {
                        "extensions": ["ZIP", "RAR"],
                        "names": ["readme.txt"],
                    },
                    "multi_file": {
                        "names": ["game.part1"],
                        "parts": {"extensions": ["TXT"], "names": ["data.xml"]},
                    },
                },
            },
            "system": {"platforms": {"gc": "ngc"}, "versions": {"naomi": "arcade"}},
            "filesystem": {"roms_folder": "ROMS", "firmware_folder": "BIOS"},
        }

        manager._parse_config()

        assert manager.config.EXCLUDED_PLATFORMS == ["test1", "test2"]
        assert manager.config.EXCLUDED_SINGLE_EXT == ["zip", "rar"]
        assert manager.config.EXCLUDED_SINGLE_FILES == ["readme.txt"]
        assert manager.config.EXCLUDED_MULTI_FILES == ["game.part1"]
        assert manager.config.EXCLUDED_MULTI_PARTS_EXT == ["txt"]
        assert manager.config.EXCLUDED_MULTI_PARTS_FILES == ["data.xml"]
        assert manager.config.PLATFORMS_BINDING == {"gc": "ngc"}
        assert manager.config.PLATFORMS_VERSIONS == {"naomi": "arcade"}
        assert manager.config.ROMS_FOLDER_NAME == "ROMS"
        assert manager.config.FIRMWARE_FOLDER_NAME == "BIOS"

    def test_parse_config_empty(self):
        """Test config parsing with empty config"""
        manager = ConfigManager()
        manager._raw_config = {}

        manager._parse_config()

        assert manager.config.EXCLUDED_PLATFORMS == []
        assert manager.config.EXCLUDED_SINGLE_EXT == []
        assert manager.config.EXCLUDED_SINGLE_FILES == []
        assert manager.config.EXCLUDED_MULTI_FILES == []
        assert manager.config.EXCLUDED_MULTI_PARTS_EXT == []
        assert manager.config.EXCLUDED_MULTI_PARTS_FILES == []
        assert manager.config.PLATFORMS_BINDING == {}
        assert manager.config.PLATFORMS_VERSIONS == {}
        assert manager.config.ROMS_FOLDER_NAME == "roms"
        assert manager.config.FIRMWARE_FOLDER_NAME == "bios"

    def test_validate_config_valid(self):
        """Test config validation with valid config"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        # Should not raise any exceptions
        manager._validate_config()

    @patch("config.config_manager.sys.exit")
    def test_validate_config_invalid_excluded_platforms(self, mock_exit):
        """Test config validation with invalid excluded platforms"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS="not a list",
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch("config.config_manager.log.critical") as mock_log:
            manager._validate_config()
            mock_log.assert_called()
            mock_exit.assert_called_with(3)

    @patch("config.config_manager.sys.exit")
    def test_validate_config_empty_roms_folder(self, mock_exit):
        """Test config validation with empty ROMs folder name"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch("config.config_manager.log.critical") as mock_log:
            manager._validate_config()
            mock_log.assert_called()
            mock_exit.assert_called_with(3)

    @patch("config.config_manager.sys.exit")
    def test_validate_config_invalid_platforms_binding(self, mock_exit):
        """Test config validation with invalid platforms binding"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={"gc": None},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch("config.config_manager.log.critical") as mock_log:
            manager._validate_config()
            mock_log.assert_called()
            mock_exit.assert_called_with(3)

    def test_get_config(self):
        """Test getting config from file"""
        config_data = {
            "exclude": {
                "platforms": ["test"],
                "roms": {
                    "single_file": {"extensions": ["zip"], "names": ["readme.txt"]},
                    "multi_file": {
                        "names": ["game.part1"],
                        "parts": {"extensions": ["txt"], "names": ["data.xml"]},
                    },
                },
            },
            "system": {"platforms": {"gc": "ngc"}, "versions": {"naomi": "arcade"}},
            "filesystem": {"roms_folder": "ROMS", "firmware_folder": "BIOS"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            manager = ConfigManager(config_file)
            config = manager.get_config()

            assert config.EXCLUDED_PLATFORMS == ["test"]
            assert config.EXCLUDED_SINGLE_EXT == ["zip"]
            assert config.EXCLUDED_SINGLE_FILES == ["readme.txt"]
            assert config.EXCLUDED_MULTI_FILES == ["game.part1"]
            assert config.EXCLUDED_MULTI_PARTS_EXT == ["txt"]
            assert config.EXCLUDED_MULTI_PARTS_FILES == ["data.xml"]
            assert config.PLATFORMS_BINDING == {"gc": "ngc"}
            assert config.PLATFORMS_VERSIONS == {"naomi": "arcade"}
            assert config.ROMS_FOLDER_NAME == "ROMS"
            assert config.FIRMWARE_FOLDER_NAME == "BIOS"
        finally:
            os.unlink(config_file)

    def test_update_config_file(self):
        """Test updating config file"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=["test1"],
            EXCLUDED_SINGLE_EXT=["zip"],
            EXCLUDED_SINGLE_FILES=["readme.txt"],
            EXCLUDED_MULTI_FILES=["game.part1"],
            EXCLUDED_MULTI_PARTS_EXT=["txt"],
            EXCLUDED_MULTI_PARTS_FILES=["data.xml"],
            PLATFORMS_BINDING={"gc": "ngc"},
            PLATFORMS_VERSIONS={"naomi": "arcade"},
            ROMS_FOLDER_NAME="ROMS",
            FIRMWARE_FOLDER_NAME="BIOS",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            config_file = f.name

        try:
            manager.config_file = config_file
            manager.update_config_file()

            # Read back the file to verify
            with open(config_file, "r") as f:
                saved_config = yaml.safe_load(f)

            assert saved_config["exclude"]["platforms"] == ["test1"]
            assert saved_config["exclude"]["roms"]["single_file"]["extensions"] == [
                "zip"
            ]
            assert saved_config["exclude"]["roms"]["single_file"]["names"] == [
                "readme.txt"
            ]
            assert saved_config["exclude"]["roms"]["multi_file"]["names"] == [
                "game.part1"
            ]
            assert saved_config["exclude"]["roms"]["multi_file"]["parts"][
                "extensions"
            ] == ["txt"]
            assert saved_config["exclude"]["roms"]["multi_file"]["parts"]["names"] == [
                "data.xml"
            ]
            assert saved_config["system"]["platforms"] == {"gc": "ngc"}
            assert saved_config["system"]["versions"] == {"naomi": "arcade"}
            assert saved_config["filesystem"]["roms_folder"] == "ROMS"
            assert saved_config["filesystem"]["firmware_folder"] == "BIOS"
        finally:
            os.unlink(config_file)

    def test_update_config_file_permission_error(self):
        """Test updating config file with permission error"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(ConfigNotWritableException):
                manager.update_config_file()

    def test_add_platform_binding_new(self):
        """Test adding new platform binding"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.add_platform_binding("gc", "ngc")

            assert manager.config.PLATFORMS_BINDING == {"gc": "ngc"}
            mock_update.assert_called_once()

    def test_add_platform_binding_existing(self):
        """Test adding existing platform binding"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={"gc": "ngc"},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch("config.config_manager.log.warning") as mock_warning, patch.object(
            manager, "update_config_file"
        ) as mock_update:

            manager.add_platform_binding("gc", "ngc")

            # Should not update config file
            mock_update.assert_not_called()
            mock_warning.assert_called_once()

    def test_remove_platform_binding_existing(self):
        """Test removing existing platform binding"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={"gc": "ngc"},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.remove_platform_binding("gc")

            assert manager.config.PLATFORMS_BINDING == {}
            mock_update.assert_called_once()

    def test_remove_platform_binding_nonexistent(self):
        """Test removing nonexistent platform binding"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.remove_platform_binding("nonexistent")

            # Should still update config file
            mock_update.assert_called_once()

    def test_add_platform_version_new(self):
        """Test adding new platform version"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.add_platform_version("naomi", "arcade")

            assert manager.config.PLATFORMS_VERSIONS == {"naomi": "arcade"}
            mock_update.assert_called_once()

    def test_add_platform_version_existing(self):
        """Test adding existing platform version"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={"naomi": "arcade"},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch("config.config_manager.log.warning") as mock_warning, patch.object(
            manager, "update_config_file"
        ) as mock_update:

            manager.add_platform_version("naomi", "arcade")

            # Should not update config file
            mock_update.assert_not_called()
            mock_warning.assert_called_once()

    def test_remove_platform_version_existing(self):
        """Test removing existing platform version"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={"naomi": "arcade"},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.remove_platform_version("naomi")

            assert manager.config.PLATFORMS_VERSIONS == {}
            mock_update.assert_called_once()

    def test_add_exclusion_new(self):
        """Test adding new exclusion"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.add_exclusion("EXCLUDED_PLATFORMS", "test_platform")

            assert "test_platform" in manager.config.EXCLUDED_PLATFORMS
            mock_update.assert_called_once()

    def test_add_exclusion_existing(self):
        """Test adding existing exclusion"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=["test_platform"],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch("config.config_manager.log.warning") as mock_warning, patch.object(
            manager, "update_config_file"
        ) as mock_update:

            manager.add_exclusion("EXCLUDED_PLATFORMS", "test_platform")

            # Should not update config file
            mock_update.assert_not_called()
            mock_warning.assert_called_once()

    def test_remove_exclusion_existing(self):
        """Test removing existing exclusion"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=["test_platform"],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.remove_exclusion("EXCLUDED_PLATFORMS", "test_platform")

            assert "test_platform" not in manager.config.EXCLUDED_PLATFORMS
            mock_update.assert_called_once()

    def test_remove_exclusion_nonexistent(self):
        """Test removing nonexistent exclusion"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with patch.object(manager, "update_config_file") as mock_update:
            manager.remove_exclusion("EXCLUDED_PLATFORMS", "nonexistent")

            # Should still update config file
            mock_update.assert_called_once()

    def test_add_exclusion_invalid_type(self):
        """Test adding exclusion with invalid type"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with pytest.raises(AttributeError):
            manager.add_exclusion("INVALID_TYPE", "test_value")

    def test_remove_exclusion_invalid_type(self):
        """Test removing exclusion with invalid type"""
        manager = ConfigManager()
        manager.config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

        with pytest.raises(AttributeError):
            manager.remove_exclusion("INVALID_TYPE", "test_value")


class TestConfigManagerIntegration:
    """Integration tests for ConfigManager"""

    def test_full_config_lifecycle(self):
        """Test complete config lifecycle: create, modify, save, reload"""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            config_file = f.name

        try:
            # Initial config
            initial_config = {
                "exclude": {
                    "platforms": ["initial_platform"],
                    "roms": {
                        "single_file": {"extensions": ["zip"], "names": ["readme.txt"]},
                        "multi_file": {
                            "names": ["game.part1"],
                            "parts": {"extensions": ["txt"], "names": ["data.xml"]},
                        },
                    },
                },
                "system": {"platforms": {"gc": "ngc"}, "versions": {"naomi": "arcade"}},
                "filesystem": {"roms_folder": "ROMS", "firmware_folder": "BIOS"},
            }

            yaml.dump(initial_config, f)

            # Create manager and load config
            manager = ConfigManager(config_file)
            config = manager.get_config()

            # Verify initial state
            assert config.EXCLUDED_PLATFORMS == ["initial_platform"]
            assert config.PLATFORMS_BINDING == {"gc": "ngc"}

            # Modify config
            manager.add_platform_binding("psx", "playstation")
            manager.add_exclusion("EXCLUDED_PLATFORMS", "new_platform")

            # Verify modifications
            assert "psx" in config.PLATFORMS_BINDING
            assert config.PLATFORMS_BINDING["psx"] == "playstation"
            assert "new_platform" in config.EXCLUDED_PLATFORMS

            # Create new manager instance to test persistence
            new_manager = ConfigManager(config_file)
            new_config = new_manager.get_config()

            # Verify persistence
            assert "psx" in new_config.PLATFORMS_BINDING
            assert new_config.PLATFORMS_BINDING["psx"] == "playstation"
            assert "new_platform" in new_config.EXCLUDED_PLATFORMS

        finally:
            os.unlink(config_file)

    def test_config_with_special_characters(self):
        """Test config handling with special characters in values"""
        config_data = {
            "exclude": {
                "platforms": ["platform with spaces", "platform-with-dashes"],
                "roms": {
                    "single_file": {
                        "extensions": ["zip", "rar", "7z"],
                        "names": ["readme.txt", "info.md", "license.txt"],
                    }
                },
            },
            "system": {
                "platforms": {"gc": "ngc", "psx": "playstation"},
                "versions": {"naomi": "arcade", "atomiswave": "arcade"},
            },
            "filesystem": {
                "roms_folder": "ROMS_FOLDER",
                "firmware_folder": "BIOS_FOLDER",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            manager = ConfigManager(config_file)
            config = manager.get_config()

            # Test special characters in platform names
            assert "platform with spaces" in config.EXCLUDED_PLATFORMS
            assert "platform-with-dashes" in config.EXCLUDED_PLATFORMS

            # Test special characters in file extensions
            assert "zip" in config.EXCLUDED_SINGLE_EXT
            assert "rar" in config.EXCLUDED_SINGLE_EXT
            assert "7z" in config.EXCLUDED_SINGLE_EXT

            # Test special characters in file names
            assert "readme.txt" in config.EXCLUDED_SINGLE_FILES
            assert "info.md" in config.EXCLUDED_SINGLE_FILES
            assert "license.txt" in config.EXCLUDED_SINGLE_FILES

        finally:
            os.unlink(config_file)
