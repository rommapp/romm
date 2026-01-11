from datetime import datetime, timedelta, timezone
from typing import Final
from uuid import uuid4

from fastapi import Request

from decorators.auth import protected_route
from endpoints.responses.sfu import SFUTokenResponse
from handler.auth import oauth_handler
from handler.auth.constants import Scope
from handler.redis_handler import sync_cache
from utils.router import APIRouter

# Declarations to configure JWT tokens for SFU authentication.
SFU_TOKEN_TTL_SECONDS: Final[int] = 30
SFU_TOKEN_ISSUER: Final[str] = "romm:sfu"
SFU_JTI_REDIS_KEY_PREFIX: Final[str] = "sfu:auth:jti:"

router = APIRouter(tags=["sfu"])

# Helper to extract netplay username from various possible ui_settings formats.
# User is autheticated with JWT token, and a unique netplay username (for this site) is made available to netplay.
def _get_netplay_username_from_ui_settings(ui_settings: dict | None) -> str | None:
    if not ui_settings:
        return None

    candidates = (
        ui_settings.get("netplay_username"),
        ui_settings.get("netplayUsername"),
        ui_settings.get("settings.netplayUsername"),
        ui_settings.get("settings.netplay_username"),
    )

    for candidate in candidates:
        if isinstance(candidate, str):
            value = candidate.strip()
            if value:
                return value

    return None

# Endpoint to mint SFU authentication tokens.
@protected_route(router.post, "/sfu/token", [Scope.ME_READ])
def mint_sfu_token(request: Request) -> SFUTokenResponse:
    user = request.user

    now = datetime.now(timezone.utc)
    expires_delta = timedelta(seconds=SFU_TOKEN_TTL_SECONDS)
    exp = now + expires_delta
    jti = uuid4().hex

    netplay_username = _get_netplay_username_from_ui_settings(getattr(user, "ui_settings", None))

    token = oauth_handler.create_oauth_token(
        data={
            "sub": user.username,
            "iss": SFU_TOKEN_ISSUER,
            "type": "sfu",
            "jti": jti,
            "iat": int(now.timestamp()),
        },
        expires_delta=expires_delta,
    )

    key = f"{SFU_JTI_REDIS_KEY_PREFIX}{jti}"
    payload: dict[str, str] = {
        "sub": user.username,
        "iss": SFU_TOKEN_ISSUER,
        "jti": jti,
        "iat": str(int(now.timestamp())),
        "exp": str(int(exp.timestamp())),
    }
    if netplay_username:
        payload["netplay_username"] = netplay_username

    with sync_cache.pipeline() as pipe:
        pipe.hset(key, mapping=payload)
        pipe.expire(key, SFU_TOKEN_TTL_SECONDS)
        pipe.execute()

    return {
        "token": token,
        "token_type": "bearer",
        "expires": SFU_TOKEN_TTL_SECONDS,
    }
