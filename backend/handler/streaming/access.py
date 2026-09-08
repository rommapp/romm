"""Who may see and drive a streaming session, and which container holds it."""

from typing import Any

from fastapi import HTTPException, Request

from handler.auth.dependencies import get_permissions
from handler.database import db_platform_handler, db_rom_handler
from handler.streaming.config import (
    ResolvedContainer,
    containers_by_key,
    containers_for_platform,
)
from handler.streaming.session_store import get_live_session
from models.rom import Rom
from models.user import Role


def session_owner_id(session: dict[str, Any], request: Request) -> int:
    """Whose library a session's states and saves belong to.

    An admin may drive a session they do not own, and what it writes is still
    the player's, so the acting user only stands in for a record that names
    nobody.
    """
    user_id = session.get("user_id")
    return user_id if isinstance(user_id, int) else request.user.id


def assert_session_owner(session: dict[str, Any], request: Request) -> None:
    """Only the user who claimed a session (or an admin) may control it."""
    if session.get("user_id") == request.user.id:
        return
    if request.user.role == Role.ADMIN:
        return
    raise HTTPException(status_code=403, detail="Session is claimed by another user")


def rom_is_visible(request: Request, rom: Rom | None) -> bool:
    """Can the caller see this ROM?

    Sessions outlive nothing but the cache, so a rom_id that no longer
    resolves is treated as visible: there is no hidden ROM left to protect.
    """
    if rom is None:
        return True
    if not request.user.is_authenticated:
        return True
    return get_permissions(request).can_see_rom(rom.id, rom.platform_id)


def _session_rom_is_visible(request: Request, session: dict[str, Any]) -> bool:
    """Can the caller see the ROM a session is running?"""
    rom_id = session.get("rom_id")
    if rom_id is None:
        return True
    return rom_is_visible(request, db_rom_handler.get_rom_simple(rom_id))


def assert_session_rom_visible(
    request: Request, session: dict[str, Any], *, not_found_detail: str
) -> None:
    """Raise 404 when the session's ROM is hidden from the caller."""
    if not _session_rom_is_visible(request, session):
        raise HTTPException(status_code=404, detail=not_found_detail)


def visible_rom_name(request: Request, session: dict[str, Any]) -> str | None:
    """The name of the ROM a session is running, blanked when the caller cannot
    see that ROM. "Busy" is safe to report to anyone; what is running is not."""
    if not session or not _session_rom_is_visible(request, session):
        return None
    name = session.get("rom_name")
    return str(name) if name else None


def platform_is_visible(request: Request, platform_slug: str) -> bool:
    """Can the caller see this platform?

    A container may name a slug the library has never scanned, which has no
    platform row and so nothing to hide.
    """
    if not platform_slug or not request.user.is_authenticated:
        return True
    platform = db_platform_handler.get_platform_by_slug(platform_slug)
    if platform is None:
        return True
    return get_permissions(request).can_see_platform(platform.id)


async def find_session_for_user(
    candidates: list[ResolvedContainer], user_id: int
) -> tuple[ResolvedContainer, str, dict[str, Any]] | None:
    """The candidate holding this user's session, as (container, key, session).

    With a pool the platform no longer identifies the container, the session
    does.
    """
    for candidate in candidates:
        session_key = candidate.key
        session = await get_live_session(session_key)
        if session is None:
            continue
        if session.get("user_id") == user_id:
            return candidate, session_key, session
    return None


async def resolve_named_container(
    platform: str, container_key: str
) -> tuple[ResolvedContainer, str, dict[str, Any] | None]:
    """One named container serving a platform, plus whatever session it holds.

    Returns (container, session_key, session), the session being None when the
    container is free or draining. Raises 404 when the key names no container
    serving this platform.
    """
    for candidate in containers_for_platform(platform):
        session_key = candidate.key
        if session_key != container_key:
            continue
        return candidate, session_key, await get_live_session(session_key)
    raise HTTPException(
        status_code=404,
        detail=f"No streaming container '{container_key}' for platform '{platform}'",
    )


async def resolve_owned_session(
    platform: str, request: Request
) -> tuple[ResolvedContainer, str, dict[str, Any]]:
    """Find the caller's session among the platform's containers.

    Returns (container, session_key, session). Raises 404 when the platform has
    no configured container or nothing is active, 403 when every active session
    belongs to someone else, 409 when an admin's fallback is ambiguous.
    """
    candidates = containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )

    others: list[tuple[ResolvedContainer, str, dict[str, Any]]] = []
    for candidate in candidates:
        session_key = candidate.key
        session = await get_live_session(session_key)
        if session is None:
            continue
        if session.get("user_id") == request.user.id:
            return candidate, session_key, session
        others.append((candidate, session_key, session))

    if not others:
        raise HTTPException(
            status_code=404, detail=f"No active session for platform '{platform}'"
        )
    # An admin may control a session they do not own, but the scan found none of
    # theirs, so fall back to the platform's active session. A pool can hold
    # several and the path does not say which, so the caller has to name one.
    if request.user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403, detail="Session is claimed by another user"
        )
    if len(others) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{len(others)} sessions are active on platform '{platform}', "
                "name a container instead"
            ),
        )
    return others[0]


def container_by_key(container_key: str) -> tuple[ResolvedContainer, str]:
    """A configured container named by its key, plus the platform to file its
    sessions under.

    The session routes are platform-keyed, so a container serving several gets
    the first, which `container_for_session` resolves back to this entry.
    Raises 404 when the key names no container.
    """
    entries = containers_by_key().get(container_key) if container_key else None
    if not entries:
        raise HTTPException(
            status_code=404, detail=f"No streaming container '{container_key}'"
        )
    return entries[0], entries[0].platform
