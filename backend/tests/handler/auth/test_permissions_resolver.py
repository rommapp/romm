"""Resolver + projection behavior: precedence, overrides, own_only, hiding, kiosk.

Complements ``test_permissions_parity.py`` (which proves the static matrices).
Here we exercise ``resolve_permissions`` / ``compute_oauth_scopes`` end-to-end
against the DB: group membership, per-user overrides, ownership scoping, hidden
entities, and the KIOSK_MODE anonymous-visitor cap.
"""

import pytest

from handler.auth.constants import EDIT_SCOPES, FULL_SCOPES, READ_SCOPES, WRITE_SCOPES
from handler.auth.permissions import resolve_permissions
from handler.database import db_user_handler
from handler.database.base_handler import sync_session
from models.permission import (
    HiddenEntity,
    PermAction,
    PermEntity,
    PermissionGroup,
    PermissionGroupGrant,
    UserPermissionOverride,
)
from models.user import User


@pytest.fixture(autouse=True)
def _cleanup_non_system_groups():
    # clear_database (conftest) deletes users, cascading overrides + user-hidden
    # rows via FK. Non-system groups created by these tests are not user-bound,
    # so drop them (cascading their grants + group-hidden rows) after each test.
    yield
    with sync_session.begin() as s:
        s.query(PermissionGroup).filter(PermissionGroup.is_system.is_(False)).delete(
            synchronize_session="evaluate"
        )


def _make_group(name, grants, *, is_default=False):
    with sync_session.begin() as s:
        group = PermissionGroup(name=name, is_default=is_default, is_system=False)
        s.add(group)
        s.flush()
        gid = group.id
        for entity, action, own_only in grants:
            s.add(
                PermissionGroupGrant(
                    group_id=gid, entity=entity, action=action, own_only=own_only
                )
            )
    return gid


def _set_group(user: User, group_id: int) -> User:
    db_user_handler.update_user(user.id, {"permission_group_id": group_id})
    return db_user_handler.get_user(user.id)


def _add_override(user_id, entity, action, *, granted, own_only=False):
    with sync_session.begin() as s:
        s.add(
            UserPermissionOverride(
                user_id=user_id,
                entity=entity,
                action=action,
                granted=granted,
                own_only=own_only,
            )
        )


def _hide(entity, entity_id, *, user_id=None, group_id=None):
    with sync_session.begin() as s:
        s.add(
            HiddenEntity(
                entity=entity, entity_id=entity_id, user_id=user_id, group_id=group_id
            )
        )


# --- Projection parity through the live property (group-less users) ----------


def test_property_parity_for_group_less_users(admin_user, editor_user, viewer_user):
    assert set(admin_user.oauth_scopes) == set(FULL_SCOPES)
    assert set(editor_user.oauth_scopes) == set(EDIT_SCOPES)
    assert set(viewer_user.oauth_scopes) == set(WRITE_SCOPES)


# --- Kiosk mode: the anonymous visitor is capped, accounts are not -----------


@pytest.fixture
def kiosk_mode(monkeypatch):
    monkeypatch.setattr("handler.auth.permissions.KIOSK_MODE", True)


def test_kiosk_leaves_logged_in_users_alone(
    kiosk_mode, admin_user, editor_user, viewer_user
):
    # Kiosk mode locks down anonymous visitors, not accounts someone logged
    # into: every user keeps exactly what their group and overrides grant.
    assert set(viewer_user.oauth_scopes) == set(WRITE_SCOPES)
    assert set(editor_user.oauth_scopes) == set(EDIT_SCOPES)
    assert set(admin_user.oauth_scopes) == set(FULL_SCOPES)


def test_kiosk_honors_write_override_on_logged_in_user(kiosk_mode, viewer_user):
    _add_override(viewer_user.id, PermEntity.ROMS, PermAction.WRITE, granted=True)
    user = db_user_handler.get_user(viewer_user.id)
    assert "roms.write" in {s.value for s in user.oauth_scopes}
    assert resolve_permissions(user).allows(PermEntity.ROMS, PermAction.WRITE)


def test_kiosk_guest_is_capped_to_read(kiosk_mode):
    # The default group grants writes, so the cap is what keeps the shared
    # synthetic visitor (id=-1) from uploading assets or editing collections.
    guest = User.kiosk_mode_user()
    assert set(guest.oauth_scopes) == set(READ_SCOPES)

    perms = resolve_permissions(guest)
    assert not perms.is_admin
    assert {g.action for g in perms.grants} == {PermAction.READ}
    assert perms.allows(PermEntity.ROMS, PermAction.READ)
    assert not perms.allows(PermEntity.ASSETS, PermAction.WRITE)


# --- Precedence: group > legacy role fallback --------------------------------


def test_explicit_group_overrides_role_fallback(editor_user):
    # A read-only group assigned to an (legacy) editor strips write access.
    gid = _make_group("readonly", [(PermEntity.ROMS, PermAction.READ, False)])
    user = _set_group(editor_user, gid)
    scopes = {s.value for s in user.oauth_scopes}
    assert "roms.read" in scopes
    assert "roms.write" not in scopes  # role said editor, group says read-only
    # Self-service scopes are always present regardless of group.
    assert {"me.read", "me.write", "roms.user.read", "roms.user.write"} <= scopes


# --- Per-user overrides add and revoke ---------------------------------------


def test_override_grants_extra_capability(viewer_user):
    _add_override(viewer_user.id, PermEntity.ROMS, PermAction.WRITE, granted=True)
    user = db_user_handler.get_user(viewer_user.id)
    assert "roms.write" in {s.value for s in user.oauth_scopes}
    perms = resolve_permissions(user)
    assert perms.allows(PermEntity.ROMS, PermAction.WRITE)


def test_override_revokes_group_capability(viewer_user):
    # Viewer matrix grants collections.write (own); a revoke override removes it.
    _add_override(
        viewer_user.id, PermEntity.COLLECTIONS, PermAction.WRITE, granted=False
    )
    user = db_user_handler.get_user(viewer_user.id)
    assert "collections.write" not in {s.value for s in user.oauth_scopes}


# --- Admin bypass and own_only semantics -------------------------------------


def test_admin_bypass(admin_user):
    perms = resolve_permissions(admin_user)
    assert perms.is_admin
    assert perms.allows(PermEntity.USERS, PermAction.DELETE)
    assert perms.allows(PermEntity.ROMS, PermAction.WRITE, owned=False)


def test_own_only_requires_ownership(viewer_user):
    perms = resolve_permissions(viewer_user)
    # collections.write is own_only in the viewer matrix.
    assert perms.allows(PermEntity.COLLECTIONS, PermAction.WRITE, owned=True)
    assert not perms.allows(PermEntity.COLLECTIONS, PermAction.WRITE, owned=False)
    assert not perms.allows(PermEntity.COLLECTIONS, PermAction.WRITE)
    # collections.read is library-wide (own_only False) -> always allowed.
    assert perms.allows(PermEntity.COLLECTIONS, PermAction.READ)


# --- Hidden entities (user and group principals) -----------------------------


def test_user_hidden_platform_and_rom_cascade(viewer_user):
    _hide(PermEntity.PLATFORMS, 5, user_id=viewer_user.id)
    _hide(PermEntity.ROMS, 99, user_id=viewer_user.id)
    perms = resolve_permissions(viewer_user)
    assert perms.hidden_platform_ids == frozenset({5})
    assert perms.hidden_rom_ids == frozenset({99})
    assert not perms.can_see_platform(5)
    assert perms.can_see_platform(6)
    # Rom on a hidden platform is hidden even if the rom itself isn't listed.
    assert not perms.can_see_rom(1, platform_id=5)
    assert not perms.can_see_rom(99, platform_id=6)
    assert perms.can_see_rom(1, platform_id=6)


def test_group_hidden_applies_to_members(viewer_user):
    gid = _make_group("kids", [(PermEntity.ROMS, PermAction.READ, False)])
    user = _set_group(viewer_user, gid)
    _hide(PermEntity.PLATFORMS, 7, group_id=gid)
    perms = resolve_permissions(user)
    assert 7 in perms.hidden_platform_ids
    assert not perms.can_see_platform(7)


def test_admin_sees_everything_despite_hides(admin_user):
    _hide(PermEntity.PLATFORMS, 5, user_id=admin_user.id)
    perms = resolve_permissions(admin_user)
    assert perms.can_see_platform(5)


def test_default_group_is_viewer_legacy():
    from handler.database import db_permission_handler

    group = db_permission_handler.get_default_group()
    assert group is not None
    assert group.name == "Viewer (legacy)"
