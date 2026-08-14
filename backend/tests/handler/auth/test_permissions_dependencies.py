"""Pure unit tests for the fine-grained enforcement helpers (no DB needed)."""

import pytest
from fastapi import HTTPException

from handler.auth.dependencies import assert_can, can_access
from handler.auth.permissions import ResolvedGrant, ResolvedPermissions
from models.permission import PermAction, PermEntity


def _perms(*, is_admin=False, user_id=1, grants=()):
    return ResolvedPermissions(
        is_admin=is_admin,
        user_id=user_id,
        grants=frozenset(grants),
        hidden_platform_ids=frozenset(),
        hidden_rom_ids=frozenset(),
    )


def test_admin_can_do_anything():
    perms = _perms(is_admin=True)
    assert can_access(perms, PermEntity.USERS, PermAction.DELETE)
    assert can_access(perms, PermEntity.ROMS, PermAction.WRITE, owner_id=999)


def test_library_wide_grant_allows_any_resource():
    perms = _perms(grants=[ResolvedGrant(PermEntity.ROMS, PermAction.DELETE, False)])
    assert can_access(perms, PermEntity.ROMS, PermAction.DELETE)
    assert can_access(perms, PermEntity.ROMS, PermAction.DELETE, owner_id=999)


def test_missing_grant_is_denied():
    perms = _perms(grants=[ResolvedGrant(PermEntity.ROMS, PermAction.READ, False)])
    assert not can_access(perms, PermEntity.ROMS, PermAction.DELETE)


def test_owner_always_allowed_even_without_grant():
    perms = _perms(user_id=7, grants=())
    assert can_access(perms, PermEntity.COLLECTIONS, PermAction.WRITE, owner_id=7)
    assert not can_access(perms, PermEntity.COLLECTIONS, PermAction.WRITE, owner_id=8)


def test_own_only_grant_does_not_allow_others_resources():
    # own_only collections.write: may act on own (owner_id match) but not others'.
    perms = _perms(
        user_id=7,
        grants=[ResolvedGrant(PermEntity.COLLECTIONS, PermAction.WRITE, True)],
    )
    assert can_access(perms, PermEntity.COLLECTIONS, PermAction.WRITE, owner_id=7)
    assert not can_access(perms, PermEntity.COLLECTIONS, PermAction.WRITE, owner_id=8)
    # No owner context (library-wide attempt) -> own_only is insufficient.
    assert not can_access(perms, PermEntity.COLLECTIONS, PermAction.WRITE)


def test_assert_can_raises_403():
    perms = _perms(grants=())
    with pytest.raises(HTTPException) as exc:
        assert_can(perms, PermEntity.PLATFORMS, PermAction.DELETE)
    assert exc.value.status_code == 403
