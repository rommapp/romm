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

from fastapi import HTTPException, Request, status

from handler.auth.permissions import ResolvedPermissions, resolve_permissions
from models.permission import PermAction, PermEntity


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
