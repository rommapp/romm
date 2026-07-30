import pytest
from adapters.services.smb_controller import SmbControllerError
from handler.database import db_smb_handler
from handler.smb_access_handler import smb_access_handler
from models.smb import SmbAccessMode, SmbPlatformPermission, SmbUser


def test_replace_permissions_updates_existing_platform_access(platform):
    user = db_smb_handler.add_user(
        SmbUser(
            username="lounge",
            permissions=[
                SmbPlatformPermission(
                    platform_id=platform.id,
                    access=SmbAccessMode.READ,
                )
            ],
        )
    )

    updated = db_smb_handler.replace_permissions(
        user.id,
        [
            SmbPlatformPermission(
                platform_id=platform.id,
                access=SmbAccessMode.WRITE,
            )
        ],
    )

    assert updated is not None
    assert len(updated.permissions) == 1
    assert updated.permissions[0].platform_id == platform.id
    assert updated.permissions[0].access == SmbAccessMode.WRITE

    persisted = db_smb_handler.get_user(user.id)
    assert persisted is not None
    assert len(persisted.permissions) == 1
    assert persisted.permissions[0].access == SmbAccessMode.WRITE


def test_delete_user_cascades_platform_permissions(platform):
    user = db_smb_handler.add_user(
        SmbUser(
            username="bedroom",
            permissions=[
                SmbPlatformPermission(
                    platform_id=platform.id,
                    access=SmbAccessMode.READ,
                )
            ],
        )
    )

    assert db_smb_handler.delete_user(user.id) == 1
    assert db_smb_handler.get_user(user.id) is None


def test_update_user_restores_permissions_when_samba_sync_fails(platform, mocker):
    user = db_smb_handler.add_user(
        SmbUser(
            username="office",
            permissions=[
                SmbPlatformPermission(
                    platform_id=platform.id,
                    access=SmbAccessMode.READ,
                )
            ],
        )
    )
    sync = mocker.patch(
        "handler.smb_access_handler.smb_controller.sync_config",
        side_effect=SmbControllerError("controller unavailable"),
    )

    with pytest.raises(SmbControllerError, match="controller unavailable"):
        smb_access_handler.update_user(
            user.id,
            [(platform.id, SmbAccessMode.WRITE)],
        )

    persisted = db_smb_handler.get_user(user.id)
    assert persisted is not None
    assert len(persisted.permissions) == 1
    assert persisted.permissions[0].access == SmbAccessMode.READ
    assert sync.call_count == 2
