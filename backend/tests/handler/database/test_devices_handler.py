from datetime import datetime, timedelta, timezone

from handler.database import db_device_handler
from models.device import Device
from models.user import User
from utils.datetime import to_utc


class TestGetDeviceByClientIdentifier:
    def test_returns_device_for_matching_user_and_identifier(self, admin_user: User):
        db_device_handler.add_device(
            Device(
                id="cid-device-1",
                user_id=admin_user.id,
                name="A",
                client_device_identifier="install-abc",
            )
        )

        found = db_device_handler.get_device_by_client_identifier(
            user_id=admin_user.id,
            client_device_identifier="install-abc",
        )

        assert found is not None
        assert found.id == "cid-device-1"

    def test_returns_none_for_unknown_identifier(self, admin_user: User):
        db_device_handler.add_device(
            Device(
                id="cid-device-2",
                user_id=admin_user.id,
                client_device_identifier="install-abc",
            )
        )

        found = db_device_handler.get_device_by_client_identifier(
            user_id=admin_user.id,
            client_device_identifier="does-not-exist",
        )

        assert found is None

    def test_scopes_by_user(self, admin_user: User, editor_user: User):
        db_device_handler.add_device(
            Device(
                id="cid-device-admin",
                user_id=admin_user.id,
                client_device_identifier="shared-identifier",
            )
        )
        db_device_handler.add_device(
            Device(
                id="cid-device-editor",
                user_id=editor_user.id,
                client_device_identifier="shared-identifier",
            )
        )

        admin_found = db_device_handler.get_device_by_client_identifier(
            user_id=admin_user.id,
            client_device_identifier="shared-identifier",
        )
        editor_found = db_device_handler.get_device_by_client_identifier(
            user_id=editor_user.id,
            client_device_identifier="shared-identifier",
        )

        assert admin_found is not None
        assert editor_found is not None
        assert admin_found.id == "cid-device-admin"
        assert editor_found.id == "cid-device-editor"

    def test_empty_identifier_returns_none(self, admin_user: User):
        db_device_handler.add_device(
            Device(
                id="cid-device-3",
                user_id=admin_user.id,
                client_device_identifier=None,
            )
        )

        found = db_device_handler.get_device_by_client_identifier(
            user_id=admin_user.id,
            client_device_identifier="",
        )
        assert found is None


class TestUpdateLastSeenDebounced:
    def test_bumps_when_last_seen_is_null(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="debounce-fresh", user_id=admin_user.id, last_seen=None)
        )

        db_device_handler.update_last_seen_debounced(device_id=device.id)

        refreshed = db_device_handler.get_device_by_id(device.id)
        assert refreshed is not None
        assert refreshed.last_seen is not None

    def test_bumps_when_last_seen_is_old(self, admin_user: User):
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        device = db_device_handler.add_device(
            Device(id="debounce-old", user_id=admin_user.id, last_seen=old)
        )

        db_device_handler.update_last_seen_debounced(device_id=device.id)

        refreshed = db_device_handler.get_device_by_id(device.id)
        assert refreshed is not None
        assert refreshed.last_seen is not None
        # MariaDB returns naive datetimes; normalize to UTC for comparison
        assert to_utc(refreshed.last_seen) > old

    def test_skips_when_last_seen_within_debounce_window(self, admin_user: User):
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        device = db_device_handler.add_device(
            Device(id="debounce-recent", user_id=admin_user.id, last_seen=recent)
        )

        db_device_handler.update_last_seen_debounced(device_id=device.id)

        refreshed = db_device_handler.get_device_by_id(device.id)
        assert refreshed is not None
        # Unchanged: still within the 5-minute debounce window
        assert refreshed.last_seen is not None
        assert abs((to_utc(refreshed.last_seen) - recent).total_seconds()) < 1

    def test_noop_on_missing_device(self):
        # Should not raise
        db_device_handler.update_last_seen_debounced(device_id="does-not-exist")
