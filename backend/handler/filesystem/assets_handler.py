import os

from config import ASSETS_BASE_PATH
from models.user import User

from .base_handler import FSHandler


class FSAssetsHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=ASSETS_BASE_PATH)

    def user_folder_path(self, user: User):
        return os.path.join("users", user.fs_safe_folder_name)

    # /users/557365723a31/profile
    def build_avatar_path(self, user: User):
        return os.path.join(self.user_folder_path(user), "profile")

    def _build_asset_file_path(
        self,
        user: User,
        folder: str,
        platform_fs_slug: str,
        rom_id: int,
        emulator: str | None = None,
    ):
        user_folder_path = self.user_folder_path(user)
        assets_path = os.path.join(
            user_folder_path, folder, platform_fs_slug, str(rom_id)
        )
        if emulator:
            assets_path = os.path.join(assets_path, emulator)
        return assets_path

    # /users/557365723a31/saves/n64/{rom.id}/mupen64plus/
    def build_saves_file_path(
        self,
        user: User,
        platform_fs_slug: str,
        rom_id: int,
        emulator: str | None = None,
    ):
        return self._build_asset_file_path(
            user, "saves", platform_fs_slug, rom_id, emulator
        )

    # /users/557365723a31/states/n64/{rom.id}/mupen64plus
    def build_states_file_path(
        self,
        user: User,
        platform_fs_slug: str,
        rom_id: int,
        emulator: str | None = None,
    ):
        return self._build_asset_file_path(
            user, "states", platform_fs_slug, rom_id, emulator
        )

    # /users/557365723a31/screenshots/{rom.id}/n64
    def build_screenshots_file_path(
        self, user: User, platform_fs_slug: str, rom_id: int
    ):
        return self._build_asset_file_path(
            user, "screenshots", platform_fs_slug, rom_id
        )
