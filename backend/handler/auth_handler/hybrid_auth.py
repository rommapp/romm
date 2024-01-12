from config import ROMM_AUTH_ENABLED
from fastapi.security.http import HTTPBasic
from handler import authh
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection
from handler import oauthh
from handler.auth_handler import FULL_SCOPES


class HybridAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):
        if not ROMM_AUTH_ENABLED:
            return (AuthCredentials(FULL_SCOPES), None)

        # Check if session key already stored in cache
        user = await authh.get_current_active_user_from_session(conn)
        if user:
            return (AuthCredentials(user.oauth_scopes), user)

        # Check if Authorization header exists
        if "Authorization" not in conn.headers:
            return (AuthCredentials([]), None)

        scheme, token = conn.headers["Authorization"].split()

        # Check if basic auth header is valid
        if scheme.lower() == "basic":
            credentials = await HTTPBasic().__call__(conn)  # type: ignore[arg-type]
            if not credentials:
                return (AuthCredentials([]), None)

            user = authh.authenticate_user(credentials.username, credentials.password)
            if user is None:
                return (AuthCredentials([]), None)

            return (AuthCredentials(user.oauth_scopes), user)

        # Check if bearer auth header is valid
        if scheme.lower() == "bearer":
            user, payload = await oauthh.get_current_active_user_from_bearer_token(token)

            # Only access tokens can request resources
            if payload.get("type") != "access":
                return (AuthCredentials([]), None)

            # Only grant access to resources with overlapping scopes
            token_scopes = set(list(payload.get("scopes").split(" ")))
            overlapping_scopes = list(token_scopes & set(user.oauth_scopes))

            return (AuthCredentials(overlapping_scopes), user)

        return (AuthCredentials([]), None)
