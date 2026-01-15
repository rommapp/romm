import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Final
from uuid import uuid4

from fastapi import Body, HTTPException, Request, status
from joserfc import jwt
from joserfc.errors import BadSignatureError, DecodeError

from config import ROMM_AUTH_SECRET_KEY, ROMM_SFU_INTERNAL_SECRET
from decorators.auth import protected_route
from endpoints.responses.base import BaseModel
from endpoints.responses.sfu import SFUTokenResponse
from handler.auth import oauth_handler
from handler.auth.base_handler import oct_key
from handler.auth.constants import Scope
from handler.redis_handler import sync_cache
from utils.router import APIRouter

# Declarations to configure JWT tokens for SFU authentication.
SFU_TOKEN_TTL_SECONDS: Final[int] = 30  # Write token TTL (deprecated, use SFU_WRITE_TOKEN_TTL_SECONDS)
SFU_READ_TOKEN_TTL_SECONDS: Final[int] = 900  # 15 minutes for read tokens
SFU_WRITE_TOKEN_TTL_SECONDS: Final[int] = 30  # 30 seconds for write tokens
SFU_TOKEN_ISSUER: Final[str] = "romm:sfu"
SFU_JTI_REDIS_KEY_PREFIX: Final[str] = "sfu:auth:jti:"
SFU_TOKEN_CLOCK_SKEW_SECONDS: Final[int] = 5

# Room registry for multi-node SFU deployments.
SFU_ROOM_REDIS_KEY_PREFIX: Final[str] = "sfu:room:"
SFU_ROOM_TTL_SECONDS: Final[int] = 60

router = APIRouter(tags=["sfu"])


def _decode_redis_hash(data: dict[Any, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (data or {}).items():
        kk = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
        vv = v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
        out[kk] = vv
    return out


def _require_sfu_internal_secret(request: Request) -> None:
    """Authenticate SFU->RomM calls using ROMM_SFU_INTERNAL_SECRET.

    This endpoint is for server-to-server calls only.
    SECURITY: Never reuse or transmit ROMM_AUTH_SECRET_KEY (JWT signing key) here.
    """
    expected = (ROMM_SFU_INTERNAL_SECRET or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SFU internal secret not configured",
        )

    provided = request.headers.get("x-romm-sfu-secret")
    if not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )


def _decode_and_validate_sfu_jwt(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, oct_key, algorithms=["HS256"])
    except (BadSignatureError, DecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        ) from exc

    claims: dict[str, Any] = dict(payload.claims)

    # Validate time-based claims with small clock skew.
    now = int(time.time())
    skew = SFU_TOKEN_CLOCK_SKEW_SECONDS
    if "nbf" in claims and claims.get("nbf") is not None:
        try:
            nbf = int(claims["nbf"])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=401, detail="invalid nbf") from exc
        if now + skew < nbf:
            raise HTTPException(status_code=401, detail="jwt not active")

    if "exp" not in claims or claims.get("exp") is None:
        raise HTTPException(status_code=401, detail="missing exp")
    try:
        exp = int(claims["exp"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="invalid exp") from exc
    if now - skew >= exp:
        raise HTTPException(status_code=401, detail="jwt expired")

    if claims.get("iss") != SFU_TOKEN_ISSUER:
        raise HTTPException(status_code=401, detail="invalid issuer")
    # Support both old "sfu" type and new "sfu:read"/"sfu:write" types
    token_type = claims.get("type")
    if token_type not in ("sfu", "sfu:read", "sfu:write"):
        raise HTTPException(status_code=401, detail="invalid token type")
    if not claims.get("sub") or not isinstance(claims.get("sub"), str):
        raise HTTPException(status_code=401, detail="missing sub")
    # JTI is only required for write tokens (which need Redis lookup)
    # Read tokens don't need JTI since they're validated by signature only
    if token_type == "sfu:write" or token_type == "sfu":
        if not claims.get("jti") or not isinstance(claims.get("jti"), str):
            raise HTTPException(status_code=401, detail="missing jti")
    return claims


class SFUVerifyRequest(BaseModel):
    token: str
    consume: bool = True


class SFUVerifyResponse(BaseModel):
    sub: str
    netplay_username: str | None = None


@router.post("/sfu/internal/verify", response_model=SFUVerifyResponse)
def sfu_internal_verify(request: Request, body: SFUVerifyRequest) -> SFUVerifyResponse:
    # This endpoint is for SFU servers only.
    _require_sfu_internal_secret(request)

    claims = _decode_and_validate_sfu_jwt(body.token)
    token_type = claims.get("type", "sfu")
    sub = str(claims["sub"])

    # Read tokens (sfu:read) don't need Redis lookup - validated by JWT signature only
    if token_type == "sfu:read":
        # For read tokens, we can extract netplay_username from user settings if needed
        # For now, return without netplay_username for read tokens
        return SFUVerifyResponse(sub=sub, netplay_username=None)

    # Write tokens (sfu:write) and legacy tokens (sfu) require Redis lookup
    jti = str(claims.get("jti", ""))
    if not jti:
        raise HTTPException(status_code=401, detail="missing jti for write token")

    allow_key = f"{SFU_JTI_REDIS_KEY_PREFIX}{jti}"
    data = _decode_redis_hash(sync_cache.hgetall(allow_key))
    if not data:
        raise HTTPException(status_code=401, detail="token not allowlisted")

    # Optional one-time consumption marker.
    if body.consume:
        used_key = f"{SFU_JTI_REDIS_KEY_PREFIX}used:{jti}"
        if not sync_cache.setnx(used_key, "1"):
            raise HTTPException(status_code=401, detail="token already used")
        ttl = sync_cache.ttl(allow_key)
        if isinstance(ttl, int) and ttl > 0:
            sync_cache.expire(used_key, ttl)

    # Record must match the claims.
    if data.get("sub") != sub:
        raise HTTPException(status_code=401, detail="sub mismatch")
    if data.get("iss") != SFU_TOKEN_ISSUER:
        raise HTTPException(status_code=401, detail="iss mismatch")
    if data.get("jti") != jti:
        raise HTTPException(status_code=401, detail="jti mismatch")

    return SFUVerifyResponse(sub=sub, netplay_username=data.get("netplay_username"))


class SFURoomRecord(BaseModel):
    room_name: str
    current: int = 0
    max: int = 0
    hasPassword: bool = False
    nodeId: str | None = None
    url: str | None = None
    updatedAt: int | None = None


def _room_key(room_name: str) -> str:
    return f"{SFU_ROOM_REDIS_KEY_PREFIX}{room_name}"


@router.post("/sfu/internal/rooms/upsert")
def sfu_internal_rooms_upsert(request: Request, body: SFURoomRecord) -> dict[str, bool]:
    _require_sfu_internal_secret(request)
    room_name = (body.room_name or "").strip()
    if not room_name:
        raise HTTPException(status_code=400, detail="missing room_name")

    payload = body.model_dump()
    payload["room_name"] = room_name
    payload["updatedAt"] = int(time.time() * 1000)

    with sync_cache.pipeline() as pipe:
        pipe.set(_room_key(room_name), json.dumps(payload), ex=SFU_ROOM_TTL_SECONDS)
        pipe.execute()
    return {"ok": True}


class SFURoomDeleteRequest(BaseModel):
    room_name: str


@router.post("/sfu/internal/rooms/delete")
def sfu_internal_rooms_delete(request: Request, body: SFURoomDeleteRequest) -> dict[str, bool]:
    _require_sfu_internal_secret(request)
    room_name = (body.room_name or "").strip()
    if not room_name:
        raise HTTPException(status_code=400, detail="missing room_name")
    sync_cache.delete(_room_key(room_name))
    return {"ok": True}


@router.get("/sfu/internal/rooms/resolve", response_model=SFURoomRecord)
def sfu_internal_rooms_resolve(request: Request, room: str) -> SFURoomRecord:
    _require_sfu_internal_secret(request)
    room_name = (room or "").strip()
    if not room_name:
        raise HTTPException(status_code=400, detail="missing room")
    raw = sync_cache.get(_room_key(room_name))
    if not raw:
        raise HTTPException(status_code=404, detail="not found")
    try:
        parsed = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="invalid room record") from exc
    return SFURoomRecord(**parsed)


@router.get("/sfu/internal/rooms/list")
def sfu_internal_rooms_list(request: Request) -> dict[str, Any]:
    _require_sfu_internal_secret(request)

    out: dict[str, Any] = {}
    cursor = 0
    match = f"{SFU_ROOM_REDIS_KEY_PREFIX}*"
    while True:
        cursor, keys = sync_cache.scan(cursor=cursor, match=match, count=200)
        if keys:
            values = sync_cache.mget(keys)
            for k, raw in zip(keys, values):
                if not raw:
                    continue
                try:
                    parsed = json.loads(
                        raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
                    )
                except Exception:
                    continue

                room_name = parsed.get("room_name")
                if not room_name:
                    # Fallback: derive from key name.
                    kk = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
                    room_name = kk[len(SFU_ROOM_REDIS_KEY_PREFIX) :]
                out[str(room_name)] = {
                    "room_name": room_name,
                    "current": parsed.get("current", 0),
                    "max": parsed.get("max", 0),
                    "hasPassword": bool(parsed.get("hasPassword")),
                    "nodeId": parsed.get("nodeId"),
                    "url": parsed.get("url"),
                }
        if int(cursor) == 0:
            break

    return out

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
def mint_sfu_token(
    request: Request,
    token_type: str = Body("read", embed=True)
) -> SFUTokenResponse:
    """Mint SFU authentication tokens.
    
    Args:
        request: FastAPI request object
        token_type: "read" for room listings (15min), "write" for creating/joining rooms (30s)
    
    Returns:
        SFUTokenResponse with token, token_type, and expires
    """
    user = request.user

    # Validate token_type parameter
    if token_type not in ("read", "write"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token_type must be 'read' or 'write'"
        )

    now = datetime.now(timezone.utc)
    
    # Set expiry based on token type
    if token_type == "read":
        expires_delta = timedelta(seconds=SFU_READ_TOKEN_TTL_SECONDS)
        token_type_claim = "sfu:read"
        expires_seconds = SFU_READ_TOKEN_TTL_SECONDS
    else:  # write
        expires_delta = timedelta(seconds=SFU_WRITE_TOKEN_TTL_SECONDS)
        token_type_claim = "sfu:write"
        expires_seconds = SFU_WRITE_TOKEN_TTL_SECONDS
    
    exp = now + expires_delta
    jti = uuid4().hex

    netplay_username = _get_netplay_username_from_ui_settings(getattr(user, "ui_settings", None))

    # Build token claims
    token_data = {
        "sub": user.username,
        "iss": SFU_TOKEN_ISSUER,
        "type": token_type_claim,
        "iat": int(now.timestamp()),
    }
    
    # Only include JTI for write tokens (read tokens don't need Redis lookup)
    if token_type == "write":
        token_data["jti"] = jti

    token = oauth_handler.create_oauth_token(
        data=token_data,
        expires_delta=expires_delta,
    )

    # Only store write tokens in Redis
    if token_type == "write":
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

        # Store with value 0 (unused), will be set to 1 when consumed
        with sync_cache.pipeline() as pipe:
            pipe.hset(key, mapping=payload)
            pipe.expire(key, SFU_WRITE_TOKEN_TTL_SECONDS)
            pipe.execute()

    return {
        "token": token,
        "token_type": "bearer",
        "expires": expires_seconds,
    }
