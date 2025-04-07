import os
import shutil
from pathlib import Path

from config import ASSETS_BASE_PATH
from fastapi import UploadFile
from logger.logger import log
from models.user import User

from .base_handler import FSHandler


class FSAssetsHandler(FSHandler):
    def __init__(self) -> None:
        pass

    def remove_file(self, file_name: str, file_path: str):
        try:
            os.remove(os.path.join(ASSETS_BASE_PATH, file_path, file_name))
        except IsADirectoryError:
            shutil.rmtree(os.path.join(ASSETS_BASE_PATH, file_path, file_name))

    def write_file(self, file: UploadFile, path: str) -> None:
        if not file.filename:
            log.error("No file name provided")
            return

        Path(os.path.join(ASSETS_BASE_PATH, path)).mkdir(parents=True, exist_ok=True)
        log.info(f" - Uploading {file.filename}")
        file_location = os.path.join(ASSETS_BASE_PATH, path, file.filename)

        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

    def get_asset_size(self, file_name: str, asset_path: str) -> int:
        return os.path.getsize(os.path.join(ASSETS_BASE_PATH, asset_path, file_name))

    def user_folder_path(self, user: User):
        return os.path.join("users", user.fs_safe_folder_name)

    # /users/557365723a31/profile
    def build_avatar_path(self, user: User):
        return os.path.join(self.user_folder_path(user), "profile")

    def _build_asset_file_path(
        self, user: User, folder: str, platform_fs_slug, emulator: str | None = None
    ):
        user_folder_path = self.user_folder_path(user)
        if emulator:
            return os.path.join(user_folder_path, folder, platform_fs_slug, emulator)
        return os.path.join(user_folder_path, folder, platform_fs_slug)

    # /users/557365723a31/saves/n64/mupen64plus
    def build_saves_file_path(
        self, user: User, platform_fs_slug: str, emulator: str | None = None
    ):
        return self._build_asset_file_path(user, "saves", platform_fs_slug)

    # /users/557365723a31/states/n64/mupen64plus
    def build_states_file_path(
        self, user: User, platform_fs_slug: str, emulator: str | None = None
    ):
        return self._build_asset_file_path(user, "saves", platform_fs_slug)

    # /users/557365723a31/screenshots/n64
    def build_screenshots_file_path(self, user: User, platform_fs_slug: str):
        return self._build_asset_file_path(user, "screenshots", platform_fs_slug)
