import logging

import pytest
from cryptography.fernet import Fernet
from tests.audit_events import recorded_events

from handler.database import db_user_handler
from handler.ra_login import (
    clear_ra_login,
    drop_ra_login_not_for,
    ra_login_for_activate,
    store_ra_login,
)
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

    [event] = [e for e in recorded_events() if e.action == "user.ra_login_set"]
    assert event.actor_id == admin_user.id
    assert event.target_id == str(admin_user.id)
    assert event.data == {}


def test_filling_ra_username_records_an_edit_naming_only_the_field(
    admin_user: User,
):
    store_ra_login(admin_user.id, "alice", TOKEN)

    [event] = [e for e in recorded_events() if e.action == "user.edit"]
    assert event.actor_id == admin_user.id
    assert event.target_id == str(admin_user.id)
    assert event.data == {"changed": ["ra_username"]}


def test_a_kept_ra_username_records_no_edit(admin_user: User):
    db_user_handler.update_user(admin_user.id, {"ra_username": "profile-name"})

    store_ra_login(admin_user.id, "alice", TOKEN)

    assert [e.action for e in recorded_events()] == ["user.ra_login_set"]


def test_an_ra_username_set_after_the_read_is_not_overwritten(
    admin_user: User, monkeypatch: pytest.MonkeyPatch
):
    """Another exit or a profile edit can fill it between the read and the write."""
    stale = _user(admin_user.id)
    db_user_handler.update_user(admin_user.id, {"ra_username": "first"})
    monkeypatch.setattr(db_user_handler, "get_user", lambda _id: stale)

    store_ra_login(admin_user.id, "alice", TOKEN)

    monkeypatch.undo()
    assert _user(admin_user.id).ra_username == "first"
    assert "user.edit" not in [e.action for e in recorded_events()]


def test_clearing_nulls_the_column_and_keeps_ra_username(admin_user: User):
    store_ra_login(admin_user.id, "alice", TOKEN)

    assert clear_ra_login(admin_user.id) is True

    stored = _user(admin_user.id)
    assert stored.ra_login_sealed is None
    assert stored.ra_username == "alice"
    assert ra_login_for_activate(stored) is None
    assert [
        e.action for e in recorded_events() if e.action.startswith("user.ra_login")
    ] == [
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


def test_dropping_for_another_account_clears_the_login(admin_user: User):
    store_ra_login(admin_user.id, "alice", TOKEN)

    assert drop_ra_login_not_for(admin_user.id, "bob") is True

    assert _user(admin_user.id).ra_login_sealed is None


def test_dropping_for_the_logins_own_account_keeps_it(admin_user: User):
    store_ra_login(admin_user.id, "Alice", TOKEN)

    assert drop_ra_login_not_for(admin_user.id, "alice") is False

    assert ra_login_for_activate(_user(admin_user.id)) == {
        "username": "Alice",
        "token": TOKEN,
    }


def test_dropping_keeps_a_login_stored_after_the_read(
    admin_user: User, monkeypatch: pytest.MonkeyPatch
):
    """An exit can store a login for the new name between the read and the clear."""
    store_ra_login(admin_user.id, "alice", TOKEN)
    stale = _user(admin_user.id)
    store_ra_login(admin_user.id, "bob", "fresh-token")
    monkeypatch.setattr(db_user_handler, "get_user", lambda _id: stale)

    assert drop_ra_login_not_for(admin_user.id, "bob") is False

    monkeypatch.undo()
    assert ra_login_for_activate(_user(admin_user.id)) == {
        "username": "bob",
        "token": "fresh-token",
    }
