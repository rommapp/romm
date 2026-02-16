import hashlib
import os
import zipfile

from config import ASSETS_BASE_PATH
from logger.logger import log
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

    async def _compute_file_hash(self, file_path: str) -> str:
        hash_obj = hashlib.md5(usedforsecurity=False)
        async with await self.stream_file(file_path=file_path) as f:
            while chunk := await f.read(8192):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    async def _compute_zip_hash(self, zip_path: str) -> str:
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_hashes = []
            for name in sorted(zf.namelist()):
                if not name.endswith("/"):
                    content = zf.read(name)
                    file_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()
                    file_hashes.append(f"{name}:{file_hash}")
            combined = "\n".join(file_hashes)
            return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()

    async def compute_content_hash(self, file_path: str) -> str | None:
        try:
            if zipfile.is_zipfile(file_path):
                return await self._compute_zip_hash(file_path)
            return await self._compute_file_hash(file_path)
        except Exception as e:
            log.debug(f"Failed to compute content hash for {file_path}: {e}")
            return None
