from pathlib import Path

from config import ROMM_BASE_PATH
from handler.filesystem.base_handler import FSHandler


class FSLaunchboxHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=str(Path(ROMM_BASE_PATH) / "launchbox"))
