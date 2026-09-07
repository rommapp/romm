"""Seed (or reset) the fixture users the Playwright e2e suite logs in as.

Idempotent: re-running resets the passwords and group assignment rather than
erroring on the existing rows. Pass ``--remove`` to delete the fixtures again.

    uv run python .github/scripts/seed_e2e_users.py
    uv run python .github/scripts/seed_e2e_users.py --remove

Two accounts, matching the two sides of every permission assertion:

  * ``e2e_admin``  — role admin, so `useCan` short-circuits to true and every
    gated affordance must be present.
  * ``e2e_viewer`` — the seeded "Viewer (legacy)" group, i.e. library read plus
    own collections/assets. Every ROM write affordance must be absent.

Never point this at a real library: it writes users with a known password.
"""

from __future__ import annotations

import argparse
import os
import sys

# The app package lives in backend/; add it to the path so these can import
# `handler.*` / `models.*` the same way the backend does.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
)

from handler.auth import auth_handler  # noqa: E402
from handler.database import db_permission_handler, db_user_handler  # noqa: E402
from models.user import Role, User  # noqa: E402

VIEWER_GROUP_NAME = "Viewer (legacy)"

E2E_ADMIN_USERNAME = "e2e_admin"
E2E_VIEWER_USERNAME = "e2e_viewer"
# Fixture-only credential for a throwaway dev instance
PASSWORD = os.environ.get("E2E_PASSWORD", "e2e-Passw0rd!")  # nosec B105


def _viewer_group_id() -> int:
    for group in db_permission_handler.get_groups():
        if group.name == VIEWER_GROUP_NAME:
            return group.id
    raise SystemExit(
        f"No {VIEWER_GROUP_NAME!r} group found, run `alembic upgrade head` first."
    )


def _upsert(username: str, role: Role, permission_group_id: int | None) -> None:
    hashed = auth_handler.get_password_hash(PASSWORD)
    existing = db_user_handler.get_user_by_username(username)
    if existing:
        db_user_handler.update_user(
            existing.id,
            {
                "hashed_password": hashed,
                "role": role,
                "enabled": True,
                "permission_group_id": permission_group_id,
            },
        )
        print(f"reset  {username} (id={existing.id}, role={role})")
        return

    user = db_user_handler.add_user(
        User(
            username=username,
            hashed_password=hashed,
            email=f"{username}@example.invalid",
            role=role,
            enabled=True,
            permission_group_id=permission_group_id,
        )
    )
    print(f"create {username} (id={user.id}, role={role})")


def _remove() -> None:
    for username in (E2E_ADMIN_USERNAME, E2E_VIEWER_USERNAME):
        user = db_user_handler.get_user_by_username(username)
        if user:
            db_user_handler.delete_user(user.id)
            print(f"delete {username} (id={user.id})")
        else:
            print(f"absent {username}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--remove", action="store_true", help="delete the fixture users instead"
    )
    args = parser.parse_args()

    if args.remove:
        _remove()
        return 0

    _upsert(E2E_ADMIN_USERNAME, Role.ADMIN, None)
    _upsert(E2E_VIEWER_USERNAME, Role.USER, _viewer_group_id())
    return 0


if __name__ == "__main__":
    sys.exit(main())
