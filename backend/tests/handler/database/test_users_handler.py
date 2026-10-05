import threading

import pytest

from exceptions.database_exceptions import LastAdminError
from handler.database import db_user_handler
from handler.database.base_handler import sync_session
from models.user import Role, User


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
