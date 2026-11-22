"""Use the OIDC `picture` claim as a user's avatar."""

import asyncio
import os
from typing import Any

import httpx2
import magic
import pydash

from config import OIDC_SERVER_APPLICATION_URL, OIDC_SERVER_METADATA_URL
from decorators.auth import OIDC_SSL_CONTEXT
from handler.database import db_user_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import sniff_mime_type
from logger.logger import log
from models.user import User
from utils.context import create_httpx_async_client
from utils.media_types import IMAGE_EXT_BY_MIME_TYPE
from utils.ssrf import parse_origin, validate_url_for_http_request
from utils.validation import ValidationError

# The file name marks an avatar as synced from the provider, so a later sign-in
# refreshes it while an avatar the user uploaded (`avatar.<ext>`) is left alone.
OIDC_AVATAR_STEM = "oidc-avatar"
MAX_OIDC_AVATAR_BYTES = 5 * 1024 * 1024
OIDC_AVATAR_TIMEOUT_SECONDS = 10

# Self-hosted providers often serve pictures from a LAN address, so private
# addresses are allowed only for the provider the admin configured.
OIDC_AVATAR_ORIGIN_ALLOWLIST: frozenset[tuple[str, int]] = frozenset(
    pydash.compact(
        [
            parse_origin(OIDC_SERVER_APPLICATION_URL),
            parse_origin(OIDC_SERVER_METADATA_URL or ""),
        ]
    )
)


def is_oidc_avatar(avatar_path: str) -> bool:
    return os.path.basename(avatar_path).startswith(f"{OIDC_AVATAR_STEM}.")


async def _download_picture(url: str) -> bytes | None:
    """Download the picture in at most OIDC_AVATAR_TIMEOUT_SECONDS overall; None if it exceeds the size limit."""
    async with (
        asyncio.timeout(OIDC_AVATAR_TIMEOUT_SECONDS),
        create_httpx_async_client(
            allowlist=OIDC_AVATAR_ORIGIN_ALLOWLIST, verify=OIDC_SSL_CONTEXT or True
        ) as client,
        client.stream(
            "GET", url, follow_redirects=True, timeout=OIDC_AVATAR_TIMEOUT_SECONDS
        ) as res,
    ):
        res.raise_for_status()
        content = bytearray()
        async for chunk in res.aiter_bytes():
            content.extend(chunk)
            if len(content) > MAX_OIDC_AVATAR_BYTES:
                log.warning("OIDC picture is larger than the avatar size limit")
                return None
    return bytes(content)


async def _remove_quietly(path: str) -> None:
    try:
        await fs_asset_handler.remove_file(path)
    except OSError:
        log.debug(f"Could not remove the unused OIDC avatar {path}")


async def discard_oidc_avatar(avatar_path: str) -> None:
    """Delete a synced avatar's file once an uploaded avatar has replaced it."""
    if avatar_path and is_oidc_avatar(avatar_path):
        await _remove_quietly(avatar_path)


async def sync_oidc_avatar(user: User, userinfo: dict[str, Any] | None) -> None:
    """Store the provider's picture as the avatar unless the user uploaded one; failures are logged and never block sign-in."""
    picture = (userinfo or {}).get("picture")
    if not isinstance(picture, str) or not picture:
        return
    if user.avatar_path and not is_oidc_avatar(user.avatar_path):
        return

    try:
        validate_url_for_http_request(
            picture,
            field_name="OIDC picture",
            allowlist=OIDC_AVATAR_ORIGIN_ALLOWLIST,
        )
        content = await _download_picture(picture)
    except TimeoutError:
        log.warning(f"Timed out fetching the OIDC picture for {user.username}")
        return
    except (ValidationError, ValueError, httpx2.HTTPError, httpx2.InvalidURL) as exc:
        log.warning(f"Could not fetch the OIDC picture for {user.username}: {exc}")
        return
    if not content:
        return

    try:
        extension = IMAGE_EXT_BY_MIME_TYPE.get(sniff_mime_type(content))
    except magic.MagicException as exc:
        log.warning(f"Could not detect the OIDC picture's file type: {exc}")
        return
    if not extension:
        log.warning(f"OIDC picture for {user.username} is not a supported image")
        return

    avatar_dir = fs_asset_handler.build_avatar_path(user=user)
    file_name = f"{OIDC_AVATAR_STEM}.{extension}"
    file_location = f"{avatar_dir}/{file_name}"
    try:
        await fs_asset_handler.write_file(
            file=content, path=avatar_dir, filename=file_name
        )
    except OSError as exc:
        log.warning(f"Could not store the OIDC picture for {user.username}: {exc}")
        return

    previous_path = user.avatar_path
    # The user may have uploaded an avatar while the picture was downloading.
    if not db_user_handler.replace_avatar_path(user.id, previous_path, file_location):
        current = db_user_handler.get_user(user.id)
        if current is None or current.avatar_path != file_location:
            await _remove_quietly(file_location)
        return
    if previous_path and previous_path != file_location:
        await _remove_quietly(previous_path)
