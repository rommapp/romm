import re
import secrets
from contextlib import suppress

from adapters.services.smb_controller import SmbControllerError, smb_controller
from models.smb import SmbAccessMode, SmbPlatformPermission, SmbUser

from handler.database import db_platform_handler, db_smb_handler
from handler.filesystem import fs_platform_handler


def _share_name(platform_id: int, fs_slug: str) -> str:
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", fs_slug).strip("_")
    return f"platform_{platform_id}_{safe_slug[:40]}"


class SmbAccessHandler:
    def list_users(self):
        return db_smb_handler.list_users()

    def get_user(self, user_id: int) -> SmbUser | None:
        return db_smb_handler.get_user(user_id)

    def get_user_by_username(self, username: str) -> SmbUser | None:
        return db_smb_handler.get_user_by_username(username)

    def create_user(
        self,
        username: str,
        permissions: list[tuple[int, SmbAccessMode]],
    ) -> tuple[SmbUser, str]:
        validated = self._build_permissions(permissions)
        raw_password = secrets.token_urlsafe(24)
        user = db_smb_handler.add_user(
            SmbUser(username=username, permissions=validated)
        )
        try:
            smb_controller.create_user(username, raw_password)
            self.sync_config()
        except SmbControllerError:
            with suppress(SmbControllerError):
                smb_controller.delete_user(username)
            db_smb_handler.delete_user(user.id)
            raise
        return user, raw_password

    def update_user(
        self,
        user_id: int,
        permissions: list[tuple[int, SmbAccessMode]],
    ) -> SmbUser | None:
        validated = self._build_permissions(permissions)
        current_user = db_smb_handler.get_user(user_id)
        if current_user is None:
            return None
        previous_permissions = [
            SmbPlatformPermission(
                platform_id=permission.platform_id,
                access=permission.access,
            )
            for permission in current_user.permissions
        ]
        user = db_smb_handler.replace_permissions(user_id, validated)
        if user is not None:
            try:
                self.sync_config()
            except SmbControllerError:
                db_smb_handler.replace_permissions(user_id, previous_permissions)
                with suppress(SmbControllerError):
                    self.sync_config()
                raise
        return user

    def rotate_password(self, user_id: int) -> tuple[SmbUser, str] | None:
        user = db_smb_handler.get_user(user_id)
        if user is None:
            return None
        raw_password = secrets.token_urlsafe(24)
        smb_controller.rotate_user(user.username, raw_password)
        return user, raw_password

    def delete_user(self, user_id: int) -> bool:
        user = db_smb_handler.get_user(user_id)
        if user is None:
            return False
        smb_controller.delete_user(user.username)
        deleted = db_smb_handler.delete_user(user_id) > 0
        self.sync_config()
        return deleted

    def sync_config(self, excluded_platform_ids: set[int] | None = None) -> None:
        excluded_platform_ids = excluded_platform_ids or set()
        users = []
        for user in db_smb_handler.list_users():
            permissions = []
            for permission in user.permissions:
                platform = permission.platform
                if platform.id in excluded_platform_ids:
                    continue
                permissions.append(
                    {
                        "platform_id": platform.id,
                        "share_name": _share_name(platform.id, platform.fs_slug),
                        "path": fs_platform_handler.get_platform_fs_structure(
                            platform.fs_slug
                        ),
                        "access": permission.access.value,
                    }
                )
            users.append({"username": user.username, "permissions": permissions})
        smb_controller.sync_config(users)

    def _build_permissions(
        self,
        permissions: list[tuple[int, SmbAccessMode]],
    ) -> list[SmbPlatformPermission]:
        platform_ids = [platform_id for platform_id, _ in permissions]
        if len(platform_ids) != len(set(platform_ids)):
            raise ValueError("Each platform can only be assigned once")

        result = []
        for platform_id, access in permissions:
            platform = db_platform_handler.get_platform(platform_id)
            if platform is None:
                raise ValueError(f"Platform {platform_id} was not found")
            if platform.missing_from_fs:
                raise ValueError(
                    f"Platform {platform.display_name if hasattr(platform, 'display_name') else platform.name} is missing from the filesystem"
                )
            result.append(
                SmbPlatformPermission(platform_id=platform_id, access=access)
            )
        return result


smb_access_handler = SmbAccessHandler()
