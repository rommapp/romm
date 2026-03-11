import json

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from decorators.auth import protected_route
from endpoints.responses.client_token import (
    ClientTokenAdminSchema,
    ClientTokenCreateSchema,
    ClientTokenPairSchema,
    ClientTokenSchema,
)
from handler.auth import auth_handler
from handler.auth.constants import Scope
from handler.database import db_client_token_handler
from handler.redis_handler import sync_cache
from models.client_token import ClientToken
from utils.client_tokens import (
    build_admin_schema,
    build_create_schema,
    build_schema,
    exchange,
    generate_pair_code,
    parse_expiry,
    validate_scopes,
)
from utils.router import APIRouter

router = APIRouter(
    prefix="/client-tokens",
    tags=["client-tokens"],
)

MAX_TOKENS_PER_USER = 25
PAIR_CODE_TTL_SECONDS = 60


class ClientTokenCreatePayload(BaseModel):
    name: str
    scopes: list[str]
    expires_in: str | None = None


class ClientTokenExchangePayload(BaseModel):
    code: str


@protected_route(router.post, "", [Scope.ME_WRITE], status_code=status.HTTP_201_CREATED)
def create_token(
    request: Request,
    payload: ClientTokenCreatePayload,
) -> ClientTokenCreateSchema:
    user = request.user
    validate_scopes(payload.scopes, user.oauth_scopes)

    count = db_client_token_handler.count_tokens_by_user(user.id)
    if count >= MAX_TOKENS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_TOKENS_PER_USER} tokens per user reached",
        )

    raw_token = auth_handler.generate_client_token()
    hashed = auth_handler.hash_client_token(raw_token)
    expires_at = parse_expiry(payload.expires_in)

    token = ClientToken(
        user_id=user.id,
        name=payload.name,
        hashed_token=hashed,
        scopes=" ".join(payload.scopes),
        expires_at=expires_at,
    )
    token = db_client_token_handler.add_token(token)
    return build_create_schema(token, raw_token)


@protected_route(router.get, "", [Scope.ME_READ])
def list_tokens(request: Request) -> list[ClientTokenSchema]:
    tokens = db_client_token_handler.get_tokens_by_user(request.user.id)
    return [build_schema(t) for t in tokens]


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
    raw_token = auth_handler.generate_client_token()
    new_hash = auth_handler.hash_client_token(raw_token)

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
    return build_create_schema(token, raw_token)


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

    code = generate_pair_code()
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


@router.post("/exchange")
def exchange_pair_code(
    request: Request,
    payload: ClientTokenExchangePayload,
) -> ClientTokenCreateSchema:
    return exchange(request, payload.code)


@protected_route(router.get, "/all", [Scope.USERS_READ])
def list_all_tokens(request: Request) -> list[ClientTokenAdminSchema]:
    tokens = db_client_token_handler.get_all_tokens()
    return [build_admin_schema(t) for t in tokens]


@protected_route(router.delete, "/{token_id}/admin", [Scope.USERS_WRITE])
def admin_delete_token(request: Request, token_id: int) -> None:
    rows = db_client_token_handler.delete_token(token_id=token_id)
    if rows == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
