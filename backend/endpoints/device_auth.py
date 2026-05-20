"""Device authorization flow endpoints (RFC 8628-style, tailored for RomM).

A device POSTs to /authorize with its metadata and requested scopes; the server
returns a device_code (secret, for polling) and a user_code (short, for QR).
The user scans the QR on their phone, lands on /pair/device in the web UI,
approves (possibly editing scopes and device name), and the device's next poll
on /token returns a ClientToken bound 1:1 to a Device record.

The flow is unauthenticated on /authorize and /token (the whole point — the
device has no credentials yet). State lives exclusively in Redis with a hard
10-minute TTL ceiling.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from decorators.auth import protected_route
from endpoints.responses.device_auth import (
    DeviceAuthApprovePayload,
    DeviceAuthApproveResponse,
    DeviceAuthDenyPayload,
    DeviceAuthInitPayload,
    DeviceAuthInitResponse,
    DeviceAuthPendingSchema,
    DeviceAuthTokenPayload,
    DeviceAuthTokenResponse,
)
from handler.auth import auth_handler
from handler.auth.constants import Scope
from handler.database import db_client_token_handler, db_device_handler
from logger.logger import log
from models.client_token import ClientToken
from models.device import Device, SyncMode
from utils.client_tokens import parse_expiry
from utils.device_auth import (
    PENDING_TTL_SECONDS,
    POLL_DEFAULT_INTERVAL_SECONDS,
    FlowStatus,
    build_verification_urls,
    check_authorize_rate_limit,
    check_token_poll_rate_limit,
    consume_approved,
    generate_device_code,
    generate_user_code,
    load_pending,
    mark_approved,
    mark_denied,
    normalize_user_code,
    pending_expires_at,
    polled_too_fast,
    resolve_device_code_from_user_code,
    store_pending,
)
from utils.router import APIRouter

router = APIRouter(prefix="/auth/device", tags=["device-auth"])


def _device_code_prefix(device_code: str) -> str:
    """Short prefix for log lines — never log the full secret."""
    return device_code[:8]


@router.post("/init", status_code=status.HTTP_201_CREATED)
def device_auth_init(
    request: Request, payload: DeviceAuthInitPayload
) -> DeviceAuthInitResponse:
    """Device-initiated: start a new pairing flow. Open endpoint, rate-limited."""
    check_authorize_rate_limit(request)

    device_code = generate_device_code()
    user_code = generate_user_code()

    store_pending(
        device_code,
        user_code,
        {
            "client_device_identifier": payload.client_device_identifier,
            "name": payload.name,
            "client": payload.client,
            "platform": payload.platform,
            "client_version": payload.client_version,
            "requested_scopes": payload.requested_scopes,
            "interval": POLL_DEFAULT_INTERVAL_SECONDS,
        },
    )

    verification_url, verification_url_complete = build_verification_urls(
        request, user_code
    )

    log.info(
        f"device_auth.init client={payload.client} "
        f"identifier={payload.client_device_identifier} "
        f"device_code_prefix={_device_code_prefix(device_code)}"
    )

    return DeviceAuthInitResponse(
        device_code=device_code,
        user_code=user_code,
        verification_url=verification_url,
        verification_url_complete=verification_url_complete,
        expires_in=PENDING_TTL_SECONDS,
        interval=POLL_DEFAULT_INTERVAL_SECONDS,
    )


@protected_route(router.get, "/pending/{user_code}", [Scope.ME_READ])
def get_pending(request: Request, user_code: str) -> DeviceAuthPendingSchema:
    """Fetch a pending request's metadata for the approval screen."""
    normalized = normalize_user_code(user_code)
    device_code = resolve_device_code_from_user_code(normalized)
    if device_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired code",
        )

    data = load_pending(device_code)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired code",
        )
    if data.get("status") != FlowStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Code already {data.get('status')}",
        )

    user_scopes = {str(s) for s in request.user.oauth_scopes}
    requested = list(data.get("requested_scopes", []))
    allowed = sorted(set(requested) & user_scopes)

    return DeviceAuthPendingSchema(
        client_device_identifier=data["client_device_identifier"],
        name=data["name"],
        client=data["client"],
        platform=data.get("platform"),
        client_version=data.get("client_version"),
        requested_scopes=sorted(requested),
        allowed_scopes=allowed,
        expires_at=pending_expires_at(device_code),
    )


@protected_route(router.post, "/approve", [Scope.ME_WRITE])
def approve(
    request: Request, payload: DeviceAuthApprovePayload
) -> DeviceAuthApproveResponse:
    """Create the Device + bound ClientToken and mark the request approved."""
    normalized = normalize_user_code(payload.user_code)
    device_code = resolve_device_code_from_user_code(normalized)
    if device_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired code",
        )

    data = load_pending(device_code)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired code",
        )
    if data.get("status") != FlowStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Code already {data.get('status')}",
        )

    user_scopes = {str(s) for s in request.user.oauth_scopes}
    requested = set(data.get("requested_scopes", []))
    allowed = requested & user_scopes
    approved_set = set(payload.approved_scopes)
    if not approved_set or not approved_set.issubset(allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Approved scopes exceed what's allowed for this user",
        )

    expires_at = parse_expiry(payload.expires_in)

    now = datetime.now(timezone.utc)
    device_name = payload.device_name or data["name"]

    existing = db_device_handler.get_device_by_client_identifier(
        user_id=request.user.id,
        client_device_identifier=data["client_device_identifier"],
    )
    if existing is not None:
        update_data = {
            "name": device_name,
            "last_seen": now,
        }
        client_version = data.get("client_version")
        if client_version is not None:
            update_data["client_version"] = client_version
        db_device_handler.update_device(
            device_id=existing.id,
            user_id=request.user.id,
            data=update_data,
        )
        device = existing
    else:
        device = db_device_handler.add_device(
            Device(
                id=str(uuid.uuid4()),
                user_id=request.user.id,
                name=device_name,
                client=data.get("client"),
                platform=data.get("platform"),
                client_version=data.get("client_version"),
                client_device_identifier=data["client_device_identifier"],
                sync_mode=SyncMode.API,
                last_seen=now,
            )
        )

    raw_token = auth_handler.generate_client_token()
    token = db_client_token_handler.add_token(
        ClientToken(
            user_id=request.user.id,
            name=device_name,
            hashed_token=auth_handler.hash_client_token(raw_token),
            scopes=" ".join(sorted(approved_set)),
            expires_at=expires_at,
            device_id=device.id,
        )
    )

    mark_approved(
        device_code,
        raw_token=raw_token,
        device_id=device.id,
        scopes=sorted(approved_set),
        expires_at=token.expires_at,
    )

    log.info(
        f"device_auth.approve user_id={request.user.id} "
        f"device_id={device.id} token_id={token.id} "
        f"device_code_prefix={_device_code_prefix(device_code)} "
        f"scopes={' '.join(sorted(approved_set))}"
    )

    return DeviceAuthApproveResponse(device_id=device.id, device_name=device_name)


@protected_route(router.post, "/deny", [Scope.ME_WRITE])
def deny(request: Request, payload: DeviceAuthDenyPayload) -> None:
    normalized = normalize_user_code(payload.user_code)
    device_code = resolve_device_code_from_user_code(normalized)
    if device_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired code",
        )

    data = load_pending(device_code)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired code",
        )
    if data.get("status") != FlowStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Code already {data.get('status')}",
        )

    mark_denied(device_code)
    log.info(
        f"device_auth.deny user_id={request.user.id} "
        f"device_code_prefix={_device_code_prefix(device_code)}"
    )


@router.post("/token")
def token(request: Request, payload: DeviceAuthTokenPayload) -> DeviceAuthTokenResponse:
    """Device-facing polling endpoint. Open, rate-limited per-IP and per-code."""
    check_token_poll_rate_limit(request)

    data = load_pending(payload.device_code)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expired_token",
        )

    state = data.get("status")

    if state == FlowStatus.PENDING:
        interval = int(data.get("interval", POLL_DEFAULT_INTERVAL_SECONDS))
        if polled_too_fast(payload.device_code, interval):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="slow_down",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="authorization_pending",
        )

    if state == FlowStatus.DENIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="access_denied",
        )

    if state == FlowStatus.APPROVED:
        approved = consume_approved(payload.device_code)
        if approved is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="expired_token",
            )
        expires_at_raw = approved.get("expires_at")
        expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
        log.info(
            f"device_auth.token_issued device_id={approved['device_id']} "
            f"device_code_prefix={_device_code_prefix(payload.device_code)}"
        )
        return DeviceAuthTokenResponse(
            access_token=approved["raw_token"],
            device_id=approved["device_id"],
            scopes=list(approved.get("scopes", [])),
            expires_at=expires_at,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="expired_token",
    )
