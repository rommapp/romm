"""The RetroAchievements login a user's emulator ended with, kept sealed on the user."""

from handler.audit_handler import AuditActor, AuditTarget, record
from handler.database import db_user_handler
from logger.logger import log
from models.audit_event import AuditAction
from models.user import User
from utils.secret_box import UnsealError, seal, unseal


def store_ra_login(user_id: int, username: str, token: str) -> bool:
    """Seal and store the login the user's session ended with, filling only an empty `ra_username`."""
    user = db_user_handler.get_user(user_id)
    if user is None:
        log.warning("no user %s to store a RetroAchievements login for", user_id)
        return False
    db_user_handler.update_user(
        user_id, {"ra_login_sealed": seal({"username": username, "token": token})}
    )
    actor = AuditActor.for_user(user)
    record(AuditAction.USER_RA_LOGIN_SET, actor, AuditTarget.of_user(user))
    # Conditional, so a profile edit or another exit that got there first wins.
    if db_user_handler.fill_empty_ra_username(user_id, username):
        record(
            AuditAction.USER_EDIT,
            actor,
            AuditTarget.of_user(user),
            {"changed": ["ra_username"]},
        )
    elif user.ra_username and user.ra_username != username:
        log.info(
            "user %s plays RetroAchievements as an account other than their profile's",
            user_id,
        )
    return True


def clear_ra_login(user_id: int) -> bool:
    """Drop the stored login after the user logged out in the emulator; `ra_username` stays."""
    user = db_user_handler.get_user(user_id)
    if user is None:
        log.warning("no user %s to clear a RetroAchievements login for", user_id)
        return False
    # Compare-and-clear, so a login another exit stored since the read survives.
    if user.ra_login_sealed is None or not db_user_handler.clear_ra_login_sealed(
        user_id, user.ra_login_sealed
    ):
        return False
    record(
        AuditAction.USER_RA_LOGIN_CLEAR,
        AuditActor.for_user(user),
        AuditTarget.of_user(user),
    )
    return True


def ra_login_for_activate(user: User) -> dict[str, str] | None:
    """The login to send on activate, or None when there is none usable."""
    if not user.ra_login_sealed:
        return None
    try:
        value = unseal(user.ra_login_sealed)
    except UnsealError:
        log.warning(
            "could not unseal the stored RetroAchievements login of user %s", user.id
        )
        return None
    login = usable_login(value)
    if login is None:
        log.warning(
            "the stored RetroAchievements login of user %s is not usable", user.id
        )
    return login


def usable_login(value: object) -> dict[str, str] | None:
    """`value` as a login, or None unless its username and token are non-empty strings."""
    if not isinstance(value, dict):
        return None
    username = value.get("username")
    token = value.get("token")
    if not (
        isinstance(username, str) and username and isinstance(token, str) and token
    ):
        return None
    return {"username": username, "token": token}


def drop_ra_login_not_for(user_id: int, ra_username: str) -> bool:
    """Drop the stored login unless it is for `ra_username`; RA names ignore case."""
    user = db_user_handler.get_user(user_id)
    if user is None or user.ra_login_sealed is None:
        return False
    login = ra_login_for_activate(user)
    if login is not None and login["username"].casefold() == ra_username.casefold():
        return False
    # Only the value judged here, so a login stored since then survives.
    return db_user_handler.clear_ra_login_sealed(user_id, user.ra_login_sealed)
