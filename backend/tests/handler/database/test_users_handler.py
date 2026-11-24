import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from exceptions.database_exceptions import LastAdminError
from handler.database import (
    db_device_handler,
    db_play_session_handler,
    db_user_handler,
)
from handler.database.base_handler import sync_engine, sync_session
from models.device import Device
from models.play_session import PlaySession
from models.rom import Rom
from models.user import Role, User
from utils.database import is_postgresql
from utils.datetime import to_utc


@pytest.fixture
def other_admin() -> User:
    return db_user_handler.add_user(
        User(username="other_admin", hashed_password="x", role=Role.ADMIN)
    )


def _role(user: User) -> Role:
    current = db_user_handler.get_user(user.id)
    assert current
    return current.role


class TestKeepAnAdmin:
    def test_the_last_admin_cannot_be_demoted(self, admin_user: User):
        with pytest.raises(LastAdminError):
            db_user_handler.update_user(
                admin_user.id, {"role": Role.USER}, keep_an_admin=True
            )

        assert _role(admin_user) == Role.ADMIN

    def test_the_last_admin_cannot_be_deleted(self, admin_user: User):
        with pytest.raises(LastAdminError):
            db_user_handler.delete_user(admin_user.id, keep_an_admin=True)

        assert db_user_handler.get_user(admin_user.id) is not None

    def test_one_of_two_admins_can_be_demoted(
        self, admin_user: User, other_admin: User
    ):
        db_user_handler.update_user(
            other_admin.id, {"role": Role.USER}, keep_an_admin=True
        )

        assert _role(other_admin) == Role.USER

    def test_one_of_two_admins_can_be_deleted(
        self, admin_user: User, other_admin: User
    ):
        db_user_handler.delete_user(other_admin.id, keep_an_admin=True)

        assert db_user_handler.get_user(other_admin.id) is None

    def test_other_edits_of_the_last_admin_go_through(self, admin_user: User):
        db_user_handler.update_user(
            admin_user.id, {"ra_username": "player"}, keep_an_admin=True
        )

    def test_a_user_can_be_deleted_with_one_admin_left(
        self, admin_user: User, viewer_user: User
    ):
        db_user_handler.delete_user(viewer_user.id, keep_an_admin=True)

        assert db_user_handler.get_user(viewer_user.id) is None

    def test_without_the_flag_the_last_admin_can_be_demoted(self, admin_user: User):
        # The OIDC role sync relies on this: the provider's claims win.
        db_user_handler.update_user(admin_user.id, {"role": Role.USER})

        assert _role(admin_user) == Role.USER

    def test_two_admins_demoting_each_other_leave_one(
        self, admin_user: User, other_admin: User
    ):
        errors: list[Exception] = []

        def demote_admin_user() -> None:
            try:
                db_user_handler.update_user(
                    admin_user.id, {"role": Role.USER}, keep_an_admin=True
                )
            except Exception as exc:
                errors.append(exc)

        # The first demotion holds its locks while the second one starts.
        with sync_session.begin() as session:
            db_user_handler.update_user(
                other_admin.id,
                {"role": Role.USER},
                keep_an_admin=True,
                session=session,
            )
            second = threading.Thread(target=demote_admin_user)
            second.start()
            second.join(timeout=1)
            assert second.is_alive(), "the second demotion did not wait for the lock"
        second.join(timeout=30)

        assert not second.is_alive()
        assert [type(error) for error in errors] == [LastAdminError]
        assert (_role(admin_user), _role(other_admin)) == (Role.ADMIN, Role.USER)


class TestDeleteUser:
    def test_only_their_devices_and_play_sessions_go(
        self, admin_user: User, editor_user: User, rom: Rom
    ):
        # A restored dump puts the unique key first, so InnoDB checks the user with it.
        with sync_engine.connect() as conn:
            if not is_postgresql(conn):
                conn.execute(text("ALTER TABLE play_sessions FORCE"))
        started = datetime.now(timezone.utc).replace(microsecond=0)
        for user in (admin_user, editor_user):
            device = db_device_handler.add_device(
                Device(id=f"{user.username}-device", user_id=user.id, name="Handheld")
            )
            db_play_session_handler.add_sessions(
                [
                    PlaySession(
                        user_id=user.id,
                        device_id=device_id,
                        rom_id=rom.id,
                        start_time=started,
                        end_time=started + timedelta(minutes=30),
                        duration_ms=30 * 60 * 1000,
                    )
                    for device_id in (device.id, None)
                ]
            )

        db_user_handler.delete_user(editor_user.id)

        assert db_user_handler.get_user(editor_user.id) is None
        assert db_device_handler.get_devices(user_id=editor_user.id) == []
        assert db_play_session_handler.get_sessions(user_id=editor_user.id) == []
        left = db_play_session_handler.get_sessions(user_id=admin_user.id)
        assert {session.device_id for session in left} == {
            f"{admin_user.username}-device",
            None,
        }


class TestUpdateLastActive:
    def test_bumps_a_user_never_active(self, admin_user: User):
        db_user_handler.update_user(admin_user.id, {"last_active": None})

        db_user_handler.update_last_active(admin_user.id)

        current = db_user_handler.get_user(admin_user.id)
        assert current is not None
        assert current.last_active is not None

    def test_skips_a_user_active_within_the_debounce_window(self, admin_user: User):
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_user_handler.update_user(admin_user.id, {"last_active": recent})

        db_user_handler.update_last_active(admin_user.id)

        current = db_user_handler.get_user(admin_user.id)
        assert current is not None
        assert current.last_active is not None
        assert abs((to_utc(current.last_active) - recent).total_seconds()) < 1

    def test_set_last_active_writes_nothing_inside_the_window(
        self, admin_user: User, executed_statements: list[str]
    ):
        user = db_user_handler.update_user(
            admin_user.id, {"last_active": datetime.now(timezone.utc)}
        )
        executed_statements.clear()

        user.set_last_active()

        assert executed_statements == []


class TestReplaceAvatarPath:
    def test_sets_the_path_while_it_is_still_the_expected_one(self, admin_user: User):
        db_user_handler.update_user(admin_user.id, {"avatar_path": "old.png"})

        replaced = db_user_handler.replace_avatar_path(
            admin_user.id, "old.png", "new.png"
        )

        current = db_user_handler.get_user(admin_user.id)
        assert replaced
        assert current is not None
        assert current.avatar_path == "new.png"

    def test_leaves_a_path_that_changed_meanwhile(self, admin_user: User):
        db_user_handler.update_user(admin_user.id, {"avatar_path": "uploaded.png"})

        replaced = db_user_handler.replace_avatar_path(
            admin_user.id, "old.png", "new.png"
        )

        current = db_user_handler.get_user(admin_user.id)
        assert not replaced
        assert current is not None
        assert current.avatar_path == "uploaded.png"
