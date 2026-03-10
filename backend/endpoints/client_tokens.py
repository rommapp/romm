import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from decorators.auth import protected_route
from endpoints.responses.client_token import (
    ClientTokenAdminSchema,
    ClientTokenCreateSchema,
    ClientTokenPairSchema,
    ClientTokenSchema,
)
from handler.auth.base_handler import generate_client_token, hash_client_token
from handler.auth.constants import Scope
from handler.database import db_client_token_handler, db_user_handler
from handler.redis_handler import sync_cache
from models.client_token import ClientToken
from utils.router import APIRouter

router = APIRouter(
    prefix="/client-tokens",
    tags=["client-tokens"],
)

MAX_TOKENS_PER_USER = 25
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


class ClientTokenCreatePayload(BaseModel):
    name: str
    scopes: list[str]
    expires_in: str | None = None


class ClientTokenExchangePayload(BaseModel):
    code: str


def _generate_pair_code() -> str:
    return "".join(secrets.choice(PAIR_ALPHABET) for _ in range(PAIR_CODE_LENGTH))


def _parse_expiry(expires_in: str | None) -> datetime | None:
    if expires_in is None or expires_in == "never":
        return None
    delta = EXPIRY_MAP.get(expires_in)
    if delta is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid expires_in value: {expires_in}. "
            f"Valid values: {', '.join(EXPIRY_MAP.keys())}, never",
        )
    return datetime.now(timezone.utc) + delta


def _validate_scopes(requested: list[str], user_scopes: list[Scope]) -> None:
    user_scope_values = {str(s) for s in user_scopes}
    invalid = set(requested) - user_scope_values
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requested scopes exceed your permissions: "
            f"{', '.join(sorted(invalid))}",
        )


def _check_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"client-token-rate:{client_ip}"
    current = sync_cache.get(rate_key)
    if current and int(current) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many exchange attempts. Try again later.",
        )
    pipe = sync_cache.pipeline()
    pipe.incr(rate_key)
    pipe.expire(rate_key, RATE_LIMIT_WINDOW_SECONDS)
    pipe.execute()


def _build_create_schema(token: ClientToken, raw_token: str) -> ClientTokenCreateSchema:
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


def _build_schema(token: ClientToken) -> ClientTokenSchema:
    return ClientTokenSchema(
        id=token.id,
        name=token.name,
        scopes=token.scopes.split(),
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        user_id=token.user_id,
    )


def _build_admin_schema(token: ClientToken) -> ClientTokenAdminSchema:
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


@protected_route(router.post, "", [Scope.ME_WRITE], status_code=status.HTTP_201_CREATED)
def create_token(
    request: Request,
    payload: ClientTokenCreatePayload,
) -> ClientTokenCreateSchema:
    user = request.user
    _validate_scopes(payload.scopes, user.oauth_scopes)

    count = db_client_token_handler.count_tokens_by_user(user.id)
    if count >= MAX_TOKENS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_TOKENS_PER_USER} tokens per user reached",
        )

    raw_token = generate_client_token()
    hashed = hash_client_token(raw_token)
    expires_at = _parse_expiry(payload.expires_in)

    token = ClientToken(
        user_id=user.id,
        name=payload.name,
        hashed_token=hashed,
        scopes=" ".join(payload.scopes),
        expires_at=expires_at,
    )
    token = db_client_token_handler.add_token(token)
    return _build_create_schema(token, raw_token)


@protected_route(router.get, "", [Scope.ME_READ])
def list_tokens(request: Request) -> list[ClientTokenSchema]:
    tokens = db_client_token_handler.get_tokens_by_user(request.user.id)
    return [_build_schema(t) for t in tokens]


@protected_route(router.delete, "/{token_id}", [Scope.ME_WRITE])
def delete_token(request: Request, token_id: int) -> None:
    rows = db_client_token_handler.delete_token(
        token_id=token_id, user_id=request.user.id
    )
    if rows == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )


@protected_route(router.put, "/{token_id}/regenerate", [Scope.ME_WRITE])
def regenerate_token(request: Request, token_id: int) -> ClientTokenCreateSchema:
    raw_token = generate_client_token()
    new_hash = hash_client_token(raw_token)

    token = db_client_token_handler.update_hashed_token(
        token_id=token_id,
        new_hash=new_hash,
        user_id=request.user.id,
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    return _build_create_schema(token, raw_token)


@protected_route(router.post, "/{token_id}/pair", [Scope.ME_WRITE])
def pair_token(request: Request, token_id: int) -> ClientTokenPairSchema:
    token = db_client_token_handler.get_token(
        token_id=token_id, user_id=request.user.id
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )

    code = _generate_pair_code()
    redis_key = f"pair:{code}"
    sync_cache.setex(
        redis_key,
        PAIR_CODE_TTL_SECONDS,
        json.dumps({"token_id": token_id, "user_id": request.user.id}),
    )
    return ClientTokenPairSchema(code=code, expires_in=PAIR_CODE_TTL_SECONDS)


@router.get(
    "/pair/{code}/status",
    status_code=status.HTTP_200_OK,
)
def pair_status(code: str) -> None:
    normalized = code.replace("-", "").upper()
    redis_key = f"pair:{normalized}"
    if not sync_cache.exists(redis_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def _exchange(request: Request, code: str) -> ClientTokenCreateSchema:
    _check_rate_limit(request)

    normalized = code.replace("-", "").upper()
    redis_key = f"pair:{normalized}"
    data = sync_cache.get(redis_key)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired pairing code",
        )

    sync_cache.delete(redis_key)
    params = json.loads(data)

    user = db_user_handler.get_user(params["user_id"])
    if user is None or not user.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token owner is disabled",
        )

    raw_token = generate_client_token()
    new_hash = hash_client_token(raw_token)

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

    return _build_create_schema(token, raw_token)


@router.post("/exchange")
def exchange_pair_code(
    request: Request,
    payload: ClientTokenExchangePayload,
) -> ClientTokenCreateSchema:
    return _exchange(request, payload.code)


@protected_route(router.get, "/all", [Scope.USERS_READ])
def list_all_tokens(request: Request) -> list[ClientTokenAdminSchema]:
    tokens = db_client_token_handler.get_all_tokens()
    return [_build_admin_schema(t) for t in tokens]


@protected_route(router.delete, "/{token_id}/admin", [Scope.USERS_WRITE])
def admin_delete_token(request: Request, token_id: int) -> None:
    rows = db_client_token_handler.delete_token(token_id=token_id)
    if rows == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
