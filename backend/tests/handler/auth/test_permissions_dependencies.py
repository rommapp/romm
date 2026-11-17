"""Pure unit tests for the fine-grained enforcement helpers (no DB needed)."""

from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException, Request

from handler.auth.dependencies import (
    assert_can,
    can_access,
    visible_firmware_or_404,
    visible_platform_or_404,
    visible_rom_or_404,
)
from handler.auth.permissions import ResolvedGrant, ResolvedPermissions
from models.firmware import Firmware
from models.permission import PermAction, PermEntity
from models.platform import Platform
from models.rom import Rom


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


def _request(perms: ResolvedPermissions) -> Request:
    return cast(
        Request,
        SimpleNamespace(
            user=SimpleNamespace(is_authenticated=True, id=perms.user_id),
            state=SimpleNamespace(permissions=perms),
        ),
    )


def _hiding(*, rom_ids=(), platform_ids=()) -> ResolvedPermissions:
    return ResolvedPermissions(
        is_admin=False,
        user_id=1,
        grants=frozenset(),
        hidden_platform_ids=frozenset(platform_ids),
        hidden_rom_ids=frozenset(rom_ids),
    )


def _not_found(call) -> tuple[int, object]:
    with pytest.raises(HTTPException) as exc:
        call()
    return exc.value.status_code, exc.value.detail


@pytest.mark.parametrize("not_found", [5, "No ROM here"])
def test_visible_rom_or_404_answers_hidden_like_missing(not_found):
    rom = Rom(id=5, platform_id=2)
    request = _request(_hiding(rom_ids={5}))

    missing = _not_found(lambda: visible_rom_or_404(request, None, not_found))
    hidden = _not_found(lambda: visible_rom_or_404(request, rom, not_found))

    assert missing == hidden
    assert missing[0] == 404
    assert visible_rom_or_404(_request(_hiding()), rom, not_found) is rom


@pytest.mark.parametrize("not_found", [2, "No platform here"])
def test_visible_platform_or_404_answers_hidden_like_missing(not_found):
    platform = Platform(id=2)
    request = _request(_hiding(platform_ids={2}))

    missing = _not_found(lambda: visible_platform_or_404(request, None, not_found))
    hidden = _not_found(lambda: visible_platform_or_404(request, platform, not_found))

    assert missing == hidden
    assert missing[0] == 404
    assert visible_platform_or_404(_request(_hiding()), platform, not_found) is platform


def test_visible_firmware_or_404_answers_hidden_like_missing():
    firmware = Firmware(id=3, platform_id=2)
    request = _request(_hiding(platform_ids={2}))

    missing = _not_found(lambda: visible_firmware_or_404(request, None, 3))
    hidden = _not_found(lambda: visible_firmware_or_404(request, firmware, 3))

    assert missing == hidden == (404, "Firmware with ID 3 not found")
    assert visible_firmware_or_404(_request(_hiding()), firmware, 3) is firmware
