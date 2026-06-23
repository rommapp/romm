"""Proves the new permission model preserves every user's pre-upgrade access.

Two layers:
  * Pure parity -- the legacy grant matrices, projected back onto coarse scopes,
    reproduce exactly what each role's ``oauth_scopes`` returns today.
  * Seed integrity -- the rows the Alembic migration actually wrote into the DB
    match those same in-code matrices, so the frozen migration literals can't
    silently drift from ``permissions_map.py``.
"""

from handler.auth.constants import EDIT_SCOPES, FULL_SCOPES, WRITE_SCOPES
from handler.auth.permissions_map import (
    LEGACY_EDITOR_GRANTS,
    LEGACY_VIEWER_GRANTS,
    grants_to_scopes,
)
from handler.database.base_handler import sync_session
from models.permission import PermissionGroup
from models.user import Role, User

# --- Pure parity: matrices reproduce legacy scopes ---------------------------


def test_viewer_matrix_projects_to_write_scopes():
    projected = set(grants_to_scopes(LEGACY_VIEWER_GRANTS))
    assert projected == set(WRITE_SCOPES)
    # And matches the property on an in-memory non-kiosk user.
    assert projected == set(User(role=Role.VIEWER).oauth_scopes)


def test_editor_matrix_projects_to_edit_scopes():
    projected = set(grants_to_scopes(LEGACY_EDITOR_GRANTS))
    assert projected == set(EDIT_SCOPES)
    assert projected == set(User(role=Role.EDITOR).oauth_scopes)


def test_admin_projects_to_full_scopes():
    projected = set(grants_to_scopes([], is_admin=True))
    assert projected == set(FULL_SCOPES)
    assert projected == set(User(role=Role.ADMIN).oauth_scopes)


def test_editor_strictly_extends_viewer():
    # The only coarse difference is library-wide write of roms/platforms/firmware.
    extra = set(grants_to_scopes(LEGACY_EDITOR_GRANTS)) - set(
        grants_to_scopes(LEGACY_VIEWER_GRANTS)
    )
    assert {s.value for s in extra} == {
        "roms.write",
        "platforms.write",
        "firmware.write",
    }


# --- Seed integrity: migration rows match the in-code matrices ---------------


def _grant_tuples(group: PermissionGroup) -> set[tuple[str, str, bool]]:
    return {(g.entity.value, g.action.value, g.own_only) for g in group.grants}


def _expected_tuples(matrix) -> set[tuple[str, str, bool]]:
    return {(e.value, a.value, o) for (e, a, o) in matrix}


def test_migration_seeded_legacy_groups():
    with sync_session.begin() as s:
        groups = {
            g.name: g
            for g in s.query(PermissionGroup)
            .filter(PermissionGroup.name.in_(["Viewer (legacy)", "Editor (legacy)"]))
            .all()
        }

        assert set(groups) == {"Viewer (legacy)", "Editor (legacy)"}

        viewer = groups["Viewer (legacy)"]
        editor = groups["Editor (legacy)"]

        # Viewer is the server-wide default; both are system groups.
        assert viewer.is_default is True
        assert viewer.is_system is True
        assert editor.is_default is False
        assert editor.is_system is True

        # Seeded grants equal the frozen matrices (no drift).
        assert _grant_tuples(viewer) == _expected_tuples(LEGACY_VIEWER_GRANTS)
        assert _grant_tuples(editor) == _expected_tuples(LEGACY_EDITOR_GRANTS)


def test_exactly_one_default_group():
    with sync_session.begin() as s:
        defaults = (
            s.query(PermissionGroup)
            .filter(PermissionGroup.is_default.is_(True))
            .count()
        )
    assert defaults == 1
