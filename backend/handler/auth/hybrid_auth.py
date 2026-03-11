from datetime import datetime, timezone

from fastapi.security.http import HTTPBasic
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection

from config import KIOSK_MODE
from handler.auth import auth_handler, oauth_handler
from handler.database import db_client_token_handler, db_user_handler
from models.user import User
from utils.datetime import to_utc

from .constants import READ_SCOPES


class HybridAuthBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, User] | None:
        # Check if session key already stored in cache
        user = await auth_handler.get_current_active_user_from_session(conn)
        if user:
            user.set_last_active()
            return (AuthCredentials(user.oauth_scopes), user)

        # Check if Authorization header exists
        if "Authorization" in conn.headers:
            scheme, token = conn.headers["Authorization"].split()

            # Check if basic auth header is valid
            if scheme.lower() == "basic":
                credentials = await HTTPBasic().__call__(conn)  # type: ignore[arg-type]
                if not credentials:
                    return None

                user = auth_handler.authenticate_user(
                    credentials.username, credentials.password
                )
                if user is None or not user.enabled:
                    return None

                user.set_last_active()
                return (AuthCredentials(user.oauth_scopes), user)

            # Check if bearer auth header is valid
            if scheme.lower() == "bearer":
                # Client API tokens use the rmm_ prefix
                if token.startswith("rmm_"):
                    hashed = auth_handler.hash_client_token(token)
                    client_token = db_client_token_handler.get_token_by_hash(hashed)
                    if client_token is None:
                        return None

                    if client_token.expires_at and to_utc(
                        client_token.expires_at
                    ) < datetime.now(timezone.utc):
                        return None

                    user = db_user_handler.get_user(client_token.user_id)
                    if user is None or not user.enabled:
                        return None

                    token_scopes = set(client_token.scopes.split())
                    effective_scopes = list(token_scopes & set(user.oauth_scopes))

                    db_client_token_handler.update_last_used(client_token.id)
                    user.set_last_active()
                    conn.state.client_token_id = client_token.id
                    return (AuthCredentials(effective_scopes), user)

                # OAuth JWT bearer tokens
                (
                    user,
                    claims,
                ) = await oauth_handler.get_current_active_user_from_bearer_token(token)

                if user is None or claims is None:
                    return None

                # Only access tokens can request resources
                if claims.get("type") != "access":
                    return None

                # Only grant access to resources with overlapping scopes
                token_scopes = set(list(claims.get("scopes", "").split(" ")))
                overlapping_scopes = list(token_scopes & set(user.oauth_scopes))

                user.set_last_active()
                return (AuthCredentials(overlapping_scopes), user)

        # Check if we're in KIOSK_MODE
        if KIOSK_MODE:
            user = User.kiosk_mode_user()
            return (AuthCredentials(READ_SCOPES), user)

        return None
