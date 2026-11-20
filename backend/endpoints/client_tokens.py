import json

from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from pydantic import Field

from decorators.auth import protected_route, raise_auth_error
from endpoints.responses.base import BaseModel
from endpoints.responses.client_token import (
    ClientTokenAdminSchema,
    ClientTokenCreateSchema,
    ClientTokenPairSchema,
    ClientTokenSchema,
)
from handler.auth.base_handler import auth_handler
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_admin_for_admin
from handler.database import db_client_token_handler
from handler.redis_handler import sync_cache
from handler.socket_handler import close_client_token_sockets
from models.audit_event import AuditAction
from models.client_token import ClientToken
from utils.auth import request_client_token_id, token_device_id
from utils.client_tokens import (
    PAIR_CODE_TTL_SECONDS,
    build_admin_schema,
    build_create_schema,
    build_schema,
    exchange,
    generate_pair_code,
    parse_expiry,
    record_token_event,
    validate_scopes,
    validate_token_device,
    validate_token_reissue,
    validate_token_within_caller,
)
from utils.router import APIRouter

router = APIRouter(
    prefix="/client-tokens",
    tags=["client-tokens"],
)

MAX_TOKENS_PER_USER = 25


class ClientTokenCreatePayload(BaseModel):
    name: str
    scopes: list[str] = Field(min_length=1)
    expires_in: str | None = None


class ClientTokenExchangePayload(BaseModel):
    code: str


@protected_route(
    router.post,
    "",
    [Scope.ME_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "The caller already has the maximum number of tokens."
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "The caller uses a device-bound token, or requests scopes it does not hold."
        },
    },
)
def create_token(
    request: Request,
    payload: ClientTokenCreatePayload,
) -> ClientTokenCreateSchema:
    """Create a client token. The response contains the token's secret, which cannot be retrieved again."""
    if token_device_id(request) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A device-bound token can't create tokens",
        )
    user = request.user
    validate_scopes(payload.scopes, request.auth.scopes)

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
    record_token_event(request, AuditAction.CLIENT_TOKEN_CREATE, token)
    return build_create_schema(token, raw_token)


@protected_route(router.get, "", [Scope.ME_READ])
def list_tokens(request: Request) -> list[ClientTokenSchema]:
    """List the caller's client tokens."""
    tokens = db_client_token_handler.get_tokens_by_user(request.user.id)
    return [build_schema(t) for t in tokens]


@protected_route(router.delete, "/{token_id}")
async def delete_token(
    request: Request,
    token_id: int,
) -> None:
    """Revoke one of the caller's tokens; a client token can always revoke itself."""
    is_self_revoke = token_id == request_client_token_id(request)
    if not is_self_revoke and Scope.ME_WRITE not in request.auth.scopes:
        raise_auth_error(request)

    token = db_client_token_handler.get_token(
        token_id=token_id, user_id=request.user.id
    )
    if token is not None:
        validate_token_device(request, token)
        validate_token_within_caller(request, token)
    rows = db_client_token_handler.delete_token(
        token_id=token_id, user_id=request.user.id
    )
    if rows == 0 or token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    record_token_event(request, AuditAction.CLIENT_TOKEN_REVOKE, token)
    await close_client_token_sockets([token_id])


@protected_route(router.put, "/{token_id}/regenerate", [Scope.ME_WRITE])
async def regenerate_token(
    request: Request,
    token_id: int,
) -> ClientTokenCreateSchema:
    """Replace a token's secret. The old secret stops working, and the new one is shown only in this response."""
    existing = db_client_token_handler.get_token(
        token_id=token_id, user_id=request.user.id
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    validate_token_device(request, existing)
    validate_token_reissue(request, existing)

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
    record_token_event(request, AuditAction.CLIENT_TOKEN_REGENERATE, token)
    await close_client_token_sockets([token_id])
    return build_create_schema(token, raw_token)


@protected_route(
    router.post,
    "/{token_id}/pair",
    [Scope.ME_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "The token has scopes the caller no longer holds."
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The caller has no token with this ID that it can see."
        },
    },
)
def pair_token(
    request: Request,
    token_id: int,
) -> ClientTokenPairSchema:
    """Create a single-use pairing code for a token. `expires_in` is the number of seconds the code stays valid."""
    token = db_client_token_handler.get_token(
        token_id=token_id, user_id=request.user.id
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    validate_token_device(request, token)
    validate_token_reissue(request, token)

    code = generate_pair_code()
    redis_key = f"pair:{code}"
    sync_cache.set(
        redis_key,
        json.dumps({"token_id": token_id, "user_id": request.user.id}),
        ex=PAIR_CODE_TTL_SECONDS,
    )
    return ClientTokenPairSchema(code=code, expires_in=PAIR_CODE_TTL_SECONDS)


@router.get(
    "/pair/{code}/status",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The code is unknown or has expired."
        }
    },
)
def pair_status(
    code: str = PathVar(
        description="The pairing code. Dashes and letter case are ignored."
    ),
) -> None:
    """Check whether a pairing code is valid."""
    normalized = code.replace("-", "").upper()
    redis_key = f"pair:{normalized}"
    if not sync_cache.exists(redis_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/exchange",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "The token's owner is disabled."},
        status.HTTP_404_NOT_FOUND: {
            "description": (
                "The code is unknown, expired or already used, or its token no"
                " longer exists."
            )
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Too many exchange attempts from this IP address."
        },
    },
)
async def exchange_pair_code(
    request: Request,
    payload: ClientTokenExchangePayload,
) -> ClientTokenCreateSchema:
    """Exchange a single-use pairing code for a new secret for the token it was created for. The token's previous secret stops working."""
    token = exchange(request, payload.code)
    await close_client_token_sockets([token.id])
    return token


@protected_route(router.get, "/all", [Scope.USERS_READ])
def list_all_tokens(request: Request) -> list[ClientTokenAdminSchema]:
    """List every user's client tokens."""
    tokens = db_client_token_handler.get_all_tokens()
    return [build_admin_schema(t) for t in tokens]


@protected_route(
    router.delete,
    "/{token_id}/admin",
    [Scope.USERS_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "The token belongs to an admin, and the caller is not one."
        },
        status.HTTP_404_NOT_FOUND: {"description": "No token has this ID."},
    },
)
async def admin_delete_token(
    request: Request,
    token_id: int,
) -> None:
    """Revoke any user's client token."""
    token = db_client_token_handler.get_token(token_id=token_id)
    if token is not None:
        assert_admin_for_admin(
            request, token.user.role, "Only an administrator can revoke admin tokens"
        )
    rows = db_client_token_handler.delete_token(token_id=token_id)
    if rows == 0 or token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    record_token_event(request, AuditAction.CLIENT_TOKEN_REVOKE, token)
    await close_client_token_sockets([token_id])
