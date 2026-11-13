"""Auth headers and hidden-entity rows shared by the backend tests."""

from collections.abc import Sequence
from datetime import timedelta

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth.base_handler import oauth_handler
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity
from models.user import User


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def user_headers(user: User, scopes: Sequence[str] | None = None) -> dict[str, str]:
    """Mint a fresh access token for `user`.

    Args:
        scopes: overrides the user's scopes, which are otherwise re-read on each
            call so permission changes made mid-test apply.
    """
    token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(user.oauth_scopes if scopes is None else scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    return bearer(token)


def hide(
    entity: PermEntity,
    entity_id: int,
    *,
    user_id: int | None = None,
    group_id: int | None = None,
) -> None:
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=entity, entity_id=entity_id, user_id=user_id, group_id=group_id
            )
        )
