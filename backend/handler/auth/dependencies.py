"""Fine-grained, DB-backed permission checks for endpoint handlers.

The coarse ``@protected_route(..., [Scope.X])`` gate stays the first line of
defense (and is what client tokens / kiosk rely on). These helpers add the
authoritative per-entity / per-action / ownership / visibility decisions on top,
resolved once per request and cached on ``request.state``.

Typical use inside a handler::

    perms = get_permissions(request)
    assert_can(perms, PermEntity.ROMS, PermAction.DELETE)          # library-wide
    assert_can(perms, PermEntity.COLLECTIONS, PermAction.WRITE,
               owner_id=collection.user_id)                        # own-data ok
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status

from exceptions.endpoint_exceptions import (
    PlatformNotFoundInDatabaseException,
    RomNotFoundInDatabaseException,
)
from handler.auth.permissions import ResolvedPermissions, resolve_permissions
from models.permission import PermAction, PermEntity

if TYPE_CHECKING:
    from models.firmware import Firmware
    from models.platform import Platform
    from models.rom import Rom


def get_permissions(request: Request) -> ResolvedPermissions:
    """Resolve (and cache for the request) the caller's effective permissions."""
    cached = getattr(request.state, "permissions", None)
    if cached is not None:
        return cached
    perms = resolve_permissions(request.user)
    request.state.permissions = perms
    return perms


def can_access(
    perms: ResolvedPermissions,
    entity: PermEntity,
    action: PermAction,
    *,
    owner_id: int | None = None,
) -> bool:
    """Whether ``perms`` may perform ``action`` on ``entity``.

    Admins bypass. A user may always act on a resource they own (``owner_id``
    matches). Otherwise a library-wide (non ``own_only``) grant is required.
    """
    if perms.is_admin:
        return True
    if owner_id is not None and owner_id == perms.user_id:
        return True
    return perms.allows(entity, action, owned=False)


def assert_can(
    perms: ResolvedPermissions,
    entity: PermEntity,
    action: PermAction,
    *,
    owner_id: int | None = None,
) -> None:
    """Raise 403 unless ``perms`` may perform ``action`` on ``entity``."""
    if not can_access(perms, entity, action, owner_id=owner_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


def require_permission(entity: PermEntity, action: PermAction):
    """FastAPI dependency factory for library-wide gating of a route.

    Returns the resolved permissions so the handler can reuse them.
    """

    def _dependency(request: Request) -> ResolvedPermissions:
        perms = get_permissions(request)
        assert_can(perms, entity, action)
        return perms

    return _dependency


def assert_admin(request: Request) -> ResolvedPermissions:
    """Raise 403 unless the caller is an admin. For permission-management routes."""
    perms = get_permissions(request)
    if not perms.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return perms


# 404-masking helpers: a hidden entity must read as non-existent, not forbidden,
# so its existence isn't leaked. The auth guard skips the check on unauthenticated
# download endpoints, which carry no permission context to resolve.
def assert_rom_visible(
    request: Request, rom: Rom, *, not_found_detail: str | None = None
) -> None:
    """Raise 404 (not 403) when the rom is hidden from the caller.

    Defaults to the standard ``RomNotFoundInDatabaseException`` message; pass
    ``not_found_detail`` for endpoints with a bespoke 404 (metadata-id / hash
    lookups) so the masked response is indistinguishable from their not-found.
    """
    if request.user.is_authenticated and not get_permissions(request).can_see_rom(
        rom.id, rom.platform_id
    ):
        if not_found_detail is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail
            )
        raise RomNotFoundInDatabaseException(rom.id)


def assert_platform_visible(
    request: Request, platform: Platform, *, not_found_detail: str | None = None
) -> None:
    """Raise 404 (not 403) when the platform is hidden from the caller.

    Pass ``not_found_detail`` to match an endpoint's bespoke 404 message.
    """
    if request.user.is_authenticated and not get_permissions(request).can_see_platform(
        platform.id
    ):
        if not_found_detail is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail
            )
        raise PlatformNotFoundInDatabaseException(platform.id)


def assert_firmware_visible(request: Request, firmware: Firmware) -> None:
    """Raise 404 when the firmware's platform is hidden (firmware inherits it)."""
    if request.user.is_authenticated and not get_permissions(request).can_see_platform(
        firmware.platform_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware with ID {firmware.id} not found",
        )
