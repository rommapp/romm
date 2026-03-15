import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status

from endpoints.responses.client_token import (
    ClientTokenAdminSchema,
    ClientTokenCreateSchema,
    ClientTokenSchema,
)
from handler.auth import auth_handler
from handler.auth.constants import Scope
from handler.database import db_client_token_handler, db_user_handler
from handler.redis_handler import sync_cache
from models.client_token import ClientToken

PAIR_CODE_LENGTH = 8
PAIR_CODE_TTL_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60
PAIR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

EXPIRY_MAP = {
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "1y": timedelta(days=365),
}


def generate_pair_code() -> str:
    return "".join(secrets.choice(PAIR_ALPHABET) for _ in range(PAIR_CODE_LENGTH))


def parse_expiry(expires_in: str | None) -> datetime | None:
    if expires_in is None or expires_in == "never":
        return None
    delta = EXPIRY_MAP.get(expires_in)
    if delta is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid expires_in value: {expires_in}. "
            f"Valid values: {', '.join(EXPIRY_MAP.keys())}, never",
        )
    return datetime.now(timezone.utc) + delta


def validate_scopes(requested: list[str], user_scopes: list[Scope]) -> None:
    user_scope_values = {str(s) for s in user_scopes}
    invalid = set(requested) - user_scope_values
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requested scopes exceed your permissions: "
            f"{', '.join(sorted(invalid))}",
        )


def check_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"client-token-rate:{client_ip}"
    pipe = sync_cache.pipeline()
    pipe.incr(rate_key)
    pipe.expire(rate_key, RATE_LIMIT_WINDOW_SECONDS)
    count, _ = pipe.execute()
    if count > RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many exchange attempts. Try again later.",
        )


def build_create_schema(token: ClientToken, raw_token: str) -> ClientTokenCreateSchema:
    return ClientTokenCreateSchema(
        id=token.id,
        name=token.name,
        scopes=token.scopes.split(),
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        user_id=token.user_id,
        raw_token=raw_token,
    )


def build_schema(token: ClientToken) -> ClientTokenSchema:
    return ClientTokenSchema(
        id=token.id,
        name=token.name,
        scopes=token.scopes.split(),
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        user_id=token.user_id,
    )


def build_admin_schema(token: ClientToken) -> ClientTokenAdminSchema:
    return ClientTokenAdminSchema(
        id=token.id,
        name=token.name,
        scopes=token.scopes.split(),
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        user_id=token.user_id,
        username=token.user.username,
    )


def exchange(request: Request, code: str) -> ClientTokenCreateSchema:
    check_rate_limit(request)

    normalized = code.replace("-", "").upper()
    redis_key = f"pair:{normalized}"
    data = sync_cache.getdel(redis_key)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired pairing code",
        )
    params = json.loads(data)

    user = db_user_handler.get_user(params["user_id"])
    if user is None or not user.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token owner is disabled",
        )

    raw_token = auth_handler.generate_client_token()
    new_hash = auth_handler.hash_client_token(raw_token)

    token = db_client_token_handler.update_hashed_token(
        token_id=params["token_id"],
        new_hash=new_hash,
        user_id=params["user_id"],
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token no longer exists",
        )

    return build_create_schema(token, raw_token)
