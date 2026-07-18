import pytest

from config.config_manager import ConfigManager
from config.config_manager import config_manager as cm


@pytest.fixture(autouse=True)
def restore_config_manager_singleton():
    """``ConfigManager`` is a process-wide singleton (``__new__`` returns the
    shared instance). Tests in this module point it at temporary config files
    and mutate it (e.g. ``add_platform_binding``), which would otherwise leak
    that state into other test modules through the global ``config_manager``.

    Re-initialize the singleton from its original config file after each test
    so the global instance returns to its default state.
    """
    original_config_file = cm.config_file
    yield
    ConfigManager(original_config_file)
