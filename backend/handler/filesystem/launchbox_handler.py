from config import LAUNCHBOX_BASE_PATH
from handler.filesystem.base_handler import FSHandler


class FSLaunchboxHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=LAUNCHBOX_BASE_PATH, tolerate_missing_base=True)
