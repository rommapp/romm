import functools

from config import LAUNCHBOX_BASE_PATH
from handler.filesystem.base_handler import FSHandler


class FSLaunchboxHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=LAUNCHBOX_BASE_PATH)


@functools.cache
def get_fs_launchbox_handler() -> FSLaunchboxHandler:
    """Lazily instantiate the LaunchBox handler on first use.

    Deferred so that startup doesn't fail when the LaunchBox feature is
    unconfigured or its base path is not writable.
    """
    return FSLaunchboxHandler()
