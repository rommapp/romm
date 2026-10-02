import logging

import pytest
from cryptography.fernet import Fernet
from tests.audit_events import recorded_events

from handler.database import db_user_handler
from handler.ra_login import clear_ra_login, ra_login_for_activate, store_ra_login
from models.user import User
from utils.secret_box import seal

TOKEN = "tok456secret"  # nosec B105


def _user(user_id: int) -> User:
    user = db_user_handler.get_user(user_id)
    assert user is not None
    return user


def test_the_stored_login_is_sealed_and_opens_back_up(admin_user: User):
    assert store_ra_login(admin_user.id, "alice", TOKEN) is True

    stored = _user(admin_user.id)
    assert stored.ra_login_sealed is not None
    assert TOKEN not in stored.ra_login_sealed
    assert "alice" not in stored.ra_login_sealed
    assert ra_login_for_activate(stored) == {"username": "alice", "token": TOKEN}


def test_storing_fills_an_empty_ra_username(admin_user: User):
    store_ra_login(admin_user.id, "alice", TOKEN)

    assert _user(admin_user.id).ra_username == "alice"


def test_storing_keeps_a_different_ra_username(admin_user: User, caplog):
    db_user_handler.update_user(admin_user.id, {"ra_username": "profile-name"})

    with caplog.at_level(logging.INFO, logger="romm"):
        store_ra_login(admin_user.id, "alice", TOKEN)

    stored = _user(admin_user.id)
    assert stored.ra_username == "profile-name"
    assert ra_login_for_activate(stored) == {"username": "alice", "token": TOKEN}
    assert str(admin_user.id) in caplog.text
    assert "alice" not in caplog.text
    assert TOKEN not in caplog.text


def test_storing_records_a_set_event_with_no_data(admin_user: User):
    store_ra_login(admin_user.id, "alice", TOKEN)

    [event] = recorded_events()
    assert event.action == "user.ra_login_set"
    assert event.actor_id == admin_user.id
    assert event.target_id == str(admin_user.id)
    assert event.data == {}


def test_clearing_nulls_the_column_and_keeps_ra_username(admin_user: User):
    store_ra_login(admin_user.id, "alice", TOKEN)

    assert clear_ra_login(admin_user.id) is True

    stored = _user(admin_user.id)
    assert stored.ra_login_sealed is None
    assert stored.ra_username == "alice"
    assert ra_login_for_activate(stored) is None
    assert [e.action for e in recorded_events()] == [
        "user.ra_login_clear",
        "user.ra_login_set",
    ]
    assert recorded_events()[0].data == {}


def test_clearing_nothing_records_nothing(admin_user: User):
    assert clear_ra_login(admin_user.id) is False

    assert recorded_events() == []


def test_an_unknown_user_stores_and_clears_nothing(caplog):
    with caplog.at_level(logging.WARNING, logger="romm"):
        assert store_ra_login(999_999, "alice", TOKEN) is False
        assert clear_ra_login(999_999) is False

    assert TOKEN not in caplog.text
    assert recorded_events() == []


def test_no_stored_login_is_none(admin_user: User):
    assert ra_login_for_activate(_user(admin_user.id)) is None


def test_a_login_sealed_under_another_key_is_none_and_warns(admin_user: User, caplog):
    foreign = (
        Fernet(Fernet.generate_key())
        .encrypt(b'{"username": "alice", "token": "x"}')
        .decode()
    )
    db_user_handler.update_user(admin_user.id, {"ra_login_sealed": foreign})

    with caplog.at_level(logging.WARNING, logger="romm"):
        assert ra_login_for_activate(_user(admin_user.id)) is None

    assert str(admin_user.id) in caplog.text
    assert foreign not in caplog.text


@pytest.mark.parametrize(
    "value",
    [
        {"username": "alice"},
        {"token": TOKEN},
        {"username": "", "token": TOKEN},
        {"username": 1, "token": TOKEN},
    ],
)
def test_a_sealed_value_without_a_usable_login_is_none(admin_user: User, caplog, value):
    db_user_handler.update_user(admin_user.id, {"ra_login_sealed": seal(value)})

    with caplog.at_level(logging.WARNING, logger="romm"):
        assert ra_login_for_activate(_user(admin_user.id)) is None

    assert TOKEN not in caplog.text
