"""The RetroAchievements login a user's emulator ended with, kept sealed on the user.

A player logs in once, inside the emulator; RomM only stores what the broker
collected and hands it back on the next launch. The token is never logged,
never returned by an API, and never in audit data.
"""

from handler.audit_handler import AuditActor, AuditDraft, AuditTarget, record_many
from handler.database import db_user_handler
from logger.logger import log
from models.audit_event import AuditAction
from models.user import User
from utils.secret_box import UnsealError, seal, unseal


def store_ra_login(user_id: int, username: str, token: str) -> bool:
    """Seal and store the login the user's session ended with.

    `ra_username` is filled in only when it was empty: it also drives the
    progression sync, so a profile that names another account keeps it.
    """
    user = db_user_handler.get_user(user_id)
    if user is None:
        log.warning("ra login: no user %s to store a login for", user_id)
        return False
    data: dict[str, object] = {
        "ra_login_sealed": seal({"username": username, "token": token})
    }
    if not user.ra_username:
        data["ra_username"] = username
    elif user.ra_username != username:
        log.info(
            "ra login: user %s plays as an account other than their profile's",
            user_id,
        )
    db_user_handler.update_user(user_id, data)
    record_many(
        [
            AuditDraft(
                AuditAction.USER_RA_LOGIN_SET,
                AuditActor.for_user_id(user_id),
                AuditTarget.of_user(user),
            )
        ]
    )
    return True


def clear_ra_login(user_id: int) -> bool:
    """Drop the stored login after the user logged out in the emulator; `ra_username` stays."""
    user = db_user_handler.get_user(user_id)
    if user is None:
        log.warning("ra login: no user %s to clear a login for", user_id)
        return False
    if user.ra_login_sealed is None:
        return False
    db_user_handler.update_user(user_id, {"ra_login_sealed": None})
    record_many(
        [
            AuditDraft(
                AuditAction.USER_RA_LOGIN_CLEAR,
                AuditActor.for_user_id(user_id),
                AuditTarget.of_user(user),
            )
        ]
    )
    return True


def ra_login_for_activate(user: User) -> dict[str, str] | None:
    """The login to send on activate, or None when there is none usable.

    An unsealable value (the auth secret changed) or one without a username
    and token starts the player logged out; the next in-emulator login
    overwrites it.
    """
    sealed = getattr(user, "ra_login_sealed", None)
    if not isinstance(sealed, str) or not sealed:
        return None
    try:
        value = unseal(sealed)
    except UnsealError:
        log.warning("ra login: could not unseal the stored login of user %s", user.id)
        return None
    username = value.get("username")
    token = value.get("token")
    if not (
        isinstance(username, str) and username and isinstance(token, str) and token
    ):
        log.warning("ra login: the stored login of user %s is not usable", user.id)
        return None
    return {"username": username, "token": token}
